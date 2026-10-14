#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 raw/*.json 生成精选画册 md。只读 raw/ 与 thumbs/，只写画册文件。"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
OUT = os.path.join(HERE, '画册-精选素材-261014.md')

# (raw文件名, 小节标题, Blender内英文搜索词, 取第几个)
THEMES = [
    ('cardboard', '01 打包纸箱（断舍离第一镜头）', 'cardboard box', [1, 2, 3]),
    ('storage',   '02 收纳盒',                   'storage box',   [3, 4, 1]),
    ('basket',    '03 收纳筐 / 置物架',           'storage basket', [3, 4, 1]),
    ('clothes',   '04 衣物整理（叠好/挂起）',       'folded clothes', [1, 2, 5]),
    ('wardrobe',  '05 衣柜',                     'wardrobe',      [1, 2, 4]),
    ('books',     '06 书架与书',                  'bookshelf',     [1, 5, 2]),
    ('kitchen',   '07 厨房密封罐',                'kitchen jar',   [3, 5, 2]),
    ('shoe',      '08 鞋架',                     'shoe rack',     [1, 3, 2]),
    ('clutter',   '09 「乱」素材（整理前状态）',    'clothes pile',  [4, 5]),
    ('room',      '10 整屋场景（舞台用）',         'bedroom interior（类型选 Scene）', [1, 2, 3]),
]

EXTS = ('.jpg', '.png', '.webp', '.img')


def slug(s, n=42):
    keep = ''.join(c if c.isalnum() else '-' for c in s.lower())
    return '-'.join(x for x in keep.split('-') if x)[:n] or 'asset'


def thumb_path(name, idx):
    base = '%02d_%s' % (idx, slug(name))
    for e in EXTS:
        p = os.path.join(HERE, 'thumbs', base + e)
        if os.path.exists(p):
            return 'thumbs/' + base + e
    return None


def main():
    lines = [
        '# BlenderKit 精选画册 · 家居整理 / 断舍离主题（29 件）',
        '',
        '> 生成于 2026-10-14。数据源 = blendkit.com 公开搜索接口（与插件内搜索同源）。',
        '> **圈选方式：直接回复编号**（如「要 1、5、9」），我转成购物清单。',
        '> 徽标：**免费** = 免费档可下 ｜ **Full** = 需订阅 ｜ ⚠ = 文件 >100MB，加载慢慎选。',
        '> 「Blender 搜索词」列照抄进插件搜索框即可找到（同一数据源）。',
        '',
    ]
    n = 0
    for tag, title, q, picks in THEMES:
        rows = json.load(open(os.path.join(RAW, tag + '.json')))
        lines += ['## %s' % title, '', 'Blender 搜索词：`%s`' % q, '']
        for rank in picks:
            r = rows[rank - 1]
            n += 1
            name = r.get('displayName') or r.get('name')
            author = r.get('author') or {}
            aname = ('%s %s' % (author.get('firstName', ''),
                                author.get('lastName', ''))).strip()
            mb = (r.get('filesSize') or 0) / 1048576.0
            qa = (r.get('ratingsAverage') or {}).get('quality') or 0
            qcnt = (r.get('ratingsCount') or {}).get('quality') or 0
            free = bool(r.get('isFree'))
            badge = '**免费**' if free else '**Full**'
            heavy = ' ⚠' if mb > 100 else ''
            link = 'https://www.blenderkit.com/get-blenderkit/%s/' % r.get('id')
            tp = thumb_path(name, rank)
            lines.append('### #%02d %s —— %s%s' % (n, name, badge, heavy))
            meta = ['- 作者：%s ｜ 质量分 %.1f/10（%d 人评）｜ 文件 %.1f MB%s'
                    % (aname, qa, qcnt, mb, heavy)]
            meta.append('- 详情页：<%s>' % link)
            if tp:
                lines.append('![#%02d %s](%s)' % (n, name, tp))
            lines += meta + ['']
    lines.append('---')
    lines.append('')
    lines.append('*本画册由 `bk_search.py` + `build_gallery.py` 自动生成；'
                 '换主题重抓时两条命令即可复刻（见方案文档 §5）。*')
    with open(OUT, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print('items:', n, '->', OUT)


if __name__ == '__main__':
    main()
