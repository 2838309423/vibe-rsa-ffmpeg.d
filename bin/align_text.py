#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「豆包朗读用的文稿」与「阿里云 Paraformer 识别结果」做字符级对齐，
输出 文稿每个汉字 -> 音频时间(ms) 的映射，供后续切分 15 段图片时间轴使用。

用法: python3 bin/align_text.py --project projects/<名>

产出（都在 <out>/ 下）:
  align.char2time.tsv   文稿字符级：序号/字符/时间 ms（标点锚在相邻实字上）
  align.doc.txt         归一化后的文稿纯文本（无空白，保留标点）
  align.report.txt      对齐统计（未匹配块、相似度）
"""
import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402


def norm_asr_words(tr):
    """展开 ASR words -> [(char, begin_ms, end_ms)]，只保留汉字/字母/数字。"""
    out = []
    for ch in tr["transcripts"]:
        for s in ch.get("sentences", []):
            for w in s.get("words", []):
                t = w["text"].strip()
                t = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", t)
                for c in t:
                    out.append((c, w["begin_time"], w["end_time"]))
    return out


def norm_doc(text):
    """文稿 -> 字符序列（保留汉字/字母/数字；标点单独保留用于定位）。"""
    txt = re.sub(r"\s+", "", text)
    return txt


def main():
    args = config.parse_args(__doc__, extra=[
        (("--asr",), {"default": None, "help": "缺省 <out>/asr/transcription.json"}),
    ])
    cfg, _ = config.read_project(args.project)
    out = cfg["_out"]
    os.makedirs(out, exist_ok=True)
    doc_path = cfg["_doc"]
    asr_path = args.asr or os.path.join(out, "asr", "transcription.json")
    prefix = os.path.join(out, "align")
    doc_raw = open(doc_path, encoding="utf-8").read()
    doc = norm_doc(doc_raw)
    tr = json.load(open(asr_path, encoding="utf-8"))
    words = norm_asr_words(tr)
    asr_chars = [c for c, _, _ in words]
    a = "".join(asr_chars)
    b = "".join(c for c in doc if re.match(r"[\u4e00-\u9fffA-Za-z0-9]", c))

    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    # doc 实字索引 -> asr 词索引
    doc2asr = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                doc2asr[j1 + k] = i1 + k
    ratio = sm.ratio()

    # 把映射摊回「文稿原文（含标点）」
    doc_chars = list(doc)
    solid_idx = -1
    rows = []
    for pos, ch in enumerate(doc_chars):
        if re.match(r"[\u4e00-\u9fffA-Za-z0-9]", ch):
            solid_idx += 1
            ai = doc2asr.get(solid_idx)
            if ai is None:
                rows.append((pos, ch, None, None))
            else:
                rows.append((pos, ch, words[ai][1], words[ai][2]))
        else:
            rows.append((pos, ch, None, None))
    # 标点/缺失处用左右最近的实字时间补齐（线性插值）
    known = [i for i, r in enumerate(rows) if r[2] is not None]
    for i, r in enumerate(rows):
        if r[2] is None:
            left = max([k for k in known if k < i], default=None)
            right = min([k for k in known if k > i], default=None)
            if left is None and right is None:
                t = (0, 0)
            elif left is None:
                t = (rows[right][2], rows[right][3])
            elif right is None:
                t = (rows[left][2], rows[left][3])
            else:
                t = (rows[left][2], rows[right][3])
            rows[i] = (r[0], r[1], t[0], t[1])
    # 时间单调化（对齐噪声可能造成回退）
    last = 0
    fixed = []
    for pos, ch, b0, e0 in rows:
        b0 = max(b0, last)
        e0 = max(e0, b0)
        last = b0
        fixed.append((pos, ch, b0, e0))

    with open(prefix + ".char2time.tsv", "w", encoding="utf-8") as f:
        f.write("pos\tchar\tbegin_ms\tend_ms\n")
        for pos, ch, b0, e0 in fixed:
            f.write("%d\t%s\t%d\t%d\n" % (pos, ch, b0, e0))
    open(prefix + ".doc.txt", "w", encoding="utf-8").write(doc)

    matched = len(doc2asr)
    total = len(b)
    with open(prefix + ".report.txt", "w", encoding="utf-8") as f:
        f.write("ASR 实字数=%d 文稿实字数=%d 对齐上=%d (%.4f) 相似度=%.4f\n"
                % (len(a), total, matched, matched / max(total, 1), ratio))
        f.write("--- 差异块 ---\n")
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                f.write("%-8s asr[%d:%d]=%s | doc[%d:%d]=%s\n"
                        % (tag, i1, i2, a[i1:i2], j1, j2, b[j1:j2]))
    print("相似度=%.4f 对齐上=%d/%d" % (ratio, matched, total))
    print("-> %s.char2time.tsv / .doc.txt / .report.txt" % prefix)


main()
