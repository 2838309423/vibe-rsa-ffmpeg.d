#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阿里云百炼：本地音频 -> 临时 OSS(oss://) -> Paraformer 非实时识别（带时间戳）-> 结果 JSON。

用法: python3 bin/asr_cn.py <audio_file> <out_dir> [model]

流程（全部走官方 RESTful，不依赖公网入站）：
  1. GET  /api/v1/uploads?action=getPolicy&model=<model>   取上传凭证
  2. POST <upload_host>（multipart 表单）上传文件           得到 oss://...
  3. POST /api/v1/services/audio/asr/transcription         提交任务（带 X-DashScope-OssResourceResolve: enable）
  4. POST /api/v1/tasks/{task_id}                          轮询到 SUCCEEDED
  5. GET  transcription_url                                下载识别结果（sentences/words 时间戳）

产出: <out_dir>/transcription.json（原始结果）、<out_dir>/asr.log（过程日志）
"""
import json
import mimetypes
import os
import sys
import time
import urllib.parse
import urllib.request

KEY_FILE = os.path.expanduser("~/.config/aliyun-bailian/api-key.txt")
UPLOADS_URL = "https://dashscope.aliyuncs.com/api/v1/uploads"


def load_key():
    key = host = None
    for line in open(KEY_FILE, encoding="utf-8"):
        s = line.strip()
        if s.startswith("sk-"):
            key = s
        if "maas.aliyuncs.com" in s:
            host = s
    if not key:
        raise SystemExit("key 文件里没找到 sk-...")
    wid = host.split(".")[0] if host else None
    base = ("https://%s.cn-beijing.maas.aliyuncs.com" % wid) if wid \
        else "https://dashscope.aliyuncs.com"
    return key, base


def http(url, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.status, r.read()


def get_policy(key, model):
    url = UPLOADS_URL + "?" + urllib.parse.urlencode({"action": "getPolicy", "model": model})
    st, body = http(url, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    j = json.loads(body)
    if st != 200:
        raise SystemExit("取上传凭证失败: %s" % body[:500])
    return j["data"]


def multipart(fields, file_field, file_path):
    """构造 multipart/form-data：fields 为文本字段，file_field 为文件字段名。"""
    boundary = "----dshform" + str(int(time.time() * 1000))
    out = []
    for k, v in fields.items():
        out.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                    % (boundary, k, v)).encode())
    fn = os.path.basename(file_path)
    ctype = mimetypes.guess_type(fn)[0] or "application/octet-stream"
    out.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                "Content-Type: %s\r\n\r\n" % (boundary, file_field, fn, ctype)).encode())
    out.append(open(file_path, "rb").read())
    out.append(("\r\n--%s--\r\n" % boundary).encode())
    return b"".join(out), "multipart/form-data; boundary=" + boundary


def upload(key, model, file_path):
    pol = get_policy(key, model)
    fname = os.path.basename(file_path)
    keyname = "%s/%s" % (pol["upload_dir"], fname)
    fields = {
        "OSSAccessKeyId": pol["oss_access_key_id"],
        "Signature": pol["signature"],
        "policy": pol["policy"],
        "x-oss-object-acl": pol["x_oss_object_acl"],
        "x-oss-forbid-overwrite": pol["x_oss_forbid_overwrite"],
        "key": keyname,
        "success_action_status": "200",
    }
    body, ctype = multipart(fields, "file", file_path)
    st, resp = http(pol["upload_host"], data=body, headers={"Content-Type": ctype}, method="POST")
    log("上传返回 status=%s" % st)
    if st != 200:
        raise SystemExit("上传 OSS 失败: %s %s" % (st, resp[:400]))
    return "oss://" + keyname


LOG_F = None


def log(msg):
    print(msg, flush=True)
    if LOG_F:
        LOG_F.write(msg + "\n")
        LOG_F.flush()


def post_json(url, key, payload, extra=None):
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    if extra:
        headers.update(extra)
    st, body = http(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    return json.loads(body)


def main():
    global LOG_F
    audio, out_dir = sys.argv[1], sys.argv[2]
    model = sys.argv[3] if len(sys.argv) > 3 else "paraformer-v2"
    os.makedirs(out_dir, exist_ok=True)
    LOG_F = open(os.path.join(out_dir, "asr.log"), "w", encoding="utf-8")
    key, base = load_key()
    log("model=%s base=%s file=%s" % (model, base, audio))

    oss_url = upload(key, model, audio)
    log("临时 URL: %s" % oss_url)

    submit_url = base + "/api/v1/services/audio/asr/transcription"
    payload = {
        "model": model,
        "input": {"file_urls": [oss_url]},
        "parameters": {
            "channel_id": [0],
            "language_hints": ["zh"],
            "timestamp_alignment_enabled": True,
            "disfluency_removal_enabled": False,
        },
    }
    r = post_json(submit_url, key, payload,
                  {"X-DashScope-Async": "enable", "X-DashScope-OssResourceResolve": "enable"})
    log("提交: %s" % json.dumps(r, ensure_ascii=False)[:300])
    task_id = r.get("output", {}).get("task_id")
    if not task_id:
        raise SystemExit("提交失败")

    t0 = time.time()
    while True:
        r = post_json(base + "/api/v1/tasks/" + task_id, key, None,
                      {"X-DashScope-OssResourceResolve": "enable"})
        status = r.get("output", {}).get("task_status")
        log("[poll %.0fs] %s" % (time.time() - t0, status))
        if status in ("SUCCEEDED", "FAILED", "UNKNOWN"):
            json.dump(r, open(os.path.join(out_dir, "task.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            if status != "SUCCEEDED":
                log(json.dumps(r, ensure_ascii=False)[:600])
                raise SystemExit("任务状态 " + status)
            for sub in r["output"]["results"]:
                if sub.get("subtask_status") != "SUCCEEDED":
                    log(json.dumps(sub, ensure_ascii=False)[:600])
                    raise SystemExit("子任务失败")
                st, body = http(sub["transcription_url"])
                trj = json.loads(body)
                out = os.path.join(out_dir, "transcription.json")
                json.dump(trj, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                t = trj["transcripts"][0]
                log("[done] 句数=%d 时长=%sms 字数=%d -> %s" % (
                    len(t.get("sentences", [])),
                    trj["properties"].get("original_duration_in_milliseconds"),
                    len(t.get("text", "")), out))
            return
        time.sleep(3)


main()
