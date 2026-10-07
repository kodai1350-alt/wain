"""
VRChat 用の刀 (雷電将軍の元素爆発の刀「夢想の一太刀」風, ファンメイド) を作成して
FBX で書き出す Blender スクリプト (Blender 5.1 で動作確認)。

使い方 (どちらでも可):
  A) Blender の Scripting タブでこのファイルを開いて「スクリプト実行」(Alt+P)
  B) コマンドライン:  blender -b -P make_katana.py -- --out <出力フォルダ>

作成されるもの:
  - Katana : 刀本体 (刃・付け根の飾り板と白い巴・鍔・柄・金具・柄頭の炎を 1 メッシュ)
      マテリアル 2 個: Katana_Blade (光る部分) / Katana_Hilt (柄と金具)
  - Grip   : 握る位置の目印 (空のオブジェクト、Katana の子)
  - Tip    : 切っ先の目印 (空のオブジェクト、Katana の子)
  - Katana.fbx と Katana_Atlas.png を出力フォルダに書き出し

仕様:
  - 刃の反り・鍔は参考画像 (ゲーム画面) を測って合わせています
  - 刃の付け根の飾り板 (トゲ・巻き・抜け) と白い巴のかけらは、参考画像の輪郭をなぞった形
  - VRChat のアバター (身長 1.4〜1.6m 前後) に合わせた大きさ: 全長 約 1.07m
    (刃 80cm・柄 20cm・柄頭の飾り 約 7cm)。参考画像のように刃が柄の約 4 倍の細長いバランス。
    SCALE で全体の大きさを変えられます
  - Unity では刃が上 (Y)、刃先が前 (+Z)。原点は鍔の中心
  - テクスチャは 3 枚 (どれも 8192x8192、2 つのマテリアルで共有):
      Katana_Atlas.png (色) / Katana_Emission.png (発光) / Katana_Normal.png (ノーマルマップ)
    FBX には埋め込まず、隣に PNG を置きます (Unity で同じフォルダに入れてください)

テクスチャ Katana_Atlas.png は make_katana_texture.py で作ったものを
このスクリプトと同じフォルダ (または .blend と同じフォルダ) に置いてください。
"""

import math
import os
import shutil
import sys

import bpy  # bpy を先に (pip 版 bpy では bmesh が bpy の後でないと読めない)
import bmesh
from mathutils import Matrix, Vector

# ---------------------------------------------------------------- 設定
SCALE = 1.0            # 全体の大きさ (1.0 = 全長 約 1.07m)
BLADE_LEN = 0.80       # 刃の長さ (m)
HANDLE_LEN = 0.20      # 柄の長さ (m)
# 反り: 刃の向きが根元から切っ先までに曲がる角度 (度)。参考画像を測った値。
#   根元から半ばまではゆるやか (CURVE_BASE)、先の 2 割で急に曲がる (CURVE_TIP, 先反り)
CURVE_BASE = 27.0      # 参考画像の反りの深さ (弦の約 7.9%) に合わせた値
CURVE_TIP = 28.0
CURVE_TIP_POWER = 12
BLADE_W = 0.032        # 刃の幅 (m)。参考画像どおり切っ先近くまでほぼ一定
BLADE_T = 0.0075       # 刃の厚み (付け根, m)
OUTPUT_DIR = ""        # 空なら: .blend のフォルダ → スクリプトのフォルダ → ホーム の順
FBX_NAME = "Katana.fbx"
ATLAS_NAME = "Katana_Atlas.png"          # 色
EMISSION_NAME = "Katana_Emission.png"    # 発光 (光らせたい所だけ明るい)
NORMAL_NAME = "Katana_Normal.png"        # ノーマルマップ (凹凸)
TEXTURES = (ATLAS_NAME, EMISSION_NAME, NORMAL_NAME)
OBJECT_NAME = "Katana"
BLADE_MATERIAL = "Katana_Blade"   # 刃・紋・ヒレ・鍔・光る玉・柄頭の炎 (光る)
HILT_MATERIAL = "Katana_Hilt"     # 柄巻き・金具

# アトラスのレイアウト (make_katana_texture.py と一致させる)
UV_BLADE = (0.0, 0.0, 1.0, 0.36)
UV_HANDLE = (0.0, 0.38, 1.0, 0.66)
UV_GOLD = (0.0, 0.68, 1.0, 0.76)
UV_GUARD = (0.0, 0.78, 0.20, 0.98)    # 刃の付け根の飾り板 (濃い紫と薄い紫の炎の模様)
UV_WHITE = (0.22, 0.78, 0.30, 0.98)
UV_TSUBA = (0.32, 0.78, 0.52, 0.98)
UV_FLAME = (0.54, 0.78, 0.64, 0.98)
UV_PAD = 0.002
UV_DARK = (0.93, 0.88)        # アトラスの空き部分 (濃い紫一色)

# 飾り板の模様の範囲 (make_katana_texture.py と一致させる)。UV_GUARD の中に
# a (鍔からの長さ) と e (峰からの距離) を同じ縮尺で並べる。上の余白は側面用の薄紫
GUARD_A_MIN, GUARD_E_MIN, GUARD_SPAN = 0.0016, -0.0345, 0.1024
UV_GUARD_SIDE = (0.10, 0.975)
BLADE_START = 0.069   # 刀身はここから (飾り板の抜けをふさがないよう、抜けより先で始める)

MAT_BLADE, MAT_HILT = 0, 1
X = Vector((1.0, 0.0, 0.0))   # 刃の厚み方向


# ---------------------------------------------------------------- パス
def script_dir():
    f = globals().get("__file__", "")
    if f and os.path.isfile(f):
        return os.path.dirname(os.path.abspath(f))
    for text in bpy.data.texts:  # Blender のテキストエディタから実行した場合
        if text.filepath and os.path.basename(text.filepath) == "make_katana.py":
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


def find_texture(name):
    for d in (script_dir(), bpy.path.abspath("//") if bpy.data.filepath else "", cli_out_dir(), OUTPUT_DIR):
        if d and os.path.isfile(os.path.join(d, name)):
            return os.path.join(d, name)
    return ""


# ---------------------------------------------------------------- 刀の中心線
def bend(t):
    """刃の付け根から t (m, 峰に沿った長さ) での曲がり角 (ラジアン)。峰側 (+Y) へ曲がる。"""
    u = min(max(t / BLADE_LEN, 0.0), 1.0)
    return math.radians(CURVE_BASE * u + CURVE_TIP * u ** CURVE_TIP_POWER)


