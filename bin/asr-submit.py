#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提交阿里云百炼 Paraformer 非实时识别任务（paraformer-v2 + 时间戳校准），轮询到成功并取回识别结果 JSON。

用法:
  python3 bin/asr-submit.py <audio_url> <out_dir>

环境/文件:
  key 文件 ~/.config/aliyun-bailian/api-key.txt（api_key: / sk-... / http api host: ws-xxx.cn-beijing.maas.aliyuncs.com）
产出:
  <out_dir>/task.json          提交/轮询原始响应
  <out_dir>/transcription.json 识别结果（含 sentences/words 时间戳）
"""
import json
import os
import sys
import time
import urllib.request

KEY_FILE = os.path.expanduser("~/.config/aliyun-bailian/api-key.txt")


def load_key():
    key = host = None
    for line in open(KEY_FILE, encoding="utf-8"):
        s = line.strip()
        if s.startswith("sk-"):
            key = s
        if "maas.aliyuncs.com" in s:
            host = s
    if not key or not host:
        raise SystemExit("key 文件里没找到 sk-... / maas host")
    wid = host.split(".")[0]
    return key, "https://%s.cn-beijing.maas.aliyuncs.com" % wid


def post(url, key, payload=None, extra_headers=None):
    data = json.dumps(payload).encode() if payload is not None else b""
    headers = {"Authorization": "Bearer " + key}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def main():
    audio_url, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    key, base = load_key()
    submit_url = base + "/api/v1/services/audio/asr/transcription"
    payload = {
        "model": "paraformer-v2",
        "input": {"file_urls": [audio_url]},
        "parameters": {
            "channel_id": [0],
            "language_hints": ["zh"],
            "timestamp_alignment_enabled": True,
            "disfluency_removal_enabled": False,
        },
    }
    print("[submit] %s" % submit_url)
    resp = post(submit_url, key, payload, {"X-DashScope-Async": "enable"})
    print("[submit] resp=%s" % json.dumps(resp, ensure_ascii=False)[:400])
    json.dump(resp, open(os.path.join(out_dir, "task.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    task_id = resp.get("output", {}).get("task_id")
    if not task_id:
        raise SystemExit("提交失败，无 task_id")

    query_url = base + "/api/v1/tasks/" + task_id
    t0 = time.time()
    while True:
        r = post(query_url, key)
        status = r.get("output", {}).get("task_status")
        print("[poll %.0fs] %s" % (time.time() - t0, status))
        if status in ("SUCCEEDED", "FAILED", "UNKNOWN"):
            json.dump(r, open(os.path.join(out_dir, "task.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            if status != "SUCCEEDED":
                print(json.dumps(r, ensure_ascii=False)[:800])
                raise SystemExit("任务状态 %s" % status)
            results = r["output"]["results"]
            for sub in results:
                if sub.get("subtask_status") != "SUCCEEDED":
                    print(json.dumps(sub, ensure_ascii=False)[:800])
                    raise SystemExit("子任务失败: %s" % sub.get("code"))
                turl = sub["transcription_url"]
                with urllib.request.urlopen(turl, timeout=60) as tr:
                    trj = json.loads(tr.read().decode())
                out = os.path.join(out_dir, "transcription.json")
                json.dump(trj, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                tr0 = trj["transcripts"][0]
                print("[done] 段数=%d 时长=%sms 文本=%d字 -> %s" % (
                    len(tr0.get("sentences", [])),
                    trj["properties"].get("original_duration_in_milliseconds"),
                    len(tr0.get("text", "")), out))
            return
        time.sleep(3)


main()
