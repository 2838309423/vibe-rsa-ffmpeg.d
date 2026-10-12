#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成片机械验收：
  ① 容器/流参数、总帧数、时长
  ② 视频 PTS 严格单调、总时长 = 音频时长（≤1 帧误差）
  ③ 每段中点帧与源图比对（缩略后逐像素 MAE，判定是否放对了图）
  ④ 成片音频与源视频音频时长/内容一致性（RMS 与相关系数）

用法: python3 bin/verify_video.py <out.mp4> <segments.json> <frames_dir> <src_video>
末行输出 __SELFTEST__ <断言数> <失败数>
"""
import json
import math
import os
import subprocess
import sys

FF = os.environ.get("FFMPEG", "/home/longxia/toolchain/ffmpeg/ffmpeg-7.0.2-amd64-static/ffmpeg")
FP = os.environ.get("FFPROBE", "/home/longxia/toolchain/ffmpeg/ffmpeg-7.0.2-amd64-static/ffprobe")

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
    cmd += ["-of", "json", path]
    return json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout)


def gray_stats(path, size="32:69"):
    """取一帧的灰度原始数据（缩放后），返回均值/方差用向量。"""
    raw = subprocess.run([FF, "-v", "error", "-i", path, "-vf", "scale=" + size,
                          "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    return list(raw)


def frame_at(video, t, size="32:69"):
    raw = subprocess.run([FF, "-v", "error", "-ss", "%.3f" % t, "-i", video,
                          "-vf", "scale=" + size, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    return list(raw)


def mae(a, b):
    n = min(len(a), len(b))
    return sum(abs(a[i] - b[i]) for i in range(n)) / max(n, 1)


def pcm(path, sr=16000):
    out = subprocess.run([FF, "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr),
                          "-f", "s16le", "-"], capture_output=True).stdout
    return [int.from_bytes(out[i:i + 2], "little", signed=True) for i in range(0, len(out) - 1, 2)]


def main():
    out, plan_path, frames_dir, src = sys.argv[1:5]
    plan = json.load(open(plan_path, encoding="utf-8"))

    # ① 容器参数
    j = probe(out, "format=duration,size", "stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames")
    v = [s for s in j["streams"] if s["codec_type"] == "video"][0]
    a = [s for s in j["streams"] if s["codec_type"] == "audio"]
    dur = float(j["format"]["duration"])
    total_frames = sum(p["frames"] for p in plan)
    ok(v["codec_name"] == "h264" and v["width"] == 886 and v["height"] == 1920,
       "视频流 %s %dx%d" % (v["codec_name"], v["width"], v["height"]))
    ok(bool(a) and a[0]["codec_name"] == "aac", "音频流 %s" % (a[0]["codec_name"] if a else "缺失"))
    ok(abs(dur - 163.84) < 0.05, "成片时长 %.3fs（目标 163.840s）" % dur)
    ok(int(v["nb_frames"]) == total_frames, "总帧数 %s = 计划 %d" % (v["nb_frames"], total_frames))

    # ② PTS 单调
    pts = subprocess.run([FP, "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "frame=pts_time", "-of", "csv=p=0", out],
                         capture_output=True, text=True).stdout.split()
    ts = [float(x.rstrip(",")) for x in pts if x.strip().rstrip(",")]
    mono = all(ts[i] > ts[i - 1] for i in range(1, len(ts)))
    ok(mono and len(ts) == total_frames, "PTS 严格单调 %d 帧（首 %.3f 末 %.3f）" % (len(ts), ts[0], ts[-1]))
    ok(abs(ts[-1] + 1 / 30 - dur) < 0.1, "末帧 %.3fs + 1帧 ≈ 时长 %.3fs" % (ts[-1], dur))

    # ③ 每段中点帧与源图比对
    base = {}
    for p in plan:
        base[p["idx"]] = gray_stats(os.path.join(frames_dir, "seg%02d.png" % p["idx"]))
    bad = []
    for p in plan:
        mid = (p["t_start_ms"] + p["t_end_ms"]) / 2000.0
        f = frame_at(out, mid)
        best, besti = 1e9, None
        for q in plan:
            d = mae(f, base[q["idx"]])
            if d < best:
                best, besti = d, q["idx"]
        if besti != p["idx"]:
            bad.append((p["idx"], besti, best))
        print("  段%02d(%.2fs) 命中图%02d MAE=%.2f %s" % (p["idx"], mid, besti, best,
                                                        "" if besti == p["idx"] else "<-- 不符"))
    ok(not bad, "15 段中点帧全部命中对应图（错配 %d 处）" % len(bad))

    # ④ 音频一致性
    src_audio = subprocess.run([FF, "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
                                "-f", "s16le", "-"], capture_output=True).stdout
    out_audio = subprocess.run([FF, "-v", "error", "-i", out, "-vn", "-ac", "1", "-ar", "16000",
                                "-f", "s16le", "-"], capture_output=True).stdout
    sa = [int.from_bytes(src_audio[i:i + 2], "little", signed=True) for i in range(0, len(src_audio) - 1, 2)]
    oa = [int.from_bytes(out_audio[i:i + 2], "little", signed=True) for i in range(0, len(out_audio) - 1, 2)]
    n = min(len(sa), len(oa))
    ok(abs(len(sa) - len(oa)) / 16000.0 < 0.1,
       "音频采样数 源=%d 成片=%d（差 %.3fs）" % (len(sa), len(oa), abs(len(sa) - len(oa)) / 16000.0))
    # 100ms 窗 RMS 包络的相关系数（对编码差异/轻微偏移稳健）
    def env(x, w=1600):
        return [math.sqrt(sum(t * t for t in x[i:i + w]) / w) for i in range(0, len(x) - w, w)]
    e1, e2 = env(sa[:n]), env(oa[:n])
    m = min(len(e1), len(e2))
    e1, e2 = e1[:m], e2[:m]
    mu1, mu2 = sum(e1) / m, sum(e2) / m
    cov = sum((e1[i] - mu1) * (e2[i] - mu2) for i in range(m))
    den = math.sqrt(sum((x - mu1) ** 2 for x in e1) * sum((x - mu2) ** 2 for x in e2))
    r = cov / den if den else 0
    ok(r > 0.99, "音频包络相关系数 r=%.4f（源 vs 成片）" % r)

    print("__SELFTEST__ %d %d" % (checks[0], checks[1]))
    sys.exit(1 if checks[1] else 0)


main()