_SPINE = []


def _spine_table():
    """峰の線を長さに沿って積分した点の表 (刃の部分)。"""
    if _SPINE:
        return _SPINE
    n = 800
    p = Vector((0.0, 0.0, 0.0))
    _SPINE.append(p.copy())
    ds = BLADE_LEN / n
    for i in range(n):
        a = bend((i + 0.5) * ds)
        p += Vector((0.0, math.sin(a), math.cos(a))) * ds
        _SPINE.append(p.copy())
    return _SPINE


def spine(t):
    """峰の線。t = 鍔からの長さ (刃側が正、柄側が負)。柄はまっすぐ。"""
    if t <= 0:
        return Vector((0.0, 0.0, t))
    table = _spine_table()
    f = min(t, BLADE_LEN) / BLADE_LEN * (len(table) - 1)
    i = min(int(f), len(table) - 2)
    return table[i].lerp(table[i + 1], f - i)


def frame(t):
    """t での (接線, 刃先方向)。刃先方向は -Y 寄り。"""
    a = bend(t) if t > 0 else 0.0
    return Vector((0.0, math.sin(a), math.cos(a))), Vector((0.0, -math.cos(a), math.sin(a)))


def center(t):
    """刃の幅の中心 (柄・鍔・柄頭はこの線に沿う)。"""
    _, n = frame(t)
    return spine(t) + n * (BLADE_W / 2)


# ---------------------------------------------------------------- テクスチャ・マテリアル
FALLBACK = {ATLAS_NAME: (0.6, 0.5, 0.95), EMISSION_NAME: (0.0, 0.0, 0.0), NORMAL_NAME: (0.5, 0.5, 1.0)}


def load_texture(name):
    """テクスチャを読み込む。見つからなければ単色の代わりを作る。"""
    path = find_texture(name)
    old = bpy.data.images.get(name)
    if old:
        bpy.data.images.remove(old)
    if path:
        img = bpy.data.images.load(path)
        img.name = name
        print("[Katana] texture:", path)
    else:
        img = bpy.data.images.new(name, 64, 64, alpha=False)
        img.pixels = [*FALLBACK[name], 1.0] * (64 * 64)
        print("[Katana] texture not found -> plain:", name)
    if name == NORMAL_NAME:
        img.colorspace_settings.name = "Non-Color"
    return img


