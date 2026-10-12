#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 15 张 1535x2732 的图按目标画幅 cover-crop 成偶数尺寸（默认 886x1920），供 libx264 编码。

用法: python3 bin/prep_frames.py <segments.json> <images_dir> <out_dir> [W] [H]
图片可读性优先：先用 ffmpeg 缩放+居中裁剪（zscale 缺失时退回 scale+crop）。

产出: <out_dir>/seg01.png ... seg15.png （尺寸 W x H）
"""
import json
import os
import subprocess
import sys

FFMPEG = os.environ.get(
    "FFMPEG", "/home/longxia/toolchain/ffmpeg/ffmpeg-7.0.2-amd64-static/ffmpeg")


def cover_crop(src, dst, w, h):
    # 覆盖式：等比缩放到完全盖住画幅，再居中裁剪
    vf = ("scale=%d:%d:flags=lanczos,crop=%d:%d,setsar=1" % (w, h, w, h))
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", src,
           "-vf", vf, "-frames:v", "1", dst]
    subprocess.run(cmd, check=True)


def main():
    plan_path, img_dir, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    W = int(sys.argv[4]) if len(sys.argv) > 4 else 886
    H = int(sys.argv[5]) if len(sys.argv) > 5 else 1920
    plan = json.load(open(plan_path, encoding="utf-8"))
    os.makedirs(out_dir, exist_ok=True)
    for p in plan:
        src = os.path.join(img_dir, p["image"])
        dst = os.path.join(out_dir, "seg%02d.png" % p["idx"])
        cover_crop(src, dst, W, H)
        sz = os.path.getsize(dst)
        print("%-22s -> %s  %dx%d  %.0f KB" % (p["image"], os.path.basename(dst), W, H, sz / 1024))
    print("共 %d 张 -> %s" % (len(plan), out_dir))


main()
