#!/usr/bin/env python3
"""build_scene.py — 断舍离房间建场脚本（blender -b 内运行）

用法（在 blender 里跑，-- 后传参）:
  blender -b --factory-startup -P room/build_scene.py -- \
      --blueprint room/blueprint.json --state A --light day \
      --camera wide --samples 24 --res 1280 720 \
      --out room/out/previews/A_day.png [--save-blend room/out/A.blend]

职责:
  1) 读 blueprint.json：房间壳（墙地顶/窗/门）+ 程序化家具 + 两态道具落位
  2) Poly Haven 素材导入规矩：按资产名过滤杂件 → 归一化(落地面/中心) → 空父级摆位
  3) 光位预设(day/evening) + 机位库 + Cycles 渲染 CLI
审美参数（配色/材质）固化在脚本 STYLE 区，改动只动这里或 blueprint。
"""
import argparse
import glob
import json
import math
import os
import random
import sys

import bpy
import mathutils

# ---------------- STYLE（风格卡：断舍离·治愈系·低饱和） ----------------
STYLE = {
    "wall": ((0.87, 0.85, 0.80), 0.85),
    "wall_accent": ((0.55, 0.62, 0.52), 0.85),   # 床头背景墙 鼠尾草绿
    "ceiling": ((0.93, 0.92, 0.90), 0.9),
    "floor_wood": ((0.52, 0.36, 0.22), 0.38),
    "frame_white": ((0.92, 0.92, 0.90), 0.45),
    "door_wood": ((0.55, 0.42, 0.30), 0.5),
    "bed_frame": ((0.38, 0.27, 0.18), 0.55),
    "mattress": ((0.87, 0.86, 0.83), 0.8),
    "blanket": ((0.45, 0.52, 0.62), 0.85),       # 灰蓝毯子（与白床品分层）
    "pillow": ((0.93, 0.92, 0.88), 0.85),
    "wardrobe": ((0.62, 0.48, 0.33), 0.5),       # 橡木色（与墙分离）
    "rug": ((0.78, 0.72, 0.62), 0.95),
    "lamp_pole": ((0.25, 0.25, 0.26), 0.4),
    "lamp_shade": ((0.90, 0.85, 0.75), 0.7),
}
CLOTHES_PALETTE = [(0.65, 0.30, 0.25), (0.35, 0.45, 0.60), (0.80, 0.78, 0.72),
                   (0.45, 0.50, 0.42), (0.70, 0.60, 0.35)]
BOOK_PALETTE = [(0.72, 0.35, 0.25), (0.30, 0.42, 0.55), (0.75, 0.70, 0.55),
                (0.40, 0.52, 0.40), (0.60, 0.55, 0.60), (0.25, 0.25, 0.28)]

ASSET_DIR = os.path.dirname(os.path.abspath(__file__))
LAMPS = {}   # 灯光注册表：floor_lamp_bulb / sun / window_fill / ceil_*


# ---------------- 基础工具 ----------------
def M(name, color, rough=0.6, metal=0.0):
    """取/建 principled 材质"""
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    return mat