def make_material(name, albedo, normal, roughness, emission_img=None, emission=0.0):
    old = bpy.data.materials.get(name)
    if old:
        bpy.data.materials.remove(old)
    mat = bpy.data.materials.new(name)
    if bpy.app.version < (5, 0, 0):
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = albedo
    tex.location = (-500, 300)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    # ノーマルマップ (柄巻きの盛り上がり・金の彫り・模様の縁の溝)
    ntex = nt.nodes.new("ShaderNodeTexImage")
    ntex.image = normal
    ntex.location = (-700, -300)
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nmap.location = (-300, -300)
    nt.links.new(ntex.outputs["Color"], nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    if emission_img is not None and emission > 0:
        etex = nt.nodes.new("ShaderNodeTexImage")
        etex.image = emission_img
        etex.location = (-500, 0)
        nt.links.new(etex.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


# ---------------------------------------------------------------- メッシュ部品
def lerp(a, b, t):
    return a + (b - a) * t


def map_rect(rect, s, t):
    u0, v0, u1, v1 = rect
    return (lerp(u0 + UV_PAD, u1 - UV_PAD, s), lerp(v0 + UV_PAD, v1 - UV_PAD, t))


class Builder:
    def __init__(self):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")

    def face(self, verts, uvs, mat):
        f = self.bm.faces.new(verts)
        f.material_index = mat
        for loop, uv in zip(f.loops, uvs):
            loop[self.uv].uv = uv
        return f

    def rings(self, rings, uv_of, mat, cap_start=None, cap_end=None):
        """リング (同じ頂点数) を順につないで筒を作る。uv_of(i, j) は j=0..n (n は継ぎ目用)。"""
        vs = [[self.bm.verts.new(p) for p in ring] for ring in rings]
        n = len(rings[0])
        for i in range(len(vs) - 1):
            for j in range(n):
                k = (j + 1) % n
                self.face((vs[i][j], vs[i][k], vs[i + 1][k], vs[i + 1][j]),
                          (uv_of(i, j), uv_of(i, j + 1), uv_of(i + 1, j + 1), uv_of(i + 1, j)), mat)
        for idx, cap in ((0, cap_start), (len(vs) - 1, cap_end)):
            if cap is None:
                continue
            if isinstance(cap, Vector):  # 1 点に集める (とがった先端)
                tip = self.bm.verts.new(cap)
                ring = vs[idx]
                for j in range(n):
                    a, b = ring[j], ring[(j + 1) % n]
                    tri = (a, b, tip) if idx else (b, a, tip)
                    self.face(tri, (uv_of(idx, j), uv_of(idx, j + 1), uv_of(idx, j + 0.5)), mat)
            else:                        # 平らなふた
                ring = vs[idx] if idx else list(reversed(vs[idx]))
                self.face(ring, [cap(v.co) for v in ring], mat)
        return vs

    def prism(self, outline, to3d, d0, d1, uv_face, uv_side, mat):
        """2D の外形 outline を厚み方向 (d0→d1) に押し出す。to3d(a, b, d) で 3D 座標へ。"""
        bot = [self.bm.verts.new(to3d(a, b, d0)) for a, b in outline]
        top = [self.bm.verts.new(to3d(a, b, d1)) for a, b in outline]
        n = len(outline)
        self.face(list(reversed(bot)), [uv_face(*outline[i]) for i in reversed(range(n))], mat)
        self.face(top, [uv_face(a, b) for a, b in outline], mat)
        for i in range(n):
            j = (i + 1) % n
            self.face((bot[i], bot[j], top[j], top[i]),
                      (uv_side(i / n, 0), uv_side((i + 1) / n, 0), uv_side((i + 1) / n, 1), uv_side(i / n, 1)), mat)


def blade_profile(t):
    """t での (刃の幅, 厚み)。"""
    tk = BLADE_LEN * 0.88               # 横手 (切っ先の始まり)
    w = lerp(BLADE_W, BLADE_W * 0.94, min(1.0, t / tk))   # ほぼ一定の幅
    th = lerp(BLADE_T, BLADE_T * 0.65, min(1.0, t / tk))
    if t > tk:                           # 切っ先: 刃先の線が丸く峰へ向かう
        u = (t - tk) / (BLADE_LEN - tk)
        k = math.sqrt(max(0.0, 1 - u * u))
        w *= k
        th *= k ** 0.7
    return w, th


def build_blade(b):
    """刃: 刃先・鎬・峰をもつ 6 角の断面を、反った中心線に沿ってつなぐ。"""
    tk = BLADE_LEN * 0.88
    ts = [lerp(BLADE_START, tk, i / 44) for i in range(45)]
    ts += [lerp(tk, BLADE_LEN, (i / 14) ** 0.8) for i in range(1, 14)]
    v_of = (0.0, 0.55, 0.85, 1.0, 0.85, 0.55)   # 刃先 → 鎬 → 峰 → 峰の頂 → 峰 → 鎬
    rings = []
    for t in ts:
        w, th = blade_profile(t)
        _, n = frame(t)
        p = spine(t)
        rings.append([
            p + n * w,                                   # 刃先
            p + n * (w * 0.36) + X * (th / 2),           # 鎬 (右)
            p + X * (th * 0.38),                         # 峰 (右)
            p - n * 0.0012,                              # 峰の頂
            p - X * (th * 0.38),                         # 峰 (左)
            p + n * (w * 0.36) - X * (th / 2),           # 鎬 (左)
        ])

    def uv_of(i, j):
        jj = min(int(j), 5) if j < 6 else 0
        frac = j - int(j)
        v = v_of[jj % 6] if frac == 0 else (v_of[jj % 6] + v_of[(jj + 1) % 6]) / 2
        return map_rect(UV_BLADE, ts[min(i, len(ts) - 1)] / BLADE_LEN, v)

    b.rings(rings, uv_of, MAT_BLADE,
            cap_start=lambda co: map_rect(UV_BLADE, 0.0, 0.5),
            cap_end=spine(BLADE_LEN))


def build_guard(b):
    """刃の付け根の飾り板と、その上の白い巴のかけら。

    参考画像 (コスプレ用の刀の写真) の輪郭をなぞって刀の寸法に合わせた形。
    峰側の大小 2 本のトゲ、刃側の鉤のように巻いた張り出し、中の抜け (穴) まで再現し、
    白い巴は 6 つの別々のかけら (つながっていない) として板から少し浮かせて載せる。
    """
    k = BLADE_W / 0.032                     # 刃の幅を変えたら飾りも同じ比率で

    def P(a, e, d):
        a, e = a * k, e * k
        _, n = frame(a)
        return spine(a) + n * e + X * d

    def guard_uv(a, e):
        return map_rect(UV_GUARD, (a - GUARD_A_MIN) / GUARD_SPAN, (e - GUARD_E_MIN) / GUARD_SPAN)

    def slab(part, half, uv_cap, uv_side):
        """part = {"pts": 輪郭の点, "rings": 外周と穴の点の数, "tris": 三角形}。厚み ±half の板にする。"""
        pts = part["pts"]
        top = [b.bm.verts.new(P(a, e, half)) for a, e in pts]
        bot = [b.bm.verts.new(P(a, e, -half)) for a, e in pts]
        for i, j, m in part["tris"]:            # 表と裏の面 (三角形はあらかじめ分割済み)
            for vs, idx in ((top, (i, j, m)), (bot, (m, j, i))):
                try:
                    b.face([vs[x] for x in idx], [uv_cap(*pts[x]) for x in idx], MAT_BLADE)
                except ValueError:
                    pass                        # つぶれた三角形は飛ばす
        off = 0
        for n in part["rings"]:                 # 側面 (外周と穴のふち)
            for i in range(n):
                i0, i1 = off + i, off + (i + 1) % n
                b.face((bot[i0], bot[i1], top[i1], top[i0]), [uv_side] * 4, MAT_BLADE)
            off += n

    half = BLADE_T / 2 + 0.0004             # 刀身の面よりわずかに外へ
    for part in GUARD_PLATE:
        slab(part, half, guard_uv, map_rect(UV_GUARD, *UV_GUARD_SIDE))
    white = map_rect(UV_WHITE, 0.5, 0.5)
    for part in GUARD_SWIRLS:
        slab(part, half + 0.0012, lambda a, e: white, white)


def build_tsuba(b):
    """細長い棒状の鍔 (両端は斜めにとがる)。"""
    L0, L1, hw = -0.046, BLADE_W + 0.064, 0.0085
    outline = [(L0, 0.0), (L0 + 0.013, -hw), (L1 - 0.013, -hw), (L1, 0.0), (L1 - 0.013, hw), (L0 + 0.013, hw)]

    def to3d(a, bb, d):
        _, n = frame(0.0)
        return spine(d) + n * a + X * bb

    b.prism(outline, to3d, -0.008, 0.0,
            lambda a, bb: map_rect(UV_TSUBA, (a - L0) / (L1 - L0), 0.5 + bb / hw * 0.5),
            lambda s_, t_: map_rect(UV_TSUBA, s_, 0.5), MAT_BLADE)


def handle_radius(t):
    """柄の断面 (厚み方向, 刃の方向) の半径。中ほどがわずかに細い。"""
    u = (-t) / HANDLE_LEN
    k = 1.0 - 0.05 * math.sin(math.pi * u)
    return 0.0118 * k, 0.0150 * k


def ellipse_ring(t, rx, rn, seg, scale=1.0):
    """楕円のリング。継ぎ目 (j=0) は峰側に置いて目立たないようにする。"""
    _, n = frame(t)
    c = center(t)
    return [c + X * (rx * scale * math.cos(a)) + n * (rn * scale * math.sin(a))
            for a in (-math.pi / 2 + math.tau * j / seg for j in range(seg))]


def build_handle(b):
    """柄: 楕円の断面。紫のマーブルに銀の柄巻き (テクスチャ)。"""
    seg = 20
    t0, t1 = -0.008, -HANDLE_LEN
    ts = [lerp(t0, t1, i / 16) for i in range(17)]
    rings = [ellipse_ring(t, *handle_radius(t), seg) for t in ts]
    b.rings(rings, lambda i, j: map_rect(UV_HANDLE, i / 16, j / seg), MAT_HILT)


def build_fittings(b):
    """縁 (ふち) と柄頭 (かしら) の金具。縁は濃い紫、柄頭は金。"""
    seg = 20
    gold = lambda i, j: map_rect(UV_GOLD, j / seg, 0.5)
    # 縁: 鍔の下の輪 (参考画像どおり濃い紫)
    rx, rn = handle_radius(-0.008)
    rings = [ellipse_ring(t, rx, rn, seg, s) for t, s in ((-0.008, 1.10), (-0.020, 1.08), (-0.022, 1.0))]
    b.rings(rings, lambda i, j: UV_DARK, MAT_BLADE)
    # 柄頭: 丸くすぼまる金具
    tE = -HANDLE_LEN
    rx, rn = handle_radius(tE)
    prof = ((tE + 0.010, 1.0), (tE + 0.008, 1.10), (tE - 0.006, 1.10), (tE - 0.013, 0.85), (tE - 0.018, 0.45))
    rings = [ellipse_ring(t, rx, rn, seg, s) for t, s in prof]
    b.rings(rings, gold, MAT_HILT, cap_end=center(tE - 0.020))


def build_pommel_flame(b):
    """柄頭の先の黄色く光る炎 (しずく形)。"""
    seg = 12
    tE = -HANDLE_LEN - 0.016
    prof = ((0.000, 0.0040), (0.010, 0.0075), (0.022, 0.0070), (0.034, 0.0040), (0.044, 0.0015))
    rings = []
    for dz, r in prof:
        rings.append(ellipse_ring(tE - dz, r, r, seg))
    nprof = len(prof)
    b.rings(rings, lambda i, j: map_rect(UV_FLAME, j / seg, i / nprof), MAT_BLADE,
            cap_start=lambda co: map_rect(UV_FLAME, 0.5, 0.0), cap_end=center(tE - 0.052))


def build_orbs(b):
    """柄の峰側に並ぶ、白く光る 2 つの玉。"""
    for t in (-0.034, -0.058):
        _, n = frame(t)
        rx, rn = handle_radius(t)
        c = center(t) - n * (rn + 0.0035)
        r = 0.0055
        rings = []
        for i in range(1, 6):
            phi = math.pi * i / 6
            rings.append([c + Vector((r * math.sin(phi) * math.cos(a), r * math.sin(phi) * math.sin(a), r * math.cos(phi)))
                          for a in (math.tau * j / 10 for j in range(10))])
        white = lambda i, j: map_rect(UV_WHITE, 0.5, 0.5)
        b.rings(rings, white, MAT_BLADE, cap_start=c + Vector((0, 0, r)), cap_end=c - Vector((0, 0, r)))


def build_talons(b):
    """柄の峰側に並ぶ、柄頭の方へ反った金の爪飾り。"""
    for k, t0 in enumerate(-HANDLE_LEN * f for f in (0.36, 0.50, 0.64, 0.78, 0.91)):
        size = 1.0 + 0.25 * k / 4
        L, W = 0.026 * size, 0.0055 * size
        center_line = []
        steps = 8
        for i in range(steps + 1):
            s = i / steps
            center_line.append((-L * s, -0.018 * size * math.sin(s * math.pi / 2) - 0.006 * s))
        outline = []
        for i, (a, bb) in enumerate(center_line):
            outline.append((a, bb + W * (1 - i / steps) * 0.5))
        for i, (a, bb) in reversed(list(enumerate(center_line))):
            outline.append((a, bb - W * (1 - i / steps) * 0.5))

        def to3d(a, bb, d, t0=t0):
            t = t0 + a
            _, n = frame(t)
            rx, rn = handle_radius(t)
            return center(t) - n * (rn - 0.002) + n * bb + X * d

        b.prism(outline, to3d, -0.0011, 0.0011,
                lambda a, bb: map_rect(UV_GOLD, min(1.0, 0.3 - a / 0.1), min(1.0, max(0.0, 0.5 + bb / 0.07))),
                lambda s_, t_: map_rect(UV_GOLD, s_, 0.2 + 0.6 * t_), MAT_HILT)


def build_mesh():
    b = Builder()
    build_blade(b)
    build_guard(b)
    build_tsuba(b)
    build_handle(b)
    build_fittings(b)
    build_pommel_flame(b)
    build_orbs(b)
    build_talons(b)
    bm = b.bm

    # へこんだ多角形も正しく三角形にする (Unity での読み込みを安定させる)
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    bmesh.ops.triangulate(bm, faces=ngons, quad_method="BEAUTY", ngon_method="BEAUTY")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:  # 刃先や角だけシャープに
        if not e.is_manifold or e.calc_face_angle(0.0) > math.radians(38):
            e.smooth = False

    # 原点を鍔の中心へ、全体の大きさを SCALE 倍に
    origin = center(0.0)
    bmesh.ops.transform(bm, matrix=Matrix.Scale(SCALE, 4) @ Matrix.Translation(-origin), verts=bm.verts)
    me = bpy.data.meshes.new(OBJECT_NAME)
    bm.to_mesh(me)
    bm.free()
    return me, origin


# ---------------------------------------------------------------- シーン
def remove_old():
    for name in ("Grip", "Tip", OBJECT_NAME):
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

    me, origin = build_mesh()
    albedo, emis, normal = (load_texture(n) for n in TEXTURES)
    me.materials.append(make_material(BLADE_MATERIAL, albedo, normal, roughness=0.3, emission_img=emis, emission=1.5))
    me.materials.append(make_material(HILT_MATERIAL, albedo, normal, roughness=0.45))
    katana = bpy.data.objects.new(OBJECT_NAME, me)
    coll.objects.link(katana)

    empties = []
    for name, pos, kind in (("Grip", center(-HANDLE_LEN * 0.5), "PLAIN_AXES"),
                            ("Tip", spine(BLADE_LEN), "SINGLE_ARROW")):
        e = bpy.data.objects.new(name, None)
        e.empty_display_type = kind
        e.empty_display_size = 0.05
        e.location = (pos - origin) * SCALE
        e.parent = katana
        coll.objects.link(e)
        empties.append(e)
    return katana, empties


def export_fbx(katana, empties, out_dir):
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    for ob in [katana] + empties:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = katana
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
        path_mode="STRIP",      # 8K テクスチャは FBX に埋め込まず、ファイル名だけ記録して隣に置く
        embed_textures=False,
    )
    for name in TEXTURES:  # Unity でマテリアルに設定しやすいよう PNG も隣に保存
        img = bpy.data.images.get(name)
        if not img:
            continue
        png = os.path.join(out_dir, name)
        src = bpy.path.abspath(img.filepath) if img.filepath else ""
        if src and os.path.isfile(src):
            if os.path.abspath(src) != os.path.abspath(png):
                shutil.copyfile(src, png)
        else:
            img.save(filepath=png)
    return path


def main():
    katana, empties = build_scene()
    out_dir = resolve_output_dir()
    path = export_fbx(katana, empties, out_dir)
    tris = sum(len(p.vertices) - 2 for p in katana.data.polygons)
    dims = katana.dimensions
    print("[Katana] triangles: %d, materials: %d" % (tris, len(katana.data.materials)))
    print("[Katana] size: %.3f x %.3f x %.3f m" % (dims.x, dims.y, dims.z))
    print("[Katana] exported:", path)


# ---------------------------------------------------------------- 飾り板の形のデータ
# 参考画像からなぞった輪郭 (a = 鍔からの長さ, e = 峰からの距離, 単位 m, 刃の幅 3.2cm 基準)。
# pts = 点 (外周 → 穴の順)、rings = それぞれの点の数、tris = 面の三角形 (点の番号)
GUARD_PLATE = [
    {"pts": [(0.0016, -0.0091), (0.0016, 0.0297), (0.0020, 0.0300), (0.0153, 0.0300), (0.0160, 0.0307), (0.0162, 0.0341), (0.0166, 0.0339), (0.0180, 0.0311), (0.0188, 0.0304), (0.0195, 0.0304), (0.0200, 0.0311), (0.0204, 0.0327), (0.0259, 0.0408), (0.0310, 0.0458), (0.0352, 0.0478), (0.0389, 0.0487), (0.0442, 0.0491), (0.0479, 0.0484), (0.0489, 0.0478), (0.0513, 0.0471), (0.0534, 0.0459), (0.0585, 0.0408), (0.0598, 0.0389), (0.0609, 0.0361), (0.0615, 0.0329), (0.0608, 0.0275), (0.0614, 0.0272), (0.0621, 0.0283), (0.0624, 0.0277), (0.0617, 0.0269), (0.0623, 0.0264), (0.0637, 0.0264), (0.0673, 0.0272), (0.0733, 0.0330), (0.0749, 0.0350), (0.0750, 0.0363), (0.0758, 0.0382), (0.0756, 0.0401), (0.0766, 0.0412), (0.0773, 0.0412), (0.0810, 0.0395), (0.0819, 0.0387), (0.0840, 0.0377), (0.0857, 0.0373), (0.0875, 0.0361), (0.0903, 0.0356), (0.0919, 0.0346), (0.0966, 0.0334), (0.0978, 0.0326), (0.0993, 0.0327), (0.1011, 0.0319), (0.1035, 0.0316), (0.1040, 0.0311), (0.1040, -0.0001), (0.1023, -0.0043), (0.1011, -0.0050), (0.0985, -0.0050), (0.0966, -0.0056), (0.0925, -0.0061), (0.0903, -0.0072), (0.0878, -0.0075), (0.0833, -0.0098), (0.0812, -0.0102), (0.0782, -0.0119), (0.0755, -0.0124), (0.0719, -0.0143), (0.0669, -0.0161), (0.0652, -0.0173), (0.0638, -0.0174), (0.0628, -0.0180), (0.0593, -0.0189), (0.0586, -0.0189), (0.0580, -0.0185), (0.0578, -0.0173), (0.0588, -0.0154), (0.0590, -0.0136), (0.0600, -0.0126), (0.0598, -0.0122), (0.0590, -0.0122), (0.0577, -0.0134), (0.0571, -0.0127), (0.0566, -0.0126), (0.0534, -0.0135), (0.0505, -0.0158), (0.0492, -0.0186), (0.0495, -0.0200), (0.0502, -0.0207), (0.0512, -0.0211), (0.0517, -0.0218), (0.0520, -0.0236), (0.0515, -0.0242), (0.0499, -0.0250), (0.0487, -0.0250), (0.0456, -0.0261), (0.0432, -0.0262), (0.0399, -0.0275), (0.0386, -0.0276), (0.0367, -0.0283), (0.0344, -0.0299), (0.0331, -0.0296), (0.0318, -0.0304), (0.0308, -0.0305), (0.0289, -0.0314), (0.0268, -0.0317), (0.0255, -0.0327), (0.0215, -0.0345), (0.0204, -0.0343), (0.0196, -0.0334), (0.0207, -0.0288), (0.0240, -0.0238), (0.0252, -0.0228), (0.0261, -0.0213), (0.0279, -0.0193), (0.0283, -0.0178), (0.0321, -0.0141), (0.0331, -0.0114), (0.0331, -0.0095), (0.0324, -0.0079), (0.0303, -0.0054), (0.0261, -0.0024), (0.0186, -0.0015), (0.0171, -0.0021), (0.0154, -0.0022), (0.0141, -0.0028), (0.0116, -0.0032), (0.0103, -0.0040), (0.0086, -0.0043), (0.0074, -0.0053), (0.0060, -0.0058), (0.0027, -0.0088), (0.0516, -0.0075), (0.0523, -0.0081), (0.0532, -0.0078), (0.0546, -0.0080), (0.0555, -0.0074), (0.0569, -0.0075), (0.0593, -0.0061), (0.0609, -0.0060), (0.0641, -0.0039), (0.0659, -0.0019), (0.0661, -0.0013), (0.0656, -0.0012), (0.0632, -0.0035), (0.0603, -0.0050), (0.0572, -0.0058), (0.0554, -0.0068), (0.0525, -0.0068), (0.0401, 0.0142), (0.0408, 0.0153), (0.0427, 0.0162), (0.0435, 0.0163), (0.0445, 0.0157), (0.0454, 0.0157), (0.0502, 0.0173), (0.0515, 0.0183), (0.0543, 0.0228), (0.0556, 0.0273), (0.0558, 0.0313), (0.0548, 0.0325), (0.0547, 0.0332), (0.0552, 0.0333), (0.0561, 0.0322), (0.0567, 0.0325), (0.0567, 0.0330), (0.0551, 0.0361), (0.0520, 0.0393), (0.0504, 0.0401), (0.0486, 0.0417), (0.0436, 0.0433), (0.0398, 0.0431), (0.0368, 0.0434), (0.0338, 0.0425), (0.0295, 0.0398), (0.0277, 0.0382), (0.0229, 0.0328), (0.0217, 0.0287), (0.0222, 0.0285), (0.0257, 0.0330), (0.0307, 0.0377), (0.0341, 0.0389), (0.0354, 0.0389), (0.0389, 0.0400), (0.0400, 0.0399), (0.0436, 0.0387), (0.0480, 0.0355), (0.0504, 0.0315), (0.0501, 0.0293), (0.0489, 0.0278), (0.0479, 0.0273), (0.0463, 0.0272), (0.0438, 0.0286), (0.0407, 0.0284), (0.0391, 0.0279), (0.0368, 0.0253), (0.0361, 0.0207), (0.0370, 0.0191), (0.0370, 0.0181), (0.0378, 0.0161), (0.0361, 0.0005), (0.0373, 0.0000), (0.0384, -0.0010), (0.0394, 0.0001), (0.0407, 0.0003), (0.0412, 0.0020), (0.0431, 0.0030), (0.0433, 0.0035), (0.0430, 0.0038), (0.0395, 0.0040), (0.0372, 0.0024), (0.0362, 0.0012), (0.0316, 0.0121), (0.0307, 0.0140), (0.0276, 0.0166), (0.0251, 0.0173), (0.0236, 0.0170), (0.0223, 0.0177), (0.0211, 0.0178), (0.0165, 0.0171), (0.0146, 0.0158), (0.0129, 0.0152), (0.0121, 0.0143), (0.0105, 0.0137), (0.0108, 0.0125), (0.0112, 0.0123), (0.0129, 0.0139), (0.0139, 0.0136), (0.0160, 0.0138), (0.0169, 0.0144), (0.0173, 0.0153), (0.0176, 0.0153), (0.0178, 0.0134), (0.0187, 0.0138), (0.0210, 0.0136), (0.0220, 0.0142), (0.0226, 0.0142), (0.0241, 0.0132), (0.0247, 0.0121), (0.0255, 0.0116), (0.0272, 0.0122), (0.0289, 0.0116), (0.0312, 0.0117)],
     "rings": [130, 17, 51, 12, 31],
     "tris": [(118, 130, 146), (118, 146, 145), (118, 145, 144), (118, 144, 143), (118, 143, 142), (118, 142, 141), (137, 136, 135), (135, 134, 133), (133, 132, 131), (131, 130, 118), (131, 118, 117), (131, 117, 116), (131, 116, 115), (131, 115, 114), (131, 114, 113), (131, 113, 112), (131, 112, 111), (131, 111, 110), (131, 110, 109), (131, 109, 108), (131, 108, 107), (131, 107, 106), (131, 106, 105), (131, 105, 104), (131, 104, 103), (131, 103, 102), (131, 102, 101), (131, 101, 100), (131, 100, 99), (131, 99, 98), (131, 98, 97), (131, 97, 96), (131, 96, 95), (131, 95, 94), (131, 94, 93), (92, 91, 90), (92, 90, 89), (92, 89, 88), (92, 88, 87), (92, 87, 86), (92, 86, 85), (92, 85, 84), (80, 79, 78), (76, 75, 74), (74, 73, 72), (74, 72, 71), (74, 71, 70), (74, 70, 69), (74, 69, 68), (74, 68, 67), (74, 67, 66), (74, 66, 65), (74, 65, 64), (74, 64, 63), (74, 63, 62), (62, 61, 60), (60, 59, 58), (58, 57, 56), (56, 55, 54), (56, 54, 53), (56, 53, 52), (56, 52, 51), (56, 51, 50), (56, 50, 49), (56, 49, 48), (56, 48, 47), (56, 47, 46), (56, 46, 45), (56, 45, 44), (56, 44, 43), (56, 43, 42), (56, 42, 41), (56, 41, 40), (56, 40, 39), (56, 39, 38), (56, 38, 37), (56, 37, 36), (56, 36, 35), (56, 35, 34), (56, 34, 33), (56, 33, 32), (56, 32, 31), (56, 31, 30), (56, 30, 29), (29, 28, 27), (29, 27, 26), (29, 26, 25), (25, 24, 23), (25, 23, 22), (25, 22, 21), (25, 21, 20), (25, 20, 19), (25, 19, 18), (25, 18, 17), (17, 16, 15), (17, 15, 14), (17, 14, 13), (17, 13, 12), (12, 11, 10), (7, 6, 5), (7, 5, 4), (7, 4, 3), (3, 2, 1), (3, 1, 0), (3, 0, 221), (3, 221, 175), (170, 169, 168), (167, 166, 165), (161, 160, 159), (161, 159, 158), (161, 158, 157), (161, 157, 156), (151, 150, 149), (151, 149, 148), (151, 148, 147), (196, 195, 194), (190, 189, 188), (190, 188, 187), (190, 187, 186), (190, 186, 185), (190, 185, 184), (190, 184, 183), (190, 183, 182), (190, 182, 181), (190, 181, 180), (190, 180, 179), (190, 179, 178), (190, 178, 177), (190, 177, 176), (176, 175, 221), (176, 221, 220), (176, 220, 219), (176, 219, 218), (176, 218, 217), (176, 217, 216), (176, 216, 215), (176, 215, 214), (176, 214, 213), (176, 213, 212), (176, 212, 211), (239, 238, 237), (236, 235, 234), (236, 234, 233), (236, 233, 232), (236, 232, 231), (236, 231, 230), (230, 229, 228), (230, 228, 227), (230, 227, 226), (230, 226, 225), (225, 224, 223), (222, 221, 0), (222, 0, 129), (222, 129, 128), (222, 128, 127), (222, 127, 126), (222, 126, 125), (222, 125, 124), (222, 124, 123), (222, 123, 122), (222, 122, 121), (222, 121, 120), (120, 198, 209), (120, 209, 208), (120, 208, 207), (204, 203, 202), (202, 201, 200), (200, 199, 198), (200, 198, 120), (200, 120, 119), (200, 119, 118), (200, 118, 141), (93, 92, 84), (93, 84, 83), (81, 80, 78), (76, 74, 62), (76, 62, 60), (76, 60, 58), (58, 56, 29), (58, 29, 25), (8, 7, 3), (8, 3, 175), (162, 161, 156), (152, 151, 147), (191, 190, 176), (237, 236, 230), (237, 230, 225), (237, 225, 223), (223, 222, 120), (223, 120, 207), (223, 207, 206), (202, 200, 141), (131, 93, 83), (131, 83, 82), (131, 82, 81), (131, 81, 78), (131, 78, 77), (77, 76, 58), (9, 8, 175), (9, 175, 174), (9, 174, 173), (192, 191, 176), (237, 223, 206), (204, 202, 141), (133, 131, 77), (133, 77, 58), (10, 9, 173), (193, 192, 176), (193, 176, 211), (193, 211, 210), (239, 237, 206), (205, 204, 141), (205, 141, 140), (135, 133, 58), (12, 10, 173), (12, 173, 172), (12, 172, 171), (12, 171, 170), (194, 193, 210), (240, 239, 206), (206, 205, 140), (137, 135, 58), (17, 12, 170), (17, 170, 168), (17, 168, 167), (17, 167, 165), (17, 165, 164), (196, 194, 210), (210, 240, 206), (210, 206, 140), (138, 137, 58), (25, 17, 164), (25, 164, 163), (25, 163, 162), (25, 162, 156), (25, 156, 155), (25, 155, 154), (197, 196, 210), (139, 138, 58), (58, 25, 154), (58, 154, 153), (58, 153, 152), (58, 152, 147), (147, 197, 210), (147, 210, 140), (140, 139, 58), (140, 58, 147)]},
]
GUARD_SWIRLS = [
    {"pts": [(0.0767, 0.0276), (0.0759, 0.0282), (0.0757, 0.0294), (0.0766, 0.0321), (0.0769, 0.0354), (0.0776, 0.0366), (0.0788, 0.0368), (0.0793, 0.0366), (0.0800, 0.0359), (0.0801, 0.0346), (0.0785, 0.0290), (0.0779, 0.0280), (0.0772, 0.0276)],
     "rings": [13],
     "tris": [(1, 0, 12), (1, 12, 11), (1, 11, 10), (1, 10, 9), (1, 9, 8), (1, 8, 7), (1, 7, 6), (1, 6, 5), (5, 4, 3), (3, 2, 1), (3, 1, 5)]},
    {"pts": [(0.0144, 0.0205), (0.0146, 0.0217), (0.0155, 0.0226), (0.0163, 0.0229), (0.0175, 0.0227), (0.0191, 0.0234), (0.0202, 0.0233), (0.0222, 0.0226), (0.0227, 0.0222), (0.0229, 0.0217), (0.0227, 0.0210), (0.0221, 0.0205), (0.0195, 0.0197), (0.0176, 0.0197), (0.0160, 0.0194), (0.0149, 0.0198)],
     "rings": [16],
     "tris": [(1, 0, 15), (1, 15, 14), (1, 14, 13), (1, 13, 12), (1, 12, 11), (1, 11, 10), (1, 10, 9), (1, 9, 8), (1, 8, 7), (1, 7, 6), (6, 5, 4), (4, 3, 2), (4, 2, 1), (4, 1, 6)]},
    {"pts": [(0.0404, 0.0120), (0.0402, 0.0125), (0.0404, 0.0140), (0.0410, 0.0152), (0.0427, 0.0160), (0.0437, 0.0160), (0.0445, 0.0155), (0.0454, 0.0155), (0.0475, 0.0161), (0.0511, 0.0176), (0.0523, 0.0190), (0.0545, 0.0227), (0.0545, 0.0234), (0.0552, 0.0246), (0.0559, 0.0282), (0.0565, 0.0287), (0.0575, 0.0287), (0.0584, 0.0281), (0.0584, 0.0245), (0.0578, 0.0210), (0.0559, 0.0172), (0.0550, 0.0161), (0.0528, 0.0141), (0.0509, 0.0127), (0.0494, 0.0119), (0.0467, 0.0112), (0.0430, 0.0108), (0.0410, 0.0115)],
     "rings": [28],
     "tris": [(1, 0, 27), (1, 27, 26), (1, 26, 25), (1, 25, 24), (1, 24, 23), (1, 23, 22), (1, 22, 21), (1, 21, 20), (20, 19, 18), (20, 18, 17), (20, 17, 16), (20, 16, 15), (20, 15, 14), (20, 14, 13), (20, 13, 12), (20, 12, 11), (20, 11, 10), (20, 10, 9), (20, 9, 8), (20, 8, 7), (6, 5, 4), (6, 4, 3), (6, 3, 2), (6, 2, 1), (1, 20, 7), (1, 7, 6)]},
    {"pts": [(0.0343, 0.0116), (0.0343, 0.0105), (0.0339, 0.0094), (0.0339, 0.0081), (0.0336, 0.0073), (0.0325, 0.0056), (0.0317, 0.0036), (0.0297, 0.0009), (0.0286, 0.0005), (0.0270, 0.0006), (0.0253, 0.0003), (0.0236, 0.0013), (0.0208, 0.0018), (0.0193, 0.0027), (0.0183, 0.0037), (0.0177, 0.0055), (0.0177, 0.0072), (0.0183, 0.0098), (0.0180, 0.0102), (0.0164, 0.0108), (0.0156, 0.0108), (0.0138, 0.0100), (0.0103, 0.0093), (0.0046, 0.0064), (0.0037, 0.0064), (0.0031, 0.0070), (0.0031, 0.0080), (0.0044, 0.0101), (0.0070, 0.0128), (0.0084, 0.0137), (0.0093, 0.0136), (0.0106, 0.0126), (0.0108, 0.0122), (0.0112, 0.0121), (0.0125, 0.0134), (0.0130, 0.0136), (0.0142, 0.0134), (0.0168, 0.0138), (0.0180, 0.0132), (0.0187, 0.0136), (0.0210, 0.0134), (0.0223, 0.0139), (0.0234, 0.0135), (0.0240, 0.0130), (0.0245, 0.0120), (0.0255, 0.0114), (0.0270, 0.0119), (0.0279, 0.0119), (0.0289, 0.0114), (0.0299, 0.0116), (0.0312, 0.0115), (0.0318, 0.0120), (0.0319, 0.0130), (0.0325, 0.0134), (0.0329, 0.0134), (0.0337, 0.0129)],
     "rings": [56],
     "tris": [(1, 0, 55), (1, 55, 54), (1, 54, 53), (1, 53, 52), (1, 52, 51), (1, 51, 50), (1, 50, 49), (1, 49, 48), (48, 47, 46), (48, 46, 45), (44, 43, 42), (44, 42, 41), (44, 41, 40), (44, 40, 39), (44, 39, 38), (38, 37, 36), (36, 35, 34), (36, 34, 33), (32, 31, 30), (32, 30, 29), (32, 29, 28), (32, 28, 27), (32, 27, 26), (32, 26, 25), (32, 25, 24), (32, 24, 23), (32, 23, 22), (32, 22, 21), (32, 21, 20), (17, 16, 15), (17, 15, 14), (17, 14, 13), (17, 13, 12), (17, 12, 11), (17, 11, 10), (17, 10, 9), (17, 9, 8), (17, 8, 7), (17, 7, 6), (17, 6, 5), (17, 5, 4), (17, 4, 3), (17, 3, 2), (17, 2, 1), (17, 1, 48), (17, 48, 45), (17, 45, 44), (17, 44, 38), (38, 36, 33), (33, 32, 20), (33, 20, 19), (18, 17, 38), (38, 33, 19), (38, 19, 18)]},
    {"pts": [(0.0670, -0.0026), (0.0664, -0.0022), (0.0661, -0.0009), (0.0664, 0.0000), (0.0674, 0.0012), (0.0675, 0.0025), (0.0680, 0.0037), (0.0679, 0.0042), (0.0675, 0.0046), (0.0669, 0.0047), (0.0647, 0.0034), (0.0634, 0.0032), (0.0628, 0.0037), (0.0628, 0.0044), (0.0634, 0.0052), (0.0655, 0.0065), (0.0677, 0.0083), (0.0701, 0.0107), (0.0719, 0.0130), (0.0726, 0.0146), (0.0733, 0.0171), (0.0739, 0.0175), (0.0747, 0.0173), (0.0751, 0.0167), (0.0751, 0.0139), (0.0746, 0.0116), (0.0739, 0.0099), (0.0738, 0.0081), (0.0727, 0.0049), (0.0707, 0.0014), (0.0693, -0.0002), (0.0687, -0.0017), (0.0680, -0.0024)],
     "rings": [33],
     "tris": [(1, 0, 32), (1, 32, 31), (1, 31, 30), (1, 30, 29), (1, 29, 28), (1, 28, 27), (1, 27, 26), (1, 26, 25), (1, 25, 24), (1, 24, 23), (1, 23, 22), (1, 22, 21), (21, 20, 19), (21, 19, 18), (15, 14, 13), (15, 13, 12), (15, 12, 11), (15, 11, 10), (15, 10, 9), (15, 9, 8), (6, 5, 4), (4, 3, 2), (4, 2, 1), (4, 1, 21), (4, 21, 18), (4, 18, 17), (16, 15, 8), (16, 8, 7), (16, 7, 6), (6, 4, 17), (6, 17, 16)]},
    {"pts": [(0.0337, -0.0034), (0.0340, -0.0019), (0.0344, -0.0012), (0.0365, -0.0004), (0.0374, -0.0005), (0.0382, -0.0012), (0.0388, -0.0010), (0.0394, -0.0002), (0.0409, 0.0002), (0.0413, 0.0009), (0.0413, 0.0017), (0.0418, 0.0022), (0.0435, 0.0031), (0.0434, 0.0037), (0.0439, 0.0044), (0.0448, 0.0046), (0.0459, 0.0043), (0.0481, 0.0030), (0.0494, 0.0015), (0.0500, 0.0003), (0.0501, -0.0011), (0.0498, -0.0030), (0.0490, -0.0046), (0.0490, -0.0051), (0.0504, -0.0065), (0.0506, -0.0070), (0.0523, -0.0083), (0.0532, -0.0080), (0.0546, -0.0082), (0.0556, -0.0076), (0.0569, -0.0077), (0.0593, -0.0063), (0.0609, -0.0062), (0.0622, -0.0054), (0.0632, -0.0056), (0.0635, -0.0061), (0.0635, -0.0066), (0.0632, -0.0073), (0.0625, -0.0079), (0.0614, -0.0082), (0.0596, -0.0093), (0.0563, -0.0104), (0.0543, -0.0117), (0.0524, -0.0120), (0.0501, -0.0128), (0.0492, -0.0128), (0.0482, -0.0123), (0.0474, -0.0123), (0.0450, -0.0130), (0.0438, -0.0124), (0.0435, -0.0117), (0.0434, -0.0106), (0.0432, -0.0102), (0.0427, -0.0099), (0.0411, -0.0101), (0.0396, -0.0095), (0.0375, -0.0097), (0.0366, -0.0092), (0.0345, -0.0069), (0.0338, -0.0051)],
     "rings": [60],
     "tris": [(1, 0, 59), (1, 59, 58), (1, 58, 57), (1, 57, 56), (1, 56, 55), (1, 55, 54), (1, 54, 53), (1, 53, 52), (51, 50, 49), (51, 49, 48), (51, 48, 47), (51, 47, 46), (46, 45, 44), (46, 44, 43), (46, 43, 42), (46, 42, 41), (46, 41, 40), (46, 40, 39), (39, 38, 37), (39, 37, 36), (39, 36, 35), (39, 35, 34), (39, 34, 33), (39, 33, 32), (39, 32, 31), (39, 31, 30), (39, 30, 29), (39, 29, 28), (28, 27, 26), (25, 24, 23), (22, 21, 20), (22, 20, 19), (22, 19, 18), (22, 18, 17), (22, 17, 16), (22, 16, 15), (22, 15, 14), (22, 14, 13), (22, 13, 12), (22, 12, 11), (22, 11, 10), (22, 10, 9), (22, 9, 8), (22, 8, 7), (22, 7, 6), (22, 6, 5), (5, 4, 3), (5, 3, 2), (5, 2, 1), (5, 1, 52), (52, 51, 46), (52, 46, 39), (52, 39, 28), (52, 28, 26), (52, 26, 25), (52, 25, 23), (52, 23, 22), (52, 22, 5)]},
]

if __name__ == "__main__":
    main()
