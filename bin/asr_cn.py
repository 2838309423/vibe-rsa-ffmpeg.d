#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阿里云百炼：项目音频 → 临时 OSS(oss://) → Paraformer 非实时识别（带时间戳）→ <out>/asr/。

用法: python3 bin/asr_cn.py --project projects/<名> [--audio work/audio16k.wav]

流程（全走官方 RESTful，不依赖公网入站 —— 本机公网端口云侧拉不到）：
  0. 需要时先用 ffmpeg 从 project.source 抽 16k 单声道 wav
  1. GET  /api/v1/uploads?action=getPolicy&model=<model>   取上传凭证
  2. POST <upload_host>（multipart 表单）上传               得到 oss://...
  3. POST /api/v1/services/audio/asr/transcription          提交任务
     ⚠ 用 oss:// 临时 URL 时**必须**带 X-DashScope-OssResourceResolve: enable
  4. POST /api/v1/tasks/{task_id}                           轮询到 SUCCEEDED
  5. GET  transcription_url                                 下载结果（sentences/words 时间戳）

产出: <out>/audio16k.wav、<out>/asr/transcription.json、<out>/asr/asr.log
"""
import json
import mimetypes
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

KEY_FILE = os.environ.get("BAILIAN_KEY_FILE",
                          os.path.expanduser("~/.config/aliyun-bailian/api-key.txt"))
UPLOADS_URL = "https://dashscope.aliyuncs.com/api/v1/uploads"
FFMPEG = os.environ.get("FFMPEG") or "ffmpeg"
LOG_F = None


def log(msg):
    print(msg, flush=True)
    if LOG_F:
        LOG_F.write(msg + "\n")
        LOG_F.flush()


def load_key():
    key = host = None
    for line in open(KEY_FILE, encoding="utf-8"):
        s = line.strip()
        if s.startswith("sk-"):
            key = s
        if "maas.aliyuncs.com" in s:
            host = s
    if not key:
        raise SystemExit("key 文件里没找到 sk-...：%s" % KEY_FILE)
    wid = host.split(".")[0] if host else None
    base = ("https://%s.cn-beijing.maas.aliyuncs.com" % wid) if wid \
        else "https://dashscope.aliyuncs.com"
    return key, base


def http(url, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.status, r.read()


def get_policy(key, model):
    url = UPLOADS_URL + "?" + urllib.parse.urlencode({"action": "getPolicy", "model": model})
    st, body = http(url, headers={"Authorization": "Bearer " + key,
                                  "Content-Type": "application/json"})
    if st != 200:
        raise SystemExit("取上传凭证失败: %s" % body[:500])
    return json.loads(body)["data"]


def multipart(fields, file_field, file_path):
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
    keyname = "%s/%s" % (pol["upload_dir"], os.path.basename(file_path))
    fields = {
        "OSSAccessKeyId": pol["oss_access_key_id"], "Signature": pol["signature"],
        "policy": pol["policy"], "x-oss-object-acl": pol["x_oss_object_acl"],
        "x-oss-forbid-overwrite": pol["x_oss_forbid_overwrite"],
        "key": keyname, "success_action_status": "200",
    }
    body, ctype = multipart(fields, "file", file_path)
    st, resp = http(pol["upload_host"], data=body, headers={"Content-Type": ctype}, method="POST")
    if st != 200:
        raise SystemExit("上传 OSS 失败: %s %s" % (st, resp[:400]))
    return "oss://" + keyname


def post_json(url, key, payload, extra=None):
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    if extra:
        headers.update(extra)
    data = json.dumps(payload).encode() if payload is not None else b""
    st, body = http(url, data=data, headers=headers, method="POST")
    return json.loads(body)


def main():
    global LOG_F
    args = config.parse_args(__doc__, extra=[
        (("--audio",), {"default": None, "help": "已抽好的音频；缺省用 ffmpeg 从 source 抽"}),
    ])
    cfg, _ = config.read_project(args.project)
    out = cfg["_out"]
    asr_dir = os.path.join(out, "asr")
    os.makedirs(asr_dir, exist_ok=True)
    LOG_F = open(os.path.join(asr_dir, "asr.log"), "w", encoding="utf-8")

    audio = args.audio or os.path.join(out, "audio16k.wav")
    if not os.path.isfile(audio):
        if not cfg["_source"]:
            raise SystemExit("没给 --audio，project.json 里也没有 source")
        log("抽音频: %s -> %s" % (cfg["_source"], audio))
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i",
                        cfg["_source"], "-vn", "-ac", "1", "-ar", "16000",
                        "-c:a", "pcm_s16le", audio], check=True)

    asr = cfg["asr"]
    model = asr["model"]
    key, base = load_key()
    log("model=%s base=%s file=%s" % (model, base, audio))

    oss_url = upload(key, model, audio)
    log("临时 URL: %s" % oss_url)

    payload = {
        "model": model,
        "input": {"file_urls": [oss_url]},
        "parameters": {
            "channel_id": [0],
            "language_hints": asr.get("language_hints", ["zh"]),
            "timestamp_alignment_enabled": asr.get("timestamp_alignment_enabled", True),
            "disfluency_removal_enabled": asr.get("disfluency_removal_enabled", False),
        },
    }
    r = post_json(base + "/api/v1/services/audio/asr/transcription", key, payload,
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
            json.dump(r, open(os.path.join(asr_dir, "task.json"), "w", encoding="utf-8"),
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
                dst = os.path.join(asr_dir, "transcription.json")
                json.dump(trj, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                t = trj["transcripts"][0]
                log("[done] 句数=%d 时长=%sms 字数=%d -> %s" % (
                    len(t.get("sentences", [])),
                    trj["properties"].get("original_duration_in_milliseconds"),
                    len(t.get("text", "")), dst))
            return
        time.sleep(3)


main()