def _active(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def box(name, dims, loc, rot=(0, 0, 0), mat=None, bevel=0.0):
    """dims=xyz 尺寸(米)，loc=中心，rot=欧拉弧度"""
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.scale = (dims[0], dims[1], dims[2])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        mod = o.modifiers.new("bev", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        bpy.ops.object.modifier_apply(modifier="bev")
    if mat:
        o.data.materials.append(mat)
    return o


def cyl(name, r, depth, loc, rot=(0, 0, 0), mat=None, v=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=v, radius=r, depth=depth, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    if mat:
        o.data.materials.append(mat)
    return o


def ground_and_center(objs):
    """世界包围盒：xy 归中心、z 最低点归 0。返回 (cx, cy, dz, minz)"""
    pts = [o.matrix_world @ mathutils.Vector(c) for o in objs for c in o.bound_box]
    if not pts:
        return 0, 0, 0, 0
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    for o in objs:
        if o.parent is None:
            o.location.x -= cx
            o.location.y -= cy
            o.location.z -= lo[2]
    return cx, cy, hi[2] - lo[2], lo[2]


# ---------------- Poly Haven 导入（杂件过滤+归一化+摆位） ----------------
def import_ph(aid, assets_root, tag):
    pat = os.path.join(ASSET_DIR, assets_root, aid, "*.gltf")
    gltfs = sorted(glob.glob(pat))
    if not gltfs:
        raise FileNotFoundError("缺素材: " + pat)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=gltfs[0])
    new = [o for o in bpy.data.objects if o not in before]
    stem = aid.split("_")[0].split("-")[0].lower()
    meshes = [o for o in new if o.type == "MESH"]
    keep = [o for o in meshes if stem in o.name.lower()]
    if not keep:
        keep = meshes  # 兜底：全保留
    for o in new:
        if o.type == "MESH" and o not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    tops = [o for o in keep if o.parent is None or o.parent not in keep]
    ground_and_center(tops)
    empty = bpy.data.objects.new("P_%s_%s" % (aid, tag), None)
    bpy.context.collection.objects.link(empty)
    for o in tops:
        o.parent = empty
    return empty


def place(entry, tag, assets_root, idx):
    kind = entry["kind"]
    loc = entry["loc"]
    if kind == "ph":
        root = import_ph(entry["id"], assets_root, "%s%d" % (tag, idx))
    else:
        fn = PROCS[entry["id"]]
        root = fn(entry, tag, idx)  # 程序化道具返回空父级
    root.rotation_euler = (math.radians(entry.get("tilt", [0, 0])[0]),
                           math.radians(entry.get("tilt", [0, 0])[1]),
                           math.radians(entry.get("rot", 0)))
    s = entry.get("s", 1.0)
    root.scale = (s, s, s)
    root.location = (loc[0], loc[1], entry.get("z", 0.0))
    return root


# ---------------- 程序化家具/道具 ----------------
def p_bed(e, tag, idx):
    w, l = e.get("w", 1.5), e.get("l", 2.0)
    x, y = e["loc"]
    box("%s_frame" % tag, (w, l, 0.25), (x, y, 0.125), mat=M("bed_frame", *STYLE["bed_frame"]))
    box("%s_mattress" % tag, (w - 0.1, l - 0.25, 0.22), (x, y - 0.1, 0.36), mat=M("mattress", *STYLE["mattress"]), bevel=0.05)
    box("%s_blanket" % tag, (w + 0.06, l * 0.55, 0.1), (x, y - l * 0.2, 0.50), mat=M("blanket", *STYLE["blanket"]), bevel=0.06)
    for sx in (-1, 1):
        box("%s_pillow%d" % (tag, sx), (w * 0.36, 0.38, 0.13), (x + sx * w * 0.22, y + l * 0.32, 0.55),
            rot=(0, 0, math.radians(sx * 7)), mat=M("pillow", *STYLE["pillow"]), bevel=0.07)
    # 床头板贴 accent 墙
    box("%s_headboard" % tag, (w + 0.1, 0.08, 0.9), (x, y + l / 2 + 0.05, 0.75), mat=M("bed_frame", *STYLE["bed_frame"]))
    e = bpy.data.objects.new("%s_root" % tag, None)
    bpy.context.collection.objects.link(e)
    return e


def p_wardrobe(e, tag, idx):
    w, d, h = e.get("w", 1.7), e.get("d", 0.62), e.get("h", 2.15)
    x, y = e["loc"]
    m = M("wardrobe", *STYLE["wardrobe"])
    box("%s_body" % tag, (w, d, h), (x, y, h / 2), mat=m)
    for sx in (-1, 1):
        box("%s_door%d" % (tag, sx), (w / 2 - 0.03, 0.025, h - 0.12), (x + sx * w / 4, y - d / 2 - 0.012, h / 2),
            mat=m, bevel=0.008)
        cyl("%s_handle%d" % (tag, sx), 0.012, 0.28, (x + sx * 0.09, y - d / 2 - 0.05, h / 2), mat=M("lamp_pole", *STYLE["lamp_pole"]))
    e2 = bpy.data.objects.new("%s_root" % tag, None)
    bpy.context.collection.objects.link(e2)
    return e2


def p_rug(e, tag, idx):
    x, y = e["loc"]
    cyl("%s_rug" % tag, e.get("r", 1.0), 0.018, (x, y, 0.009), v=64, mat=M("rug", *STYLE["rug"]))
    e2 = bpy.data.objects.new("%s_root" % tag, None)
    bpy.context.collection.objects.link(e2)
    return e2


def p_floor_lamp(e, tag, idx):
    x, y = e["loc"]
    cyl("%s_base" % tag, 0.16, 0.025, (x, y, 0.012), mat=M("lamp_pole", *STYLE["lamp_pole"]))
    cyl("%s_pole" % tag, 0.015, 1.3, (x, y, 0.67), mat=M("lamp_pole", *STYLE["lamp_pole"]))
    bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=0.19, radius2=0.13, depth=0.26, location=(x, y, 1.42))
    shade = bpy.context.object
    shade.name = "%s_shade" % tag
    shade.data.materials.append(M("lamp_shade", *STYLE["lamp_shade"]))
    li = bpy.data.lights.new("%s_bulb" % tag, "POINT")
    li.energy = 0
    li.shadow_soft_size = 0.09
    li.color = (1.0, 0.75, 0.5)
    lo = bpy.data.objects.new("%s_bulb" % tag, li)
    lo.location = (x, y, 1.33)
    bpy.context.collection.objects.link(lo)
    LAMPS["floor_lamp_bulb"] = li
    e2 = bpy.data.objects.new("%s_root" % tag, None)
    bpy.context.collection.objects.link(e2)
    return e2


def p_clothes_pile(e, tag, idx):
    rng = random.Random(e.get("seed", 1))
    n = e.get("n", 4)
    for i in range(n):
        c = CLOTHES_PALETTE[rng.randrange(len(CLOTHES_PALETTE))]
        box("%s_c%d" % (tag, i),
            (rng.uniform(0.28, 0.42), rng.uniform(0.24, 0.36), rng.uniform(0.05, 0.09)),
            (rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08), 0.04 + i * 0.055),
            rot=(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rng.uniform(0, 6.28)),
            mat=M("cloth_%d" % (i % len(CLOTHES_PALETTE)), c, 0.9), bevel=0.03)
    e2 = bpy.data.objects.new("%s_root" % tag, None)
    bpy.context.collection.objects.link(e2)
    return e2


