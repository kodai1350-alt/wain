"""
VRChat 用ワインボトル (ボルドー型) を作成して FBX で書き出す Blender スクリプト。

使い方 (どちらでも可):
  A) Blender の Scripting タブでこのファイルを開いて「スクリプト実行」(Alt+P)
  B) コマンドライン:  blender -b -P make_wine_bottle.py -- --out <出力フォルダ>

作成されるもの:
  - WineBottle : ボトル本体 (瓶 + キャップシール + ラベルを 1 メッシュ / 1 マテリアル)
  - Spout      : 注ぎ口の目印 (空のオブジェクト)。WineBottle の子で、口の真上の中心
  - WineBottle.fbx と WineBottle_Atlas.png を出力フォルダに書き出し

仕様:
  - 立てた状態。Unity では Y が上、注ぎ口が真上 (FBX 書き出し時に Z-up → Y-up 変換)
  - 高さ 30cm / 太さ (直径) 7cm。原点は底面の中心
  - 約 1,800 三角形、マテリアル 1 個 (テクスチャアトラス 1 枚)
  - 中の液体なし (外側の瓶だけ)
  - ラベルの正面は Blender の -Y 側 (正面ビューで見える側)

テクスチャ WineBottle_Atlas.png は make_label_texture.py で作ったものを
このスクリプトと同じフォルダ (または .blend と同じフォルダ) に置いてください。
見つからない場合は文字なしの簡易テクスチャを自動で作ります。
"""

import math
import os
import shutil
import sys

import bpy  # bpy を先に (pip 版 bpy では bmesh が bpy の後でないと読めない)
import bmesh

# ---------------------------------------------------------------- 設定
HEIGHT = 0.30          # 高さ (m)
DIAMETER = 0.07        # 胴の直径 (m)
SEGMENTS = 40          # 円周の分割数 (三角形数はおよそ 50 x SEGMENTS)
OUTPUT_DIR = ""        # 空なら: .blend のフォルダ → スクリプトのフォルダ → ホーム の順
FBX_NAME = "WineBottle.fbx"
ATLAS_NAME = "WineBottle_Atlas.png"
OBJECT_NAME = "WineBottle"
SPOUT_NAME = "Spout"
MATERIAL_NAME = "WineBottle_Mat"

# 断面 (半径, 高さ) — 高さ 0.30m / 直径 0.07m 基準。下から上へ。
# 写真のボルドー型: 胴は真っすぐ、なで肩、細い首、上部にキャップシール。
PROFILE = [
    (0.0000, 0.0100),  # 底の上げ底 (中心)
    (0.0180, 0.0040),
    (0.0270, 0.0000),  # 接地リング
    (0.0325, 0.0010),
    (0.0345, 0.0040),
    (0.0350, 0.0090),
    (0.0350, 0.0500),  # ラベル下端
    (0.0350, 0.1700),  # ラベル上端
    (0.0350, 0.1850),  # 肩の始まり
    (0.0343, 0.1950),
    (0.0322, 0.2050),
    (0.0285, 0.2140),
    (0.0232, 0.2210),
    (0.0180, 0.2270),
    (0.0145, 0.2330),
    (0.0128, 0.2400),
    (0.0125, 0.2440),  # ガラスの首 (キャップシールの下端の内側)
    (0.0132, 0.2440),  # キャップシール下端 (わずかな段差)
    (0.0131, 0.2850),
    (0.0141, 0.2880),  # 口の膨らみ (シールの上から)
    (0.0143, 0.2960),
    (0.0137, 0.2994),
    (0.0123, 0.3000),
    (0.0000, 0.3000),  # 天面の中心 (注ぎ口)
]
LABEL_Z = (0.0500, 0.1700)
CAPSULE_Z = 0.2440
REF_HEIGHT, REF_RADIUS = 0.30, 0.035

# アトラスのレイアウト (make_label_texture.py と一致させる)
UV_LABEL = (0.0, 0.0, 1.0, 0.50)       # u0, v0, u1, v1
UV_CAPSULE = (0.0, 0.52, 1.0, 0.72)
UV_GLASS = (0.0, 0.76, 0.70, 1.0)
UV_CAP_TOP = (0.74, 0.76, 0.98, 1.0)
UV_PAD = 0.004


# ---------------------------------------------------------------- パス
def script_dir():
    f = globals().get("__file__", "")
    if f and os.path.isfile(f):
        return os.path.dirname(os.path.abspath(f))
    # Blender のテキストエディタから実行した場合
    for text in bpy.data.texts:
        if text.filepath and os.path.basename(text.filepath) == "make_wine_bottle.py":
            return os.path.dirname(bpy.path.abspath(text.filepath))
    return ""


