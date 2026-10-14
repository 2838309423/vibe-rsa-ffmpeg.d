#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Blendkit（原 BlenderKit）公开搜索小工具 —— 纯只读：检索 + 缩略图落盘。

用法:
  python3 bk_search.py "storage box" --type model --max 5 --thumbs thumbs --json raw/storage.json
  python3 bk_search.py "bedroom interior" --type scene --max 4 --thumbs thumbs
说明:
  - 用的是官网公开搜索接口（无需账号），与插件内搜索同一数据源。
  - 排序: 免费优先 -> 质量评分高优先 -> 评分人数多优先。
"""
import argparse
import json
import os
import urllib.parse
import urllib.request

API = 'https://www.blenderkit.com/api/v1/search/'


def search(q, atype=None, page_size=24):
    params = {'query': q, 'page_size': page_size}
    if atype and atype != 'any':
        params['asset_type'] = atype
    url = API + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def slug(s, n=42):
    keep = ''.join(c if c.isalnum() else '-' for c in s.lower())
    parts = [x for x in keep.split('-') if x]
    return '-'.join(parts)[:n] or 'asset'


def img_ext(b):
    if b[:2] == b'\xff\xd8':
        return '.jpg'
    if b[:8] == b'\x89PNG\r\n\x1a\n':
        return '.png'
    if b[:4] == b'RIFF':
        return '.webp'
    return '.img'


def qavg(r):
    return (r.get('ratingsAverage') or {}).get('quality') or 0


def qn(r):
    return (r.get('ratingsCount') or {}).get('quality') or 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('query')
    ap.add_argument('--type', default='model',
                    help='model/scene/material/hdr/any，默认 model')
    ap.add_argument('--max', type=int, default=5)
    ap.add_argument('--thumbs', help='缩略图保存目录')
    ap.add_argument('--json', help='筛选结果的 JSON 落盘路径')
    a = ap.parse_args()

    d = search(a.query, a.type)
    rows = [r for r in d['results']
            if a.type == 'any' or r.get('assetType') == a.type]
    rows.sort(key=lambda r: (bool(r.get('isFree')), qavg(r), min(qn(r), 50)),
              reverse=True)
    rows = rows[:a.max]

    print('# 查询: %s  类型: %s  命中总量: %s' % (a.query, a.type, d.get('count')))
    print('idx\t免/Full\t评分avg/人数\t大小MB\t名称\t作者\t类目\tassetBaseId')
    for i, r in enumerate(rows, 1):
        author = r.get('author') or {}
        aname = ('%s %s' % (author.get('firstName', ''),
                            author.get('lastName', ''))).strip()
        mb = (r.get('filesSize') or 0) / 1048576.0
        print('%d\t%s\t%.1f/%d\t%.1f\t%s\t%s\t%s\t%s' % (
            i, r.get('accessLabel') or ('免费' if r.get('isFree') else 'Full'),
            qavg(r), qn(r), mb, r.get('displayName') or r.get('name'),
            aname, r.get('category'), r.get('assetBaseId')))

        if a.thumbs:
            os.makedirs(a.thumbs, exist_ok=True)
            tu = (r.get('thumbnailMiddleUrlNonsquared')
                  or r.get('thumbnailMiddleUrl')
                  or r.get('thumbnailSmallUrl'))
            if tu:
                try:
                    req = urllib.request.Request(tu, headers={'User-Agent': 'Mozilla/5.0'})
                    data = urllib.request.urlopen(req, timeout=30).read()
                    fn = '%s/%02d_%s%s' % (a.thumbs, i, slug(r.get('displayName') or r.get('name', '')),
                                           img_ext(data))
                    with open(fn, 'wb') as f:
                        f.write(data)
                    print('    thumb -> %s (%d KB)' % (fn, len(data) // 1024))
                except Exception as e:  # 缩略图失败不致命
                    print('    thumb FAIL: %s' % e)

    if a.json:
        os.makedirs(os.path.dirname(a.json) or '.', exist_ok=True)
        with open(a.json, 'w') as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print('# JSON -> %s' % a.json)


if __name__ == '__main__':
    main()