def p_books_scatter(e, tag, idx):
    rng = random.Random(e.get("seed", 1))
    n = e.get("n", 5)
    z = 0.015
    for i in range(n):
        c = BOOK_PALETTE[rng.randrange(len(BOOK_PALETTE))]
        box("%s_b%d" % (tag, i),
            (rng.uniform(0.16, 0.24), rng.uniform(0.22, 0.30), 0.03),
            (rng.uniform(-0.35, 0.35), rng.uniform(-0.3, 0.3), z),
            rot=(0, 0, rng.uniform(0, 6.28)),
            mat=M("book_%d" % (i % len(BOOK_PALETTE)), c, 0.6))
        if i % 3 == 2:
            z += 0.032  # 偶尔叠一本
    e2 = bpy.data.objects.new("%s_root" % tag, None)
    bpy.context.collection.objects.link(e2)
    return e2


PROCS = {"bed": p_bed, "wardrobe": p_wardrobe, "rug": p_rug,
         "floor_lamp": p_floor_lamp, "clothes_pile": p_clothes_pile, "books_scatter": p_books_scatter}


# ---------------- 房间壳 ----------------
def build_shell(bp):
    R = bp["room"]
    w, d, h, t = R["w"], R["d"], R["h"], R["wall_t"]
    floor = M("floor_wood", *STYLE["floor_wood"])
    wall = M("wall", *STYLE["wall"])
    acc = M("wall_accent", *STYLE["wall_accent"])
    ceil = M("ceiling", *STYLE["ceiling"])
    white = M("frame_white", *STYLE["frame_white"])
    wood = M("door_wood", *STYLE["door_wood"])
    box("floor", (w + 2 * t, d + 2 * t, 0.1), (0, 0, -0.05), mat=floor)
    box("ceiling", (w + 2 * t, d + 2 * t, 0.1), (0, 0, h + 0.05), mat=ceil)
    # N 墙（床头 accent 绿）+ W 墙（暖白）
    box("wall_N", (w + 2 * t, t, h), (0, d / 2 + t / 2, h / 2), mat=acc)
    box("wall_W", (t, d, h), (-w / 2 - t / 2, 0, h / 2), mat=wall)
    # S 墙开窗
    win = R["window"]
    x0, x1 = -w / 2, w / 2
    wa, wb = win["cx"] - win["w"] / 2, win["cx"] + win["w"] / 2
    yc = -(d / 2 + t / 2)
    box("wall_S_L", (wa - x0, t, h), ((x0 + wa) / 2, yc, h / 2), mat=wall)
    box("wall_S_R", (x1 - wb, t, h), ((wb + x1) / 2, yc, h / 2), mat=wall)
    box("wall_S_B", (win["w"], t, win["z0"]), (win["cx"], yc, win["z0"] / 2), mat=wall)
    box("wall_S_T", (win["w"], t, h - win["z1"]), (win["cx"], yc, (h + win["z1"]) / 2), mat=wall)
    # 窗框 + 中梃 + 窗台
    fy = -(d / 2)
    for zz in (win["z0"], win["z1"]):
        box("frame_h%.0f" % (zz * 10), (win["w"] + 0.1, 0.07, 0.06), (win["cx"], fy, zz), mat=white)
    for xx in (wa, wb, win["cx"]):
        box("frame_v%d" % int(xx * 100), (0.06, 0.07, win["z1"] - win["z0"]), (xx, fy, (win["z0"] + win["z1"]) / 2), mat=white)
    box("sill", (win["w"] + 0.16, 0.16, 0.03), (win["cx"], fy + 0.03, win["z0"] - 0.015), mat=white)
    # E 墙开门洞
    dr = R["door"]
    y0, y1 = -d / 2, d / 2
    da, db = dr["cy"] - dr["w"] / 2, dr["cy"] + dr["w"] / 2
    xc = w / 2 + t / 2
    box("wall_E_S", (t, da - y0, h), (xc, (y0 + da) / 2, h / 2), mat=wall)
    box("wall_E_N", (t, y1 - db, h), (xc, (db + y1) / 2, h / 2), mat=wall)
    box("wall_E_T", (t, dr["w"], h - dr["z1"]), (xc, dr["cy"], (h + dr["z1"]) / 2), mat=wall)
    box("door_leaf", (0.05, dr["w"] - 0.04, dr["z1"] - 0.02), (xc, dr["cy"], (dr["z1"]) / 2), mat=wood)
    cyl("door_knob", 0.03, 0.03, (w / 2 - 0.05, dr["cy"] + dr["w"] / 2 - 0.09, 1.02), rot=(0, math.radians(90), 0),
        mat=M("lamp_pole", *STYLE["lamp_pole"]))