def cli_out_dir():
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]
        if "--out" in args and args.index("--out") + 1 < len(args):
            return os.path.abspath(args[args.index("--out") + 1])
    return ""


def resolve_output_dir():
    for d in (cli_out_dir(), OUTPUT_DIR, bpy.path.abspath("//") if bpy.data.filepath else "",
              script_dir(), os.path.expanduser("~")):
        if d:
            os.makedirs(d, exist_ok=True)
            return d
    return os.getcwd()


def find_atlas():
    dirs = [script_dir(), bpy.path.abspath("//") if bpy.data.filepath else "", cli_out_dir(), OUTPUT_DIR]
    for d in dirs:
        if d and os.path.isfile(os.path.join(d, ATLAS_NAME)):
            return os.path.join(d, ATLAS_NAME)
    return ""


# ---------------------------------------------------------------- テクスチャ
def fallback_atlas(size=512):
    """アトラス画像が無いとき用の文字なし簡易テクスチャ。"""
    img = bpy.data.images.new(ATLAS_NAME, size, size, alpha=False)
    glass = (0.157, 0.047, 0.071)
    paper = (0.94, 0.91, 0.85)
    red = (0.58, 0.08, 0.125)
    gold = (0.79, 0.64, 0.32)
    px = [0.0] * (size * size * 4)
    for y in range(size):
        v = (y + 0.5) / size
        for x in range(size):
            u = (x + 0.5) / size
            c = glass
            if v < 0.5:
                if 0.275 < u < 0.725 and 0.01 < v < 0.49:
                    c = paper if v > 0.08 else (0.11, 0.09, 0.09)
            elif 0.52 <= v < 0.72:
                c = gold if (v > 0.695 or v < 0.53) else red
            elif v >= 0.76 and u >= 0.72:
                du, dv = (u - 0.86) / 0.12, (v - 0.88) / 0.12
                c = red if du * du + dv * dv < 0.74 else gold
            i = (y * size + x) * 4
            px[i:i + 4] = (*c, 1.0)
    img.pixels = px
    return img


def load_atlas():
    path = find_atlas()
    old = bpy.data.images.get(ATLAS_NAME)
    if old:
        bpy.data.images.remove(old)
    if path:
        img = bpy.data.images.load(path)
        img.name = ATLAS_NAME
        print("[WineBottle] texture:", path)
    else:
        img = fallback_atlas()
        print("[WineBottle] texture not found -> simple fallback texture")
    img.pack()
    return img


def make_material(img):
    old = bpy.data.materials.get(MATERIAL_NAME)
    if old:
        bpy.data.materials.remove(old)
    mat = bpy.data.materials.new(MATERIAL_NAME)
    if bpy.app.version < (5, 0, 0):
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.location = (-400, 200)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.25
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.6
    return mat


# ---------------------------------------------------------------- メッシュ
def lerp(a, b, t):
    return a + (b - a) * t


def map_rect(rect, s, t):
    u0, v0, u1, v1 = rect
    return (lerp(u0 + UV_PAD, u1 - UV_PAD, s), lerp(v0 + UV_PAD, v1 - UV_PAD, t))


