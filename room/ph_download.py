#!/usr/bin/env python3
"""ph_download.py — Poly Haven 模型免登录下载器（glTF 2k 优先，1k 兜底）

用法:
  python3 ph_download.py id1 id2 ...            # 下载到 room/assets/ph/<id>/
  python3 ph_download.py --from-blueprint room/blueprint.json   # 按 blueprint 全量补齐素材
  python3 ph_download.py id1 --max-mb 60        # 单件载荷超 60MB 则跳过
  python3 ph_download.py id1 --list-only        # 只报体积不下载
特性: 已存在文件跳过（断点可重跑）；url + include(bin/贴图) 全部落位；
     单件总载荷 = gltf 本体 + 全部 include 的 content-length 预检。
"""
import json
import os
import sys
import urllib.request

API = "https://api.polyhaven.com/files/"
UA = {"User-Agent": "vibe-rsa-ffmpeg-room-line/0.1"}


def http(url, method="GET"):
    req = urllib.request.Request(url, headers=UA, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def head_len(url):
    req = urllib.request.Request(url, headers=UA, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers.get("Content-Length") or 0)


def pick_format(files):
    """选 gltf 档：2k 优先、1k 兜底；返回 (档名, gltf_url, {rel_path: url})"""
    gltf = files.get("gltf") or {}
    for res in ("2k", "1k"):
        if res in gltf:
            node = gltf[res]["gltf"]
            inc = {rel: v["url"] for rel, v in (node.get("include") or {}).items()}
            return res, node["url"], inc
    return None, None, None


def ids_from_blueprint(path):
    """从蓝图收集全部 kind=="ph" 的素材 id（去重，保持首次出现顺序）"""
    bp = json.load(open(path))
    items = list(bp.get("static") or [])
    for st in (bp.get("states") or {}).values():
        items += list(st or [])
    ids, seen = [], set()
    for e in items:
        if isinstance(e, dict) and e.get("kind") == "ph" and e.get("id"):
            if e["id"] not in seen:
                seen.add(e["id"])
                ids.append(e["id"])
    return ids


def payload_size(url, inc):
    total = head_len(url)
    for u in inc.values():
        total += head_len(u)
    return total


def download(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return 0  # 缓存命中
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    data = http(url)
    with open(dest, "wb") as f:
        f.write(data)
    return len(data)


def fetch_one(aid, root, max_mb, list_only):
    files = json.loads(http(API + aid).decode())
    res, url, inc = pick_format(files)
    if not url:
        return aid, 0, "无 gltf 档，跳过"
    mb = payload_size(url, inc) / 1e6
    if list_only:
        return aid, mb, "仅查体积"
    if mb > max_mb:
        return aid, mb, "超预算 %.0fMB，跳过" % max_mb
    base = os.path.join(root, aid)
    n = download(url, os.path.join(base, os.path.basename(url)))
    for rel, u in inc.items():
        n += download(u, os.path.join(base, rel))
    return aid, mb, "落盘 %.1fMB（%d 文件）" % (n / 1e6, 1 + len(inc))


def main():
    args = sys.argv[1:]
    max_mb, list_only = 80.0, False
    ids = []
    i = 0
    while i < len(args):
        if args[i] == "--max-mb":
            max_mb = float(args[i + 1]); i += 2
        elif args[i] == "--list-only":
            list_only = True; i += 1
        elif args[i] == "--dir":
            root = args[i + 1]; i += 2
        elif args[i] == "--from-blueprint":
            ids += ids_from_blueprint(args[i + 1]); i += 2
        else:
            ids.append(args[i]); i += 1
    root = locals().get("root", os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "ph"))
    print("%-34s %8s  %s" % ("asset", "载荷MB", "结果"))
    bad = 0
    for aid in ids:
        try:
            _, mb, msg = fetch_one(aid, root, max_mb, list_only)
            print("%-34s %8.1f  %s" % (aid, mb, msg))
        except Exception as e:  # noqa: BLE001
            bad += 1
            print("%-34s %8s  失败: %s" % (aid, "-", str(e)[:90]))
    print("PH_DOWNLOAD_DONE ids=%d fail=%d" % (len(ids), bad))


if __name__ == "__main__":
    main()
