"""
VRChat 用ワインボトル (シェリー型 / PEARCHAN OLOROSO) を作成して FBX で書き出す
Blender スクリプト (Blender 5.1 で動作確認)。ラベルと質感は参考画像に合わせています。

使い方 (どちらでも可):
  A) Blender の Scripting タブでこのファイルを開いて「スクリプト実行」(Alt+P)
  B) コマンドライン:  blender -b -P make_wine_bottle.py -- --out <出力フォルダ>

作成されるもの:
  - WineBottle : ボトル本体 (瓶 + キャップシール + ラベルを 1 メッシュ / 2 マテリアル)
  - Spout      : 注ぎ口の目印 (空のオブジェクト)。WineBottle の子で、口の真上の中心
  - WineBottle.fbx と WineBottle_Atlas.png を出力フォルダに書き出し

仕様:
  - 立てた状態。Unity では Y が上、注ぎ口が真上 (FBX 書き出し時に Z-up → Y-up 変換)
  - 高さ 30cm / 太さ (直径) 7cm。原点は底面の中心
  - 約 2,800 三角形、マテリアル 2 個 (ツヤのあるガラス / つや消しのラベル・キャップ)。
    テクスチャはアトラス 1 枚を 2 つのマテリアルで共有
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
SEGMENTS = 48          # 円周の分割数 (三角形数はおよそ 60 x SEGMENTS)
OUTPUT_DIR = ""        # 空なら: .blend のフォルダ → スクリプトのフォルダ → ホーム の順
FBX_NAME = "WineBottle.fbx"
ATLAS_NAME = "WineBottle_Atlas.png"
OBJECT_NAME = "WineBottle"
SPOUT_NAME = "Spout"
GLASS_MATERIAL = "WineBottle_Glass"   # ガラス (ツヤあり)
LABEL_MATERIAL = "WineBottle_Label"   # ラベル・キャップ (ツヤ控えめ)

# 断面 (半径, 高さ) — 高さ 0.30m / 直径 0.07m 基準。下から上へ。
# 参考画像のシェリー型: 細長い胴、丸く高い肩、長くゆるやかに細くなる首、
# 上部 2 割ほどを覆う黒いキャップシール。
PROFILE = [
    (0.0000, 0.0180),  # 底の上げ底 (中心) — 深めの上げ底
    (0.0100, 0.0150),
    (0.0185, 0.0070),
    (0.0260, 0.0005),
    (0.0275, 0.0000),  # 接地リング
    (0.0325, 0.0010),
    (0.0345, 0.0040),
    (0.0350, 0.0090),
    (0.0350, 0.0750),  # ラベル下端 (下辺中央の出っ張りの下)
    (0.0350, 0.1430),  # ラベル上端
    (0.0348, 0.1530),
    (0.0340, 0.1650),  # 肩
    (0.0326, 0.1755),
    (0.0305, 0.1830),
    (0.0282, 0.1875),
    (0.0256, 0.1910),
    (0.0229, 0.1945),
    (0.0202, 0.1985),
    (0.0180, 0.2030),
    (0.0166, 0.2085),  # 首
    (0.0159, 0.2140),
    (0.0151, 0.2250),
    (0.0145, 0.2360),
    (0.0143, 0.2410),  # ガラスの首 (キャップシール下端の内側)
    (0.0149, 0.2410),  # キャップシール下端 (わずかな段差)
    (0.0141, 0.2620),
    (0.0135, 0.2850),
    (0.0133, 0.2960),
    (0.0128, 0.2993),
    (0.0120, 0.3000),
    (0.0000, 0.3000),  # 天面の中心 (注ぎ口)
]
LABEL_Z = (0.0750, 0.1430)
LABEL_FRACTION = 0.35  # ラベルが覆う円周の割合 (正面中央)
CAPSULE_Z = 0.2410
REF_HEIGHT, REF_RADIUS = 0.30, 0.035

# アトラスのレイアウト (make_label_texture.py と一致させる)
UV_LABEL = (0.0, 0.0, 1.0, 0.66)       # u0, v0, u1, v1
UV_CAPSULE = (0.0, 0.68, 1.0, 0.86)
UV_GLASS = (0.0, 0.88, 0.70, 1.0)
UV_CAP_TOP = (0.74, 0.88, 0.86, 1.0)
UV_PAD = 0.002


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
def fallback_atlas(size=256):
    """アトラス画像が無いとき用の文字なし簡易テクスチャ。"""
    img = bpy.data.images.new(ATLAS_NAME, size, size, alpha=False)
    glass = (0.06, 0.008, 0.005)
    paper = (0.87, 0.73, 0.69)
    black = (0.012, 0.011, 0.010)
    px = [0.0] * (size * size * 4)
    for y in range(size):
        v = (y + 0.5) / size
        for x in range(size):
            u = (x + 0.5) / size
            c = glass
            if v < 0.66:
                c = paper if (v > 0.06 or 0.3 < u < 0.7) else glass
            elif 0.68 <= v < 0.86:
                c = black
            elif v >= 0.88 and u >= 0.72:
                c = black
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


def make_material(name, img, roughness, specular):
    old = bpy.data.materials.get(name)
    if old:
        bpy.data.materials.remove(old)
    mat = bpy.data.materials.new(name)
    if bpy.app.version < (5, 0, 0):
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.location = (-400, 200)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = specular
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

    # ラベルの列 (正面 j = n/2 を中心に、頂点の列でちょうど区切る)
    half = max(1, round(n * LABEL_FRACTION / 2))
    lab_j0, lab_j1 = n // 2 - half, n // 2 + half

    top_z = prof[-1][1]
    cap_start = next(i for i, (r, z) in enumerate(prof) if z >= cap_z - eps and r > prof[i - 1][0])

    def angle(j):
        # j=0 (継ぎ目) を背面 +Y、j=n/2 を正面 -Y にする
        return math.pi / 2 + 2 * math.pi * j / n

    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    rings = []
    for r, z in prof:
        if r < eps:
            rings.append([bm.verts.new((0.0, 0.0, z))])
        else:
            rings.append([bm.verts.new((r * math.cos(angle(j)), r * math.sin(angle(j)), z)) for j in range(n)])

    def region(i, j):
        z0, z1 = prof[i][1], prof[i + 1][1]
        if i + 1 >= cap_start:
            return "capsule"
        if z0 >= label_z[0] - eps and z1 <= label_z[1] + eps and lab_j0 <= j < lab_j1:
            return "label"
        return "glass"

    def glass_uv(z, s):
        # ガラスは高さのグラデーション (底 → キャップ下端)
        return map_rect(UV_GLASS, s, min(1.0, max(0.0, z / cap_z)))

    def ring_uv(i, j, reg):
        if reg == "label":
            t = (prof[i][1] - label_z[0]) / (label_z[1] - label_z[0])
            return map_rect(UV_LABEL, (j - lab_j0) / (lab_j1 - lab_j0), t)
        if reg == "capsule":  # v は高さに比例 (make_label_texture.py と同じ)
            return map_rect(UV_CAPSULE, j / n, (prof[i][1] - cap_z) / (top_z - cap_z))
        return glass_uv(prof[i][1], j / n)

    def top_uv(v):
        # 天面は真上から見た平面投影
        r = prof[-2][0]
        return map_rect(UV_CAP_TOP, 0.5 + v.co.x / r * 0.5, 0.5 + v.co.y / r * 0.5)

    for i in range(len(prof) - 1):
        a, b = rings[i], rings[i + 1]
        if len(a) == 1:  # 底の中心 → 扇形
            for j in range(n):
                f = bm.faces.new((a[0], b[(j + 1) % n], b[j]))
                f.material_index = 0
                for loop in f.loops:
                    loop[uv_layer].uv = glass_uv(loop.vert.co.z, 0.5)
        elif len(b) == 1:  # 天面の中心 → 扇形
            for j in range(n):
                f = bm.faces.new((a[j], a[(j + 1) % n], b[0]))
                f.material_index = 1
                for loop in f.loops:
                    loop[uv_layer].uv = top_uv(loop.vert)
        else:
            for j in range(n):
                k = (j + 1) % n
                reg = region(i, j)
                f = bm.faces.new((a[j], a[k], b[k], b[j]))
                f.material_index = 0 if reg == "glass" else 1
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
    # 以前のバージョンの 1 マテリアル版が残っていれば片付ける
    legacy = bpy.data.materials.get("WineBottle_Mat")
    if legacy and legacy.users == 0:
        bpy.data.materials.remove(legacy)


def build_scene():
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    remove_old()
    coll = bpy.context.scene.collection

    me = build_mesh()
    img = load_atlas()
    # 参考画像のガラスはハイライトが柔らかめ、ラベルとキャップはつや消し
    me.materials.append(make_material(GLASS_MATERIAL, img, roughness=0.2, specular=0.6))
    me.materials.append(make_material(LABEL_MATERIAL, img, roughness=0.65, specular=0.25))
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
