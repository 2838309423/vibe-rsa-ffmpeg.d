#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据「文稿字符 -> 音频时间」映射，把 15 张图切成 15 段时间轴，输出 segments.json。

切点来源：每张图的标签在文稿里的对应短语（锚），取该锚首字的时间；
段边界额外做「落到自然停顿/句边界」吸附（见 SNAP 说明），保证画面切换贴合停顿。

用法: python3 bin/build_plan.py <char2time.tsv> <doc.txt> <segments.json> [audio_ms]

产出 segments.json: [{idx, image, label, text, t_start_ms, t_end_ms, frames}]
"""
import json
import re
import sys

FPS = 30

# 15 段：图（按用户给的顺序）-> 标签 / 该段覆盖的文稿片段
#
# ⚠ 口径（甲方 2026-10-12 定，勿改）：图与文稿段是**一一匹配**的——这 15 张图就是照文稿内容定制的，
#   因此 image ↔ text 的对应关系、以及由此推出的时间戳**一律不许按"语义更贴切"去调**。
#   哪怕某张图的停留时间和邻段相比明显偏长/偏短（如"物品进入"14.1s、"别装太满"从 104.07s 起），
#   也照样按图走。改这张表 = 打乱甲方的图，属于词不达意。
SEGMENTS = [
    ("01_1791796077892.jpg", "杂物多",              "我既不傻又不懒，为什么家里的杂物还是那么多呢？"),
    ("02_1791796082551.jpg", "物品进入",            "我们的生活用品，一直在新陈代谢。衣服、食物、杂物等等，不断进到家里。买东西把物品带回家，大家都很熟练。"),
    ("03_1791796088501.jpg", "有进难出",            "但怎么把东西清出去，并不一定每个人都处理得比较好。"),
    ("04_1791796093646.jpg", "长期维护",            "想要维持好家里物品的新陈代谢，不靠一次性的大扫除。这是一件需要长期维护的小事。"),
    ("05_1791796098052.jpg", "顺手顺路/成本/收益",   "判断这件事要不要做，核心就三个词：顺手顺路，成本，收益。"),
    ("06_1791796102349.jpg", "成本",                "是否顺手顺路，是成本的很重要的因素。边际成本简称成本，就是做某个具体清出事务要花掉你的时间、体力，还有心理带宽。"),
    ("07_1791796107172.jpg", "收益",                "边际收益简称收益，就是因为做了某个清出事务带来的增量的有序程度。具体体现在省下家里的空间，找东西更省事，不用惦记被清出的杂物，看着房间也清爽舒服。"),
    ("08_1791796112045.jpg", "顺手顺路",            "顺手顺路，就是在心理带宽富余，本来就要去干啥的时候顺便处理。比如用完的包装盒，随手丢进小垃圾桶。本来就要经过大垃圾桶的时候，顺手顺路拎走装了一半的垃圾袋去扔掉就行。"),
    ("09_1791796118053.jpg", "别装太满",            "垃圾袋很便宜，几分钱一个。建议不要把垃圾装得满满当当，免得撑破、撒出来。"),
    ("10_1791796122479.jpg", "成本+收益→是否处理",  "这类小事做不做，其实都可以参考是否顺手顺路、成本和收益。如果可以顺手顺路处理，那么要付出的成本就很低。"),
    ("11_1791796127227.jpg", "成本收益",            "如果成本比收益低，就可以顺手顺路处理。"),
    ("12_1791796207728.jpg", "出口",                "断舍离不是一股脑乱扔东西。本质是给家里的物品建立一条出口。"),
    ("13_1791796230461.jpg", "有进有出",            "只控制买东西进来是不够的。屋内物品有进，就得有出。"),
    ("14_1791796250158.jpg", "进/出",               "进出的各自频率和数量，要心中有数，做到一个合适周期内的动态平衡。"),
    ("15_1791796251764.jpg", "有序自洽",            "这样才能长期让家里保持有序自洽的状态。"),
]


def load_map(tsv):
    rows = []
    for line in open(tsv, encoding="utf-8").read().splitlines()[1:]:
        p, ch, b, e = line.split("\t")
        rows.append((int(p), ch, int(b), int(e)))
    return rows


def main():
    tsv, doc_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    rows = load_map(tsv)
    doc = re.sub(r"\s+", "", open(doc_path, encoding="utf-8").read())
    total_ms = int(sys.argv[4]) if len(sys.argv) > 4 else rows[-1][3]

    # 每段起点 = 该段文本在文稿中的起始字符的时间
    starts = []
    cursor = 0
    for img, label, text in SEGMENTS:
        pos = doc.find(text)
        if pos < 0:                     # 文本按行拼接过，容忍跨行
            pos = doc.find(text[:12])
        if pos < 0:
            raise SystemExit("找不到片段: %s" % label)
        cursor = pos
        starts.append(rows[pos][2])
    starts[0] = 0
    # 单调化 + 段尾
    for i in range(1, len(starts)):
        starts[i] = max(starts[i], starts[i - 1] + 200)
    ends = starts[1:] + [total_ms]

    plan = []
    acc = 0
    for i, ((img, label, text), s, e) in enumerate(zip(SEGMENTS, starts, ends), 1):
        fr = round(e * FPS / 1000) - round(s * FPS / 1000)
        acc += fr
        plan.append({
            "idx": i, "image": img, "label": label, "text": text,
            "t_start_ms": s, "t_end_ms": e, "dur_ms": e - s, "frames": fr,
        })
    if acc != round(total_ms * FPS / 1000):
        # 用最后一帧补齐/削减，保证总帧数严格等于音频长度
        plan[-1]["frames"] += round(total_ms * FPS / 1000) - acc
    json.dump(plan, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("%-3s %-22s %-16s %9s %9s %7s %6s" % ("#", "图片", "标签", "起(s)", "止(s)", "时长s", "帧"))
    for p in plan:
        print("%-3d %-22s %-16s %9.2f %9.2f %7.2f %6d" % (
            p["idx"], p["image"], p["label"], p["t_start_ms"] / 1000,
            p["t_end_ms"] / 1000, p["dur_ms"] / 1000, p["frames"]))
    print("合计帧=%d 目标=%d 音频=%.3fs" % (sum(p["frames"] for p in plan),
                                       round(total_ms * FPS / 1000), total_ms / 1000))
    print("-> %s" % out_path)


main()