# ---------------- 灯光/世界/相机 ----------------
def build_lights():
    sun = bpy.data.lights.new("sun", "SUN")
    sun.angle = 0.03
    so = bpy.data.objects.new("sun", sun)
    bpy.context.collection.objects.link(so)
    LAMPS["sun"] = sun
    LAMPS["sun_obj"] = so
    fill = bpy.data.lights.new("window_fill", "AREA")
    fill.size = 1.5
    fo = bpy.data.objects.new("window_fill", fill)
    fo.location = (0.9, -1.75, 1.55)
    fo.rotation_euler = (math.radians(90), 0, 0)  # 朝 +y 屋内
    bpy.context.collection.objects.link(fo)
    LAMPS["window_fill"] = fill
    for i, cx in enumerate((-0.7, 0.7)):
        cli = bpy.data.lights.new("ceil_%d" % i, "AREA")
        cli.size = 1.6
        cli.color = (1.0, 0.82, 0.62)
        co = bpy.data.objects.new("ceil_%d" % i, cli)
        co.location = (cx, 0, 2.6)
        bpy.context.collection.objects.link(co)
        LAMPS["ceil_%d" % i] = cli


def apply_lighting(preset):
    sun = LAMPS["sun"]
    LAMPS["sun_obj"].rotation_euler = tuple(math.radians(a) for a in preset["sun_rot"])
    sun.energy = preset["sun_energy"]
    LAMPS["window_fill"].energy = preset["window_fill"]
    LAMPS["window_fill"].color = preset.get("window_fill_color", (0.85, 0.9, 1.0))
    if "floor_lamp_bulb" in LAMPS:
        LAMPS["floor_lamp_bulb"].energy = preset["lamp_energy"]
    for k in ("ceil_0", "ceil_1"):
        LAMPS[k].energy = preset["ceil_energy"]
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*preset["world_color"], 1.0)
    bg.inputs[1].default_value = preset["world_strength"]


