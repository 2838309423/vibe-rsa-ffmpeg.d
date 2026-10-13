#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目配置读取（所有脚本共用）。

约定：一个视频项目 = `projects/<项目名>/` 一个目录，里面有

    project.json    配置（片段表、画幅、帧率、识别模型…）
    doc.txt         文稿（切分基准）
    images/         插图（顺序由 project.json 的 segments 决定）
    source.mp4      音频来源（已导出成片或纯音频都行）
    out/            产物（成片 / 对账图 / plan.json / 中间帧；不入仓）

project.json 相对路径一律相对该目录解析。命令行统一用 `--project <目录|project.json>` 指定，
缺省取当前工作目录。
"""
import argparse
import json
import os

DEFAULTS = {
    "video": {"width": 886, "height": 1920, "fps": 30, "crf": 20, "preset": "medium",
              "audio_bitrate": "192k"},
    "asr": {"model": "paraformer-v2", "language_hints": ["zh"],
            "timestamp_alignment_enabled": True},
    "doc": "doc.txt",
    "images_dir": "images",
    "out_dir": "out",
}


def _deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def parse_args(desc, extra=None):
    ap = argparse.ArgumentParser(description=desc)
    ap.add_argument("--project", default=".", help="项目目录或 project.json 路径（缺省当前目录）")
    for a in (extra or []):
        ap.add_argument(*a[0], **a[1])
    return ap.parse_args()


def read_project(arg="."):
    """返回 (cfg, project_dir)。cfg 已并入 DEFAULTS；相对路径已相对项目目录解析。"""
    path = arg
    if os.path.isdir(path):
        path = os.path.join(path, "project.json")
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise SystemExit("找不到 project.json: %s" % path)
    pdir = os.path.dirname(path)
    cfg = _deep_merge(DEFAULTS, json.load(open(path, encoding="utf-8")))

    def rel(p):
        return p if os.path.isabs(p) else os.path.join(pdir, p)

    cfg["_path"] = path
    cfg["_dir"] = pdir
    cfg["_doc"] = rel(cfg.get("doc", "doc.txt"))
    cfg["_images"] = rel(cfg.get("images_dir", "images"))
    cfg["_out"] = rel(cfg.get("out_dir", "out"))
    cfg["_source"] = rel(cfg["source"]) if cfg.get("source") else None
    if not cfg.get("segments"):
        raise SystemExit("%s 里没有 segments（片段表）" % path)
    return cfg, pdir
