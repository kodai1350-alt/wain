"""
VRChat 用の刀 (雷電将軍の元素爆発の刀「夢想の一太刀」風, ファンメイド) を作成して
FBX で書き出す Blender スクリプト (Blender 5.1 で動作確認)。

使い方 (どちらでも可):
  A) Blender の Scripting タブでこのファイルを開いて「スクリプト実行」(Alt+P)
  B) コマンドライン:  blender -b -P make_katana.py -- --out <出力フォルダ>

作成されるもの:
  - Katana : 刀本体 (刃・三つ巴の紋・ヒレ・鍔・柄・金具・柄頭の炎を 1 メッシュ)
      マテリアル 2 個: Katana_Blade (光る部分) / Katana_Hilt (柄と金具)
  - Grip   : 握る位置の目印 (空のオブジェクト、Katana の子)
  - Tip    : 切っ先の目印 (空のオブジェクト、Katana の子)
  - Katana.fbx と Katana_Atlas.png を出力フォルダに書き出し

仕様:
  - 刃の反り・三つ巴の紋・紫のトゲ・鍔は参考画像 (ゲーム画面) を測って合わせています
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
UV_EMBLEM = (0.0, 0.78, 0.20, 0.98)
UV_WHITE = (0.22, 0.78, 0.30, 0.98)
UV_TSUBA = (0.32, 0.78, 0.52, 0.98)
UV_FLAME = (0.54, 0.78, 0.64, 0.98)
UV_FIN = (0.66, 0.78, 0.86, 0.98)
UV_PAD = 0.002
UV_DARK = (0.93, 0.88)        # アトラスの空き部分 (濃い紫一色)。紋の台座に使う

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
    ts = [0.0] + [tk * (i / 44) for i in range(1, 45)]
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


def build_habaki(b):
    """刃の付け根の鎺 (はばき)。参考画像どおり濃い紫。"""
    rings = []
    for t, grow in ((0.0, 0.0024), (0.032, 0.0016)):
        w, th = blade_profile(t)
        _, n = frame(t)
        p = spine(t)
        hx = th / 2 + grow
        rings.append([p - n * grow + X * hx, p + n * (w + grow) + X * hx * 0.55,
                      p + n * (w + grow) - X * hx * 0.55, p - n * grow - X * hx])
    b.rings(rings, lambda i, j: map_rect(UV_FIN, j / 4, i), MAT_BLADE,
            cap_start=lambda co: map_rect(UV_FIN, 0.5, 0.5), cap_end=lambda co: map_rect(UV_FIN, 0.5, 0.5))


def tomoe_outline(R, rot, sweep=math.radians(100), n=18):
    """巴 1 つの外形 (2D)。丸い頭の外側半分から、外周に沿って細い尾が伸びてとがる。"""
    hd, hr = R * 0.50, R * 0.30                   # 頭の円の中心までの距離と半径
    hx, hy = hd * math.cos(rot), hd * math.sin(rot)
    # 尾の内側の線の始まり: 頭の円の「進む向き」側の点
    fx, fy = hx - hr * math.sin(rot), hy + hr * math.cos(rot)
    rf, af = math.hypot(fx, fy), rot + math.atan2(hr, hd)   # 角度は rot 基準で (一周の巻き戻りを防ぐ)
    pts = []
    for i in range(n + 1):                        # 外側の線 (頭の外側 → 尾の先)
        t = i / n
        a = rot + t * sweep
        r = lerp(hd + hr, R * 0.97, t ** 0.7)
        pts.append((r * math.cos(a), r * math.sin(a)))
    for i in range(n - 1, -1, -1):                # 内側の線 (尾の先 → 頭の前の点)
        t = i / n
        a = lerp(af, rot + sweep, t)
        r = lerp(rf, R * 0.97, t ** 0.8)
        pts.append((r * math.cos(a), r * math.sin(a)))
    for i in range(1, n * 2):                     # 頭の円 (前 → 内側 → 後ろ → 外側)
        phi = rot + math.pi / 2 + 1.5 * math.pi * i / (n * 2)
        pts.append((hx + hr * math.cos(phi), hy + hr * math.sin(phi)))
    return pts


def build_emblem(b):
    """刃の付け根の三つ巴の紋。外側の円はなく、3 つの巴が刃の幅からはみ出す。"""
    t0 = 0.052
    tan, n = frame(t0)
    c = spine(t0) + n * (BLADE_W * 0.50)
    R = BLADE_W * 0.80
    half = BLADE_T / 2 + 0.0020

    def to3d(a, bb, d):
        return c + tan * a + n * bb + X * d

    # 巴の後ろの濃い紫の台座 (巴より少し薄い円盤) — 白い巴の形がはっきり見えるように
    seg = 28
    disc = [(R * 1.02 * math.cos(math.tau * j / seg), R * 1.02 * math.sin(math.tau * j / seg)) for j in range(seg)]
    b.prism(disc, to3d, -(half - 0.0008), half - 0.0008,
            lambda a, bb: UV_DARK, lambda s_, t_: UV_DARK, MAT_BLADE)
    for i in range(3):
        outline = tomoe_outline(R, math.radians(90 + 120 * i))
        b.prism(outline, to3d, -half, half,
                lambda a, bb: map_rect(UV_WHITE, 0.5, 0.5),
                lambda s_, t_: map_rect(UV_WHITE, 0.5, 0.5), MAT_BLADE)


def build_fin(b):
    """紋の峰側から柄の方へ斜め (約 40 度) に伸びる、細長くとがった濃い紫のトゲ。"""
    L, Wd = BLADE_W * 2.3, BLADE_W * 0.36
    ang = math.radians(40)
    # トゲの付け根 (紋の峰側) からの (柄の方へ, 峰の外へ) の 2D 外形
    shape = [(0.0, -Wd * 0.5), (L * 0.35, -Wd * 0.55), (L, 0.0), (L * 0.35, Wd * 0.45), (0.0, Wd * 0.5)]
    t0 = 0.050
    tan, n = frame(t0)
    base = spine(t0) + n * (BLADE_W * 0.15)
    axis = (-tan * math.cos(ang) - n * math.sin(ang))   # 柄の方へ、峰の外へ
    side = tan * math.sin(ang) - n * math.cos(ang)

    def to3d(a, bb, d):
        return base + axis * a + side * bb + X * d

    b.prism(shape, to3d, -0.0016, 0.0016,
            lambda a, bb: map_rect(UV_FIN, a / L, 0.5 + bb / Wd),
            lambda s_, t_: map_rect(UV_FIN, s_, t_), MAT_BLADE)


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
    b.rings(rings, lambda i, j: map_rect(UV_FIN, j / seg, i / 2), MAT_BLADE)
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
    build_habaki(b)
    build_emblem(b)
    build_fin(b)
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


if __name__ == "__main__":
    main()