def add_camera(cam_cfg):
    cam = bpy.data.cameras.new("cam")
    cam.lens = cam_cfg.get("lens", 24)
    cam.clip_start = 0.03
    co = bpy.data.objects.new("cam", cam)
    co.location = cam_cfg["loc"]
    d = mathutils.Vector(cam_cfg["look_at"]) - mathutils.Vector(cam_cfg["loc"])
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.collection.objects.link(co)
    bpy.context.scene.camera = co


# ---------------- 主流程 ----------------
def build(bp, state, light, camera):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.images):
        for x in list(blk):
            if x.users == 0:
                blk.remove(x)
    build_shell(bp)
    build_lights()
    for i, e in enumerate(bp.get("static", [])):
        place(e, "S%d_" % i, bp["assets_root"], i)
    for i, e in enumerate(bp["states"][state]):
        place(e, "%s%d_" % (state, i), bp["assets_root"], i)
    apply_lighting(bp["lighting"][light])
    add_camera(bp["cameras"][camera])
    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    scn.cycles.device = "CPU"
    scn.cycles.use_denoising = True
    scn.cycles.sample_clamp_indirect = 8.0
    scn.view_settings.view_transform = "AgX"
    scn.view_settings.look = "AgX - Medium High Contrast"
    return scn


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--blueprint", required=True)
    ap.add_argument("--state", default="A", choices=["A", "B"])
    ap.add_argument("--light", default="day", choices=["day", "evening"])
    ap.add_argument("--camera", default="wide")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--res", nargs=2, type=int, default=[1280, 720])
    ap.add_argument("--out", required=True)
    ap.add_argument("--save-blend", default=None)
    args = ap.parse_args(argv)

    bp = json.load(open(args.blueprint))
    scn = build(bp, args.state, args.light, args.camera)
    scn.cycles.samples = args.samples
    scn.render.resolution_x, scn.render.resolution_y = args.res
    scn.render.image_settings.file_format = "PNG"
    scn.render.image_settings.color_mode = "RGB"
    scn.render.filepath = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(scn.render.filepath), exist_ok=True)
    if args.save_blend:
        os.makedirs(os.path.dirname(os.path.abspath(args.save_blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save_blend))
    bpy.ops.render.render(write_still=True)
    print("BUILD_RENDER_DONE state=%s light=%s cam=%s out=%s" % (args.state, args.light, args.camera, args.out), flush=True)


if __name__ == "__main__":
    main()
