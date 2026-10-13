#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把插图按目标画幅 cover-crop（等比放大到盖住画幅再居中裁），供 libx264 编码。

用法: python3 bin/prep_frames.py --project projects/<名>

为什么需要这一步：libx264 要求 yuv420p 的宽高均为偶数，而插图原始尺寸（如 1535x2732）是奇数；
直接用 -loop 1 喂原图会报 width not divisible by 2。顺带把画幅统一成配置里的 WxH。

产出: <out>/segfr/segNN.png（尺寸 = config.video.width x height）
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

FFMPEG = os.environ.get("FFMPEG") or "ffmpeg"


def cover_crop(src, dst, w, h):
    vf = "scale=%d:%d:flags=lanczos,crop=%d:%d,setsar=1" % (w, h, w, h)
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", src,
                    "-vf", vf, "-frames:v", "1", dst], check=True)


def main():
    args = config.parse_args(__doc__, extra=[
        (("--plan",), {"default": None, "help": "缺省 <out>/plan.json"}),
        (("--outdir",), {"default": None, "help": "缺省 <out>/segfr"}),
    ])
    cfg, _ = config.read_project(args.project)
    out = cfg["_out"]
    plan_path = args.plan or os.path.join(out, "plan.json")
    segfr = args.outdir or os.path.join(out, "segfr")
    w, h = int(cfg["video"]["width"]), int(cfg["video"]["height"])
    os.makedirs(segfr, exist_ok=True)

    import json
    plan = json.load(open(plan_path, encoding="utf-8"))
    for p in plan:
        src = os.path.join(cfg["_images"], p["image"])
        if not os.path.isfile(src):
            raise SystemExit("缺图: %s" % src)
        dst = os.path.join(segfr, "seg%02d.png" % p["idx"])
        cover_crop(src, dst, w, h)
        print("%-24s -> %s  %dx%d  %.0f KB" % (p["image"], os.path.basename(dst), w, h,
                                               os.path.getsize(dst) / 1024))
    print("共 %d 张 -> %s" % (len(plan), segfr))


main()