def build_mesh():
    sx = DIAMETER / (2 * REF_RADIUS)
    sz = HEIGHT / REF_HEIGHT
    prof = [(r * sx, z * sz) for r, z in PROFILE]
    label_z = (LABEL_Z[0] * sz, LABEL_Z[1] * sz)
    cap_z = CAPSULE_Z * sz
    n = SEGMENTS
    eps = 1e-6

    # 断面に沿った長さ (ガラスとキャップシールの v 座標に使う)
    arc = [0.0]
    for (r0, z0), (r1, z1) in zip(prof, prof[1:]):
        arc.append(arc[-1] + math.hypot(r1 - r0, z1 - z0))
    cap_start = next(i for i, (r, z) in enumerate(prof) if z >= cap_z - eps and r > prof[i - 1][0])
    glass_len = arc[cap_start - 1]
    cap_len = arc[-2] - arc[cap_start - 1]

    def angle(j):
        # u=0 (継ぎ目) を背面 +Y、u=0.5 を正面 -Y にする
        return math.pi / 2 + 2 * math.pi * j / n

    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    rings = []
    for r, z in prof:
        if r < eps:
            rings.append([bm.verts.new((0.0, 0.0, z))])
        else:
            rings.append([bm.verts.new((r * math.cos(angle(j)), r * math.sin(angle(j)), z)) for j in range(n)])

    def region(i):
        z0, z1 = prof[i][1], prof[i + 1][1]
        if z0 >= label_z[0] - eps and z1 <= label_z[1] + eps:
            return "label"
        if i + 1 >= cap_start:
            return "capsule"
        return "glass"

    def ring_uv(i, j, reg):
        s = j / n
        if reg == "label":
            t = (prof[i][1] - label_z[0]) / (label_z[1] - label_z[0])
            return map_rect(UV_LABEL, s, t)
        if reg == "capsule":
            t = (arc[i] - arc[cap_start - 1]) / cap_len
            return map_rect(UV_CAPSULE, s, t)
        return map_rect(UV_GLASS, s, arc[i] / glass_len)

    def top_uv(v):
        # 天面は真上から見た平面投影 (正面 -Y が画像の下)
        r = prof[-2][0]
        return map_rect(UV_CAP_TOP, 0.5 + v.co.x / r * 0.5, 0.5 + v.co.y / r * 0.5)

    def bottom_uv(v):
        r = prof[2][0]
        return map_rect(UV_GLASS, 0.5 + v.co.x / r * 0.5, 0.5 + v.co.y / r * 0.5)

    for i in range(len(prof) - 1):
        a, b = rings[i], rings[i + 1]
        reg = region(i)
        if len(a) == 1:  # 底の中心 → 扇形
            for j in range(n):
                f = bm.faces.new((a[0], b[(j + 1) % n], b[j]))
                for loop in f.loops:
                    loop[uv_layer].uv = bottom_uv(loop.vert)
        elif len(b) == 1:  # 天面の中心 → 扇形
            for j in range(n):
                f = bm.faces.new((a[j], a[(j + 1) % n], b[0]))
                for loop in f.loops:
                    loop[uv_layer].uv = top_uv(loop.vert)
        else:
            for j in range(n):
                k = (j + 1) % n
                f = bm.faces.new((a[j], a[k], b[k], b[j]))
                # UV はループごとに設定 (継ぎ目で u=1.0 になるよう j+1 を使う)
                uvs = (ring_uv(i, j, reg), ring_uv(i, j + 1, reg),
                       ring_uv(i + 1, j + 1, reg), ring_uv(i + 1, j, reg))
                for loop, uv in zip(f.loops, uvs):
                    loop[uv_layer].uv = uv

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = True
    # 角の立った所 (底の縁・シールの段差・口の縁) だけシャープに
    for e in bm.edges:
        if e.is_manifold and e.calc_face_angle(0.0) > math.radians(40):
            e.smooth = False

    me = bpy.data.meshes.new(OBJECT_NAME)
    bm.to_mesh(me)
    bm.free()
    return me


# ---------------------------------------------------------------- シーン
def remove_old():
    for name in (SPOUT_NAME, OBJECT_NAME):
        ob = bpy.data.objects.get(name)
        if ob:
            data = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if data and data.users == 0:
                bpy.data.meshes.remove(data)
    me = bpy.data.meshes.get(OBJECT_NAME)
    if me and me.users == 0:
        bpy.data.meshes.remove(me)


def build_scene():
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    remove_old()
    coll = bpy.context.scene.collection

    me = build_mesh()
    me.materials.append(make_material(load_atlas()))
    bottle = bpy.data.objects.new(OBJECT_NAME, me)
    coll.objects.link(bottle)

    spout = bpy.data.objects.new(SPOUT_NAME, None)
    spout.empty_display_type = "SINGLE_ARROW"   # 矢印 = 注ぐ向き (上)
    spout.empty_display_size = 0.03
    spout.location = (0.0, 0.0, HEIGHT)
    spout.parent = bottle
    coll.objects.link(spout)
    return bottle, spout


def export_fbx(bottle, spout, out_dir):
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    bottle.select_set(True)
    spout.select_set(True)
    bpy.context.view_layer.objects.active = bottle

    path = os.path.join(out_dir, FBX_NAME)
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"MESH", "EMPTY"},
        # Unity 向け: 1unit=1m、回転 0・スケール 1 で読み込まれる設定
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z",
        axis_up="Y",
        bake_space_transform=True,
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        add_leaf_bones=False,
        bake_anim=False,
        path_mode="COPY",
        embed_textures=True,
    )
    # Unity でマテリアルに設定しやすいよう PNG も隣に保存
    img = bpy.data.images.get(ATLAS_NAME)
    if img:
        png = os.path.join(out_dir, ATLAS_NAME)
        src = bpy.path.abspath(img.filepath) if img.filepath else ""
        if src and os.path.isfile(src):
            if os.path.abspath(src) != os.path.abspath(png):
                shutil.copyfile(src, png)
        else:
            img.save(filepath=png)
    return path


def main():
    bottle, spout = build_scene()
    out_dir = resolve_output_dir()
    path = export_fbx(bottle, spout, out_dir)
    tris = sum(len(p.vertices) - 2 for p in bottle.data.polygons)
    print("[WineBottle] triangles: %d, materials: %d" % (tris, len(bottle.data.materials)))
    print("[WineBottle] exported:", path)


if __name__ == "__main__":
    main()
