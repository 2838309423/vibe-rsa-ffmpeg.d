#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成片机械验收（不需要人眼看片）：
  ① 容器/流参数（H.264 + AAC、画幅、帧率与配置一致）
  ② 总帧数 = plan 计划、PTS 严格单调、末帧+1帧 ≈ 时长
  ③ 每段中点帧与源图比对（缩略后逐像素 MAE，判定放没放对图、顺序对不对）
  ④ 成片音频 vs 源音频：时长一致 + 100ms 包络相关系数

用法: python3 bin/verify_video.py --project projects/<名> [--out <成片>]
末行输出 __SELFTEST__ <断言数> <失败数>（0 失败 = 绿）
"""
import json
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

FF = os.environ.get("FFMPEG") or "ffmpeg"
FP = os.environ.get("FFPROBE") or "ffprobe"
checks = [0, 0]


def ok(cond, msg):
    checks[0] += 1
    if not cond:
        checks[1] += 1
    print("%s %s" % ("PASS" if cond else "FAIL", msg))
    return cond


def probe(path, *entries):
    cmd = [FP, "-v", "error"]
    for e in entries:
        cmd += ["-show_entries", e]
    return json.loads(subprocess.run(cmd + ["-of", "json", path],
                                     capture_output=True, text=True).stdout)


def gray_at(path, t=None, size="32:69"):
    """取一帧的灰度原始数据（先缩放，便于跨编码比对）。t=None ⇒ 首帧。"""
    cmd = [FF, "-v", "error"]
    if t is not None:
        cmd += ["-ss", "%.3f" % t]
    cmd += ["-i", path, "-vf", "scale=" + size, "-frames:v", "1",
            "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    return list(subprocess.run(cmd, capture_output=True).stdout)


def mae(a, b):
    n = min(len(a), len(b))
    return sum(abs(a[i] - b[i]) for i in range(n)) / max(n, 1)


def envelope_pcm(path, sr=16000, win=1600):
    """返回 (采样列表, 100ms 窗 RMS 包络)。"""
    raw = subprocess.run([FF, "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr),
                          "-f", "s16le", "-"], capture_output=True).stdout
    x = [int.from_bytes(raw[i:i + 2], "little", signed=True) for i in range(0, len(raw) - 1, 2)]
    env = [math.sqrt(sum(t * t for t in x[i:i + win]) / win) for i in range(0, len(x) - win, win)]
    return x, env


def corr(a, b):
    m = min(len(a), len(b))
    a, b = a[:m], b[:m]
    ma, mb = sum(a) / m, sum(b) / m
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(m))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((x - mb) ** 2 for x in b))
    return cov / den if den else 0


def main():
    args = config.parse_args(__doc__, extra=[
        (("--out",), {"default": None, "help": "成片路径（缺省 <out>/final.mp4）"}),
        (("--plan",), {"default": None, "help": "缺省 <out>/plan.json"}),
        (("--segfr",), {"default": None, "help": "缺省 <out>/segfr"}),
    ])
    cfg, _ = config.read_project(args.project)
    out = cfg["_out"]
    video = args.out or os.path.join(out, "final.mp4")
    plan = json.load(open(args.plan or os.path.join(out, "plan.json"), encoding="utf-8"))
    segfr = args.segfr or os.path.join(out, "segfr")
    W, H = int(cfg["video"]["width"]), int(cfg["video"]["height"])
    fps = int(cfg["video"]["fps"])
    src = cfg["_source"]
    total_frames = sum(p["frames"] for p in plan)
    target_dur = plan[-1]["t_end_ms"] / 1000.0

    # ① 容器参数
    j = probe(video, "format=duration",
              "stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames")
    v = [s for s in j["streams"] if s["codec_type"] == "video"][0]
    a = [s for s in j["streams"] if s["codec_type"] == "audio"]
    dur = float(j["format"]["duration"])
    ok(v["codec_name"] == "h264" and int(v["width"]) == W and int(v["height"]) == H,
       "视频流 %s %sx%s（配置 %dx%d）" % (v["codec_name"], v["width"], v["height"], W, H))
    ok(v["r_frame_rate"] == "%d/1" % fps, "帧率 %s（配置 %d）" % (v["r_frame_rate"], fps))
    ok(bool(a) and a[0]["codec_name"] == "aac", "音频流 %s" % (a[0]["codec_name"] if a else "缺失"))
    ok(abs(dur - target_dur) < 0.05, "成片时长 %.3fs（目标 %.3fs）" % (dur, target_dur))
    ok(int(v["nb_frames"]) == total_frames, "总帧数 %s = 计划 %d" % (v["nb_frames"], total_frames))

    # ② PTS 单调
    raw = subprocess.run([FP, "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "frame=pts_time", "-of", "csv=p=0", video],
                         capture_output=True, text=True).stdout.split()
    ts = [float(x.rstrip(",")) for x in raw if x.strip().rstrip(",")]
    ok(all(ts[i] > ts[i - 1] for i in range(1, len(ts))) and len(ts) == total_frames,
       "PTS 严格单调 %d 帧（首 %.3f 末 %.3f）" % (len(ts), ts[0], ts[-1]))
    ok(abs(ts[-1] + 1.0 / fps - dur) < 0.1, "末帧 %.3fs + 1帧 ≈ 时长 %.3fs" % (ts[-1], dur))

    # ③ 每段中点帧 vs 源图
    base = {p["idx"]: gray_at(os.path.join(segfr, "seg%02d.png" % p["idx"])) for p in plan}
    bad = []
    for p in plan:
        mid = (p["t_start_ms"] + p["t_end_ms"]) / 2000.0
        f = gray_at(video, t=mid)
        best, besti = 1e9, None
        for q in plan:
            d = mae(f, base[q["idx"]])
            if d < best:
                best, besti = d, q["idx"]
        if besti != p["idx"]:
            bad.append((p["idx"], besti, best))
        print("  段%02d(%.2fs) 命中图%02d MAE=%.2f %s" % (
            p["idx"], mid, besti, best, "" if besti == p["idx"] else "<-- 不符"))
    ok(not bad, "%d 段中点帧全部命中对应图（错配 %d 处）" % (len(plan), len(bad)))

    # ④ 音频一致性
    if src and os.path.isfile(src):
        xs, es = envelope_pcm(src)
        xo, eo = envelope_pcm(video)
        ok(abs(len(xs) - len(xo)) / 16000.0 < 0.1,
           "音频采样数 源=%d 成片=%d（差 %.3fs）" % (len(xs), len(xo),
                                                abs(len(xs) - len(xo)) / 16000.0))
        ok(corr(es, eo) > 0.99, "音频包络相关系数 r=%.4f（源 vs 成片）" % corr(es, eo))
    else:
        print("SKIP 源文件不存在（%s），跳过音频一致性" % src)

    print("__SELFTEST__ %d %d" % (checks[0], checks[1]))
    sys.exit(1 if checks[1] else 0)


main()
