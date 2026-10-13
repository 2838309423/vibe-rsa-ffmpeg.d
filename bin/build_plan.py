#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按项目配置把插图切成 N 段时间轴，输出 `out/plan.json`。

切点来源：每段在文稿里的对应短语（config 的 segments[].text）首字时间；段内不留空档、无重叠，
总帧数严格等于音频长度（末段吸收取整误差）。

用法: python3 bin/build_plan.py --project projects/<名> [--audio-ms 163840]

口径（甲方 2026-10-12 定，勿改）：图与文稿段是**一一匹配**的（图是照文稿内容定制的），
`segments` 里的 image ↔ text 对照不许按"语义更贴切"去调；时间戳只从该表**推导**，不得反向改动。
哪怕某张图停留明显偏长/偏短（如「物品进入」14.1s、「别装太满」从 104.07s 起），也照样按图走。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402


def load_map(tsv):
    rows = []
    for line in open(tsv, encoding="utf-8").read().splitlines()[1:]:
        p, ch, b, e = line.split("\t")
        rows.append((int(p), ch, int(b), int(e)))
    return rows


def main():
    args = config.parse_args(__doc__, extra=[
        (("--char2time",), {"default": None, "help": "字符时间表（缺省 <out>/align.char2time.tsv）"}),
        (("--audio-ms",), {"type": int, "default": None, "help": "音频总长 ms（缺省取字符表末值）"}),
    ])
    cfg, _ = config.read_project(args.project)
    out = cfg["_out"]
    os.makedirs(out, exist_ok=True)
    tsv = args.char2time or os.path.join(out, "align.char2time.tsv")
    fps = int(cfg["video"]["fps"])

    rows = load_map(tsv)
    doc = re.sub(r"\s+", "", open(cfg["_doc"], encoding="utf-8").read())
    total_ms = args.audio_ms or rows[-1][3]
    segs = cfg["segments"]

    # 每段起点 = 该段文本在文稿中的起始字符的时间
    starts = []
    for s in segs:
        text = s["text"]
        pos = doc.find(text)
        if pos < 0:                     # 文稿按行拼接过，容忍跨行
            pos = doc.find(text[:12])
        if pos < 0:
            raise SystemExit("文稿里找不到该段文字: %s / %s" % (s.get("label"), text[:20]))
        starts.append(rows[pos][2])
    starts[0] = 0
    for i in range(1, len(starts)):     # 单调化
        starts[i] = max(starts[i], starts[i - 1] + 200)
    ends = starts[1:] + [total_ms]

    plan, acc = [], 0
    for i, (s, st, en) in enumerate(zip(segs, starts, ends), 1):
        fr = round(en * fps / 1000) - round(st * fps / 1000)
        acc += fr
        plan.append({
            "idx": i, "image": s["image"], "label": s.get("label", ""), "text": s["text"],
            "t_start_ms": st, "t_end_ms": en, "dur_ms": en - st, "frames": fr,
        })
    want = round(total_ms * fps / 1000)
    if acc != want:                     # 末段补齐/削减，保证总帧数严格等于音频长度
        plan[-1]["frames"] += want - acc
    json.dump(plan, open(os.path.join(out, "plan.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print("%-3s %-24s %-16s %9s %9s %8s %7s" % ("#", "图片", "标签", "起(s)", "止(s)", "时长s", "帧"))
    for p in plan:
        print("%-3d %-24s %-16s %9.2f %9.2f %8.2f %7d" % (
            p["idx"], p["image"], p["label"], p["t_start_ms"] / 1000,
            p["t_end_ms"] / 1000, p["dur_ms"] / 1000, p["frames"]))
    print("合计帧=%d 目标=%d 音频=%.3fs fps=%d" % (
        sum(p["frames"] for p in plan), want, total_ms / 1000, fps))

    covered = sum(len(re.sub(r"\s+", "", s["text"])) for s in segs)
    if covered != len(doc):
        print("⚠ 片段表覆盖 %d 字 ≠ 文稿 %d 字 —— 有 %d 字没被任何一段覆盖（核对 segments[].text）"
              % (covered, len(doc), len(doc) - covered))
    print("-> %s" % os.path.join(out, "plan.json"))


main()
