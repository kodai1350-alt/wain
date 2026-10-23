"""
VRChat 用の刀 (雷電将軍の元素爆発の刀「夢想の一太刀」風, ファンメイド) を作成して
FBX で書き出す Blender スクリプト (Blender 5.1 で動作確認)。

使い方 (どちらでも可):
  A) Blender の Scripting タブでこのファイルを開いて「スクリプト実行」(Alt+P)
  B) コマンドライン:  blender -b -P make_katana.py -- --out <出力フォルダ>

作成されるもの:
  - Katana : 刀本体 (刃・付け根の飾り板と白い巴・鍔・柄・鋲・赤い紐を 1 メッシュ)
      マテリアル 2 個: Katana_Blade (光る部分) / Katana_Hilt (鍔・柄)
  - Grip   : 握る位置の目印 (空のオブジェクト、Katana の子)
  - Tip    : 切っ先の目印 (空のオブジェクト、Katana の子)
  - Katana.fbx と Katana_Atlas.png を出力フォルダに書き出し

仕様:
  - 刃の反りは参考画像 (ゲーム画面) を測って合わせています
  - 刃の付け根の飾り板 (トゲ・巻き・抜け) と白い巴のかけら、金色の楕円の鍔、柄 (飾り板のトゲ・
    金の線・X 字に巻いた赤い紐・鋲・柄頭) は、参考画像 (コスプレ用の刀の写真) を測ってなぞった形
  - VRChat のアバター (身長 1.4〜1.6m 前後) に合わせた大きさ: 全長 約 1.04m
    (刃 80cm・柄 24cm)。SCALE で全体の大きさを変えられます
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
SCALE = 1.0            # 全体の大きさ (1.0 = 全長 約 1.04m)
BLADE_LEN = 0.80       # 刃の長さ (m)
HANDLE_LEN = 0.24      # 柄の長さ (m, 鍔の表から柄頭まで)。参考画像の写真の比率
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
# 鍔: 参考画像の写真を測った金色の楕円
TSUBA_SIZE = (0.112, 0.084)   # (峰〜刃の方向, 厚みの方向) の直径 (m)
TSUBA_T = 0.0055              # 鍔の厚み (m)
TSUBA_OFFSET = -0.004         # 刃の幅の中心から峰側へずらす量 (m, 写真では峰側が少し長い)
# 柄に巻いた赤い紐 (参考画像の写真を測った位置)
CORD_R = 0.0018               # 紐の太さ (半径, m)
CORD_U0 = 0.366               # 表の最初の X の位置 (柄の 0 = 鍔の裏 → 1 = 柄頭)
CORD_PITCH_U = 0.086          # X の間隔 (= 1 巻きで進む長さ)
CORD_CROSSINGS = 3            # 表の X の数
OBJECT_NAME = "Katana"
BLADE_MATERIAL = "Katana_Blade"   # 刃・付け根の飾り板・白い巴 (光る)
HILT_MATERIAL = "Katana_Hilt"     # 鍔・柄・鋲・紐 (金の線・稲妻・星・象嵌がほのかに光る)

# アトラスのレイアウト (make_katana_texture.py と一致させる)
UV_BLADE = (0.0, 0.0, 1.0, 0.36)
UV_HANDLE = (0.0, 0.38, 1.0, 0.66)    # 柄 (横 = 鍔側→柄頭, 縦 = 一周: 0 = 峰, 0.25 = 表, 0.5 = 刃側, 0.75 = 裏)
UV_GUARD = (0.0, 0.78, 0.20, 0.98)    # 刃の付け根の飾り板 (濃い紫と薄い紫の炎の模様)
UV_WHITE = (0.22, 0.78, 0.30, 0.98)
UV_TSUBA = (0.32, 0.78, 0.52, 0.98)
UV_STUD = (0.54, 0.78, 0.64, 0.98)     # 柄の白い鋲
UV_CORD = (0.66, 0.78, 0.76, 0.98)     # 柄に巻いた赤い紐 (横 = 紐の一周, 縦 = 紐の長さ)
UV_PAD = 0.002

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


def make_material(name, albedo, normal, roughness, emission_img=None, emission=0.0, metallic=0.0):
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
    bsdf.inputs["Metallic"].default_value = metallic
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
    """金色の楕円の鍔 (参考画像の写真どおり)。表と裏のふちが少し盛り上がる (耳)。"""
    seg = 40
    A, B = TSUBA_SIZE[0] / 2, TSUBA_SIZE[1] / 2        # 峰〜刃の方向 / 厚みの方向の半径
    _, n = frame(0.0)
    c = spine(0.0) + n * (BLADE_W / 2 + TSUBA_OFFSET)
    T = TSUBA_T
    # (大きさ, 鍔からの深さ): 表の面 → 耳 → 外周 → 耳 → 裏の面
    prof = ((0.86, -0.0006), (0.93, 0.0), (1.0, -0.0012), (1.0, -T + 0.0012), (0.93, -T), (0.86, -T + 0.0006))
    rings = [[c + X * (B * s * math.cos(a)) + n * (A * s * math.sin(a)) + Vector((0.0, 0.0, d))
              for a in (math.tau * j / seg for j in range(seg))] for s, d in prof]

    def face_uv(s, j):
        a = math.tau * j / seg
        return map_rect(UV_TSUBA, 0.5 + 0.5 * s * math.cos(a), 0.5 + 0.5 * s * math.sin(a))

    vs =[[b.bm.verts.new(p) for p in ring] for ring in rings]
    for i in range(len(vs) - 1):
        for j in range(seg):
            k = (j + 1) % seg
            quad = (vs[i][j], vs[i][k], vs[i + 1][k], vs[i + 1][j])
            if i == 2:      # 外周の側面は耳と同じ磨いた金
                uvs = [face_uv(0.96, j), face_uv(0.96, j + 1), face_uv(0.97, j + 1), face_uv(0.97, j)]
            else:
                uvs = [face_uv(prof[i][0], j), face_uv(prof[i][0], j + 1),
                       face_uv(prof[i + 1][0], j + 1), face_uv(prof[i + 1][0], j)]
            b.face(quad, uvs, MAT_HILT)
    b.face(list(reversed(vs[0])), [face_uv(prof[0][0], j) for j in reversed(range(seg))], MAT_HILT)
    b.face(vs[-1], [face_uv(prof[-1][0], j) for j in range(seg)], MAT_HILT)


def handle_ring(u):
    """柄の u (0 = 鍔の裏, 1 = 柄頭) での (中心, 刃の方向の半径, 厚みの方向の半径)。"""
    k = BLADE_W / 0.032
    rs = HANDLE_RINGS
    for (u0, l0, h0, x0), (u1, l1, h1, x1) in zip(rs, rs[1:]):
        if u <= u1:
            f = (u - u0) / max(1e-9, u1 - u0)
            lo, hi, rx = lerp(l0, l1, f), lerp(h0, h1, f), lerp(x0, x1, f)
            break
    else:
        _, lo, hi, rx = rs[-1]
    t = handle_t(u)
    _, n = frame(t)
    return spine(t) + n * ((lo + hi) / 2 * k), (hi - lo) / 2 * k, rx * k


def handle_t(u):
    return lerp(-TSUBA_T, -HANDLE_LEN, u)


def handle_point(u, a, lift=0.0):
    """柄の表面の点と外向きの向き。a = 周りの角度 (-90° = 峰, 0° = 表の中央, 90° = 刃側)。"""
    c, rn, rx = handle_ring(u)
    _, n = frame(handle_t(u))
    nrm = (X * (math.cos(a) / rx) + n * (math.sin(a) / rn)).normalized()
    return c + X * (rx * math.cos(a)) + n * (rn * math.sin(a)) + nrm * lift, nrm


def build_handle(b):
    """柄: 参考画像の写真の輪郭を測った断面 (鍔の近くの 2 枚の飾り板のトゲ・刃側の張り出し、
    少し太くなる柄頭と峰側の小さな鉤) を楕円のリングでつなぐ。模様 (金の線) はテクスチャ、赤い紐は build_cords。"""
    seg = 18
    rows = []
    for u, *_ in HANDLE_RINGS:
        c, rn, rx = handle_ring(u)
        _, n = frame(handle_t(u))
        rows.append([c + X * (rx * math.cos(a)) + n * (rn * math.sin(a))
                     for a in (-math.pi / 2 + math.tau * j / seg for j in range(seg))])
    us = [r[0] for r in HANDLE_RINGS]
    c_end, _, _ = handle_ring(1.0)
    tan, _ = frame(handle_t(1.0))
    b.rings(rows, lambda i, j: map_rect(UV_HANDLE, us[min(i, len(us) - 1)], j / seg), MAT_HILT,
            cap_end=c_end - tan * 0.002)


def build_studs(b):
    """鍔の近くの飾り板にある、白い丸い鋲 (表と裏に 2 つずつ)。"""
    r, hgt, seg = 0.0030, 0.0021, 8
    for u, deg in HANDLE_STUDS:
        for a in (math.radians(deg), math.pi - math.radians(deg)):     # 表と、裏 (左右対称)
            p, nrm = handle_point(u, a)
            tx = nrm.cross(Vector((0.0, 0.0, 1.0)))
            if tx.length < 1e-6:
                tx = nrm.cross(X)
            tx.normalize()
            ty = nrm.cross(tx)
            base = p - nrm * 0.0008                      # 少し埋めて浮きを防ぐ
            lat = ((1.0, 0.0), (0.82, 0.55), (0.45, 0.9))
            rings = [[base + (tx * math.cos(q) + ty * math.sin(q)) * (r * rr) + nrm * (hgt * hh + 0.0008)
                      for q in (math.tau * j / seg for j in range(seg))] for rr, hh in lat]

            def uv_of(i, j, lat=lat):
                q = math.tau * j / seg
                return map_rect(UV_STUD, 0.5 + 0.5 * lat[min(i, 2)][0] * math.cos(q), 0.5 + 0.5 * lat[min(i, 2)][0] * math.sin(q))
            b.rings(rings, uv_of, MAT_HILT, cap_end=base + nrm * (hgt + 0.0008))


def build_cords(b):
    """柄の中ほどに巻いた赤い紐 (参考画像の写真どおり、表と裏に X 字の交差ができる 2 本の逆巻きのらせん)。"""
    r, sides, steps = CORD_R, 6, 16                     # 紐の太さ・断面の角数・一周あたりの区切り
    turns = CORD_CROSSINGS                               # 表の交差の数 = 巻き数
    for sgn in (1, -1):                                  # 右巻きと左巻き
        n = steps * turns + 1
        a0, a1 = -math.pi, math.tau * (turns - 1) + math.pi
        pts = []
        for i in range(n):
            a = lerp(a0, a1, i / (n - 1))
            u = CORD_U0 + CORD_PITCH_U * a / math.tau
            if sgn < 0:                                  # 逆巻き: 同じ範囲を反対向きに回る
                u = CORD_U0 + CORD_PITCH_U * (turns - 1) - CORD_PITCH_U * a / math.tau
            p, nrm = handle_point(u, a, r * 0.55)
            pts.append((p, nrm))
        rings = []
        for i, (p, nrm) in enumerate(pts):
            q0, q1 = pts[max(0, i - 1)][0], pts[min(len(pts) - 1, i + 1)][0]
            tan = (q1 - q0).normalized()
            nn = (nrm - tan * nrm.dot(tan)).normalized()
            bn = tan.cross(nn)
            rings.append([p + (nn * math.cos(f) + bn * math.sin(f)) * r for f in (math.tau * k / sides for k in range(sides))])
        L = len(rings) - 1
        b.rings(rings, lambda i, j: map_rect(UV_CORD, j / sides, i / L), MAT_HILT,
                cap_start=pts[0][0] - pts[0][1] * r * 0.5, cap_end=pts[-1][0] - pts[-1][1] * r * 0.5)


def build_mesh():
    b = Builder()
    build_blade(b)
    build_guard(b)
    build_tsuba(b)
    build_handle(b)
    build_studs(b)
    build_cords(b)
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
    me.materials.append(make_material(BLADE_MATERIAL, albedo, normal, roughness=0.25, emission_img=emis, emission=1.5, metallic=0.35))
    me.materials.append(make_material(HILT_MATERIAL, albedo, normal, roughness=0.35, emission_img=emis, emission=1.0))
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


# ---------------------------------------------------------------- 柄の形のデータ
# 参考画像の写真の柄の輪郭を測った断面 (刃の幅 3.2cm 基準, 単位 m)。
# (u = 鍔の裏 0 → 柄頭 1, 峰側のふち, 刃側のふち (どちらも峰の線からの距離), 厚みの方向の半径)
HANDLE_RINGS = [
    (0.0001, -0.00237, 0.03566, 0.01321), (0.0262, -0.00237, 0.03082, 0.01321), (0.048, -0.00237, 0.02932, 0.01267),
    (0.0557, -0.00372, 0.0297, 0.01337), (0.0712, -0.00214, 0.03098, 0.01325), (0.0754, -0.0019, 0.03252, 0.01345),
    (0.0811, -0.00166, 0.03629, 0.01363), (0.0846, -0.0017, 0.03711, 0.01375), (0.1022, -0.00582, 0.03712, 0.01433),
    (0.1261, -0.01029, 0.03526, 0.01512), (0.1585, -0.01402, 0.03368, 0.01484), (0.1662, -0.01311, 0.03348, 0.01481),
    (0.1753, -0.00767, 0.03322, 0.01476), (0.1824, -0.00578, 0.03293, 0.01469), (0.2077, -0.00318, 0.03225, 0.01417),
    (0.2471, -0.00676, 0.03175, 0.01397), (0.257, -0.00702, 0.0324, 0.01422), (0.2696, -0.00605, 0.0321, 0.01407),
    (0.2823, -0.0035, 0.03156, 0.01384), (0.2978, -0.00275, 0.03165, 0.01376), (0.3062, -0.00278, 0.03223, 0.01401),
    (0.3351, -0.00212, 0.03111, 0.01329), (0.3562, -0.00171, 0.032, 0.01348), (0.3892, -0.00087, 0.03178, 0.01306),
    (0.4223, -0.00034, 0.03201, 0.01294), (0.4469, -0.00091, 0.03244, 0.01334), (0.461, -5e-05, 0.03174, 0.01271),
    (0.4969, -9e-05, 0.0327, 0.01312), (0.5265, 0.00064, 0.03234, 0.01268), (0.549, -0.0001, 0.03212, 0.01289),
    (0.5701, 0.00059, 0.03212, 0.01261), (0.5849, -0.00018, 0.03223, 0.01297), (0.5954, 0.00013, 0.03307, 0.01318),
    (0.6299, 0.00136, 0.03259, 0.01249), (0.6482, 0.00103, 0.03159, 0.01223), (0.6686, 0.00012, 0.03165, 0.01261),
    (0.6911, 0.0006, 0.03171, 0.01244), (0.7122, 7e-05, 0.03271, 0.01306), (0.7249, -0.00041, 0.0317, 0.01284),
    (0.7467, -0.00156, 0.03197, 0.01341), (0.7657, -0.00121, 0.03205, 0.0133), (0.7889, -0.00358, 0.03297, 0.01462),
    (0.8037, -0.00331, 0.03182, 0.01405), (0.8445, -0.00225, 0.03198, 0.01369), (0.8656, -0.0027, 0.03183, 0.01381),
    (0.8938, -0.00549, 0.03182, 0.01493), (0.936, -0.00412, 0.03131, 0.01417), (0.9564, -0.0048, 0.0304, 0.01408),
    (0.9627, -0.00573, 0.0298, 0.01421), (0.969, -0.00655, 0.02889, 0.01417), (0.9761, -0.00628, 0.02767, 0.01358),
    (0.9845, -0.00563, 0.02484, 0.01219), (0.988, -0.00537, 0.02265, 0.01121), (0.9901, -0.00527, 0.02023, 0.0102),
    (0.9923, -0.00523, 0.01617, 0.00856), (0.9965, -0.00522, 0.00595, 0.00447), (0.9993, -0.00509, 0.00209, 0.00287),
]
# 薄紫の鋲 (u, 周りの角度 °: 0 = 表の中央, 正 = 刃側)
HANDLE_STUDS = [(0.0715, 0.1), (0.1632, 15.2)]

# ---------------------------------------------------------------- 飾り板の形のデータ
# 参考画像からなぞった輪郭を、トゲの先などの角は残してなめらかな曲線に整えたもの
# (a = 鍔からの長さ, e = 峰からの距離, 単位 m, 刃の幅 3.2cm 基準)。
# pts = 点 (外周 → 穴の順)、rings = それぞれの点の数、tris = 面の三角形 (点の番号)
GUARD_PLATE = [
    {"pts": [(0.0015, -0.0092), (0.0015, -0.0087), (0.0018, -0.0074), (0.0020, -0.0060), (0.0017, -0.0045), (0.0016, -0.0019), (0.0016, 0.0225), (0.0017, 0.0252), (0.0019, 0.0262), (0.0021, 0.0272), (0.0019, 0.0285), (0.0015, 0.0297), (0.0019, 0.0300), (0.0036, 0.0295), (0.0044, 0.0295), (0.0050, 0.0297), (0.0061, 0.0299), (0.0110, 0.0302), (0.0124, 0.0304), (0.0134, 0.0306), (0.0145, 0.0311), (0.0157, 0.0317), (0.0159, 0.0320), (0.0160, 0.0323), (0.0161, 0.0339), (0.0164, 0.0341), (0.0167, 0.0338), (0.0169, 0.0332), (0.0174, 0.0324), (0.0176, 0.0322), (0.0179, 0.0321), (0.0180, 0.0320), (0.0188, 0.0305), (0.0195, 0.0305), (0.0199, 0.0322), (0.0203, 0.0330), (0.0209, 0.0337), (0.0215, 0.0345), (0.0249, 0.0392), (0.0270, 0.0417), (0.0289, 0.0436), (0.0308, 0.0451), (0.0328, 0.0464), (0.0349, 0.0474), (0.0372, 0.0481), (0.0383, 0.0483), (0.0399, 0.0486), (0.0415, 0.0487), (0.0426, 0.0488), (0.0450, 0.0486), (0.0473, 0.0482), (0.0488, 0.0478), (0.0499, 0.0473), (0.0520, 0.0463), (0.0539, 0.0450), (0.0557, 0.0434), (0.0568, 0.0423), (0.0576, 0.0414), (0.0590, 0.0395), (0.0599, 0.0378), (0.0603, 0.0367), (0.0607, 0.0352), (0.0610, 0.0341), (0.0612, 0.0326), (0.0614, 0.0302), (0.0612, 0.0289), (0.0609, 0.0277), (0.0610, 0.0275), (0.0613, 0.0273), (0.0615, 0.0275), (0.0620, 0.0282), (0.0622, 0.0282), (0.0624, 0.0278), (0.0623, 0.0275), (0.0618, 0.0269), (0.0624, 0.0265), (0.0639, 0.0269), (0.0647, 0.0273), (0.0659, 0.0276), (0.0668, 0.0279), (0.0681, 0.0286), (0.0696, 0.0297), (0.0705, 0.0305), (0.0716, 0.0316), (0.0731, 0.0334), (0.0741, 0.0350), (0.0756, 0.0378), (0.0763, 0.0388), (0.0767, 0.0392), (0.0772, 0.0395), (0.0777, 0.0397), (0.0783, 0.0398), (0.0788, 0.0398), (0.0795, 0.0397), (0.0808, 0.0393), (0.0857, 0.0372), (0.0883, 0.0362), (0.0927, 0.0346), (0.0993, 0.0324), (0.1007, 0.0319), (0.1016, 0.0314), (0.1024, 0.0313), (0.1034, 0.0313), (0.1040, 0.0312), (0.1036, 0.0296), (0.1035, 0.0288), (0.1037, 0.0278), (0.1039, 0.0267), (0.1040, 0.0240), (0.1040, 0.0076), (0.1039, 0.0032), (0.1037, 0.0013), (0.1033, -0.0005), (0.1029, -0.0015), (0.1025, -0.0022), (0.1021, -0.0027), (0.1017, -0.0032), (0.1006, -0.0041), (0.1000, -0.0044), (0.0990, -0.0049), (0.0972, -0.0054), (0.0918, -0.0067), (0.0881, -0.0078), (0.0855, -0.0088), (0.0755, -0.0127), (0.0657, -0.0168), (0.0642, -0.0173), (0.0628, -0.0177), (0.0618, -0.0178), (0.0609, -0.0179), (0.0591, -0.0187), (0.0585, -0.0189), (0.0581, -0.0186), (0.0582, -0.0181), (0.0586, -0.0171), (0.0590, -0.0164), (0.0587, -0.0150), (0.0587, -0.0142), (0.0589, -0.0138), (0.0592, -0.0133), (0.0599, -0.0126), (0.0598, -0.0123), (0.0591, -0.0123), (0.0580, -0.0131), (0.0579, -0.0133), (0.0576, -0.0133), (0.0572, -0.0131), (0.0568, -0.0129), (0.0564, -0.0131), (0.0557, -0.0134), (0.0544, -0.0138), (0.0532, -0.0145), (0.0522, -0.0154), (0.0515, -0.0161), (0.0511, -0.0167), (0.0509, -0.0172), (0.0505, -0.0185), (0.0505, -0.0194), (0.0506, -0.0218), (0.0505, -0.0226), (0.0504, -0.0231), (0.0499, -0.0238), (0.0493, -0.0244), (0.0485, -0.0249), (0.0475, -0.0253), (0.0461, -0.0257), (0.0416, -0.0270), (0.0389, -0.0278), (0.0248, -0.0328), (0.0232, -0.0332), (0.0224, -0.0332), (0.0219, -0.0331), (0.0215, -0.0328), (0.0212, -0.0325), (0.0209, -0.0321), (0.0208, -0.0313), (0.0208, -0.0307), (0.0210, -0.0298), (0.0213, -0.0288), (0.0217, -0.0278), (0.0227, -0.0261), (0.0238, -0.0244), (0.0294, -0.0169), (0.0305, -0.0153), (0.0313, -0.0140), (0.0318, -0.0127), (0.0321, -0.0117), (0.0321, -0.0110), (0.0321, -0.0103), (0.0320, -0.0096), (0.0319, -0.0089), (0.0315, -0.0079), (0.0311, -0.0073), (0.0305, -0.0064), (0.0294, -0.0053), (0.0282, -0.0044), (0.0269, -0.0036), (0.0252, -0.0029), (0.0237, -0.0024), (0.0218, -0.0021), (0.0198, -0.0020), (0.0179, -0.0022), (0.0160, -0.0024), (0.0137, -0.0030), (0.0115, -0.0037), (0.0097, -0.0044), (0.0079, -0.0052), (0.0051, -0.0067), (0.0040, -0.0071), (0.0034, -0.0077), (0.0030, -0.0082), (0.0020, -0.0090), (0.0515, -0.0075), (0.0522, -0.0081), (0.0549, -0.0075), (0.0559, -0.0073), (0.0568, -0.0071), (0.0582, -0.0067), (0.0596, -0.0062), (0.0613, -0.0053), (0.0630, -0.0043), (0.0655, -0.0023), (0.0660, -0.0018), (0.0662, -0.0013), (0.0658, -0.0011), (0.0654, -0.0013), (0.0640, -0.0027), (0.0633, -0.0032), (0.0597, -0.0048), (0.0547, -0.0067), (0.0538, -0.0068), (0.0532, -0.0068), (0.0526, -0.0069), (0.0519, -0.0072), (0.0401, 0.0140), (0.0407, 0.0150), (0.0410, 0.0153), (0.0413, 0.0155), (0.0417, 0.0156), (0.0434, 0.0157), (0.0452, 0.0160), (0.0466, 0.0164), (0.0477, 0.0168), (0.0491, 0.0174), (0.0501, 0.0180), (0.0510, 0.0187), (0.0518, 0.0195), (0.0529, 0.0210), (0.0539, 0.0227), (0.0546, 0.0245), (0.0551, 0.0264), (0.0554, 0.0282), (0.0557, 0.0309), (0.0556, 0.0314), (0.0554, 0.0318), (0.0549, 0.0328), (0.0548, 0.0331), (0.0550, 0.0331), (0.0553, 0.0330), (0.0561, 0.0321), (0.0566, 0.0323), (0.0568, 0.0326), (0.0568, 0.0331), (0.0551, 0.0351), (0.0545, 0.0362), (0.0537, 0.0373), (0.0520, 0.0389), (0.0508, 0.0398), (0.0498, 0.0405), (0.0485, 0.0413), (0.0474, 0.0418), (0.0463, 0.0422), (0.0452, 0.0426), (0.0441, 0.0428), (0.0425, 0.0431), (0.0413, 0.0432), (0.0398, 0.0432), (0.0382, 0.0431), (0.0370, 0.0430), (0.0355, 0.0427), (0.0344, 0.0423), (0.0333, 0.0419), (0.0319, 0.0412), (0.0306, 0.0403), (0.0293, 0.0394), (0.0281, 0.0384), (0.0269, 0.0373), (0.0256, 0.0358), (0.0246, 0.0346), (0.0235, 0.0328), (0.0230, 0.0316), (0.0217, 0.0290), (0.0217, 0.0286), (0.0222, 0.0284), (0.0225, 0.0287), (0.0232, 0.0299), (0.0241, 0.0311), (0.0275, 0.0344), (0.0293, 0.0359), (0.0306, 0.0368), (0.0316, 0.0373), (0.0326, 0.0378), (0.0340, 0.0384), (0.0359, 0.0389), (0.0374, 0.0391), (0.0389, 0.0391), (0.0404, 0.0390), (0.0419, 0.0387), (0.0433, 0.0381), (0.0446, 0.0374), (0.0458, 0.0365), (0.0469, 0.0355), (0.0477, 0.0347), (0.0483, 0.0338), (0.0487, 0.0329), (0.0490, 0.0319), (0.0490, 0.0310), (0.0489, 0.0302), (0.0485, 0.0295), (0.0482, 0.0291), (0.0477, 0.0288), (0.0472, 0.0285), (0.0466, 0.0284), (0.0457, 0.0282), (0.0422, 0.0280), (0.0408, 0.0277), (0.0398, 0.0272), (0.0390, 0.0266), (0.0385, 0.0261), (0.0380, 0.0256), (0.0375, 0.0247), (0.0370, 0.0233), (0.0368, 0.0223), (0.0368, 0.0212), (0.0369, 0.0201), (0.0372, 0.0191), (0.0375, 0.0181), (0.0379, 0.0175), (0.0382, 0.0170), (0.0386, 0.0166), (0.0390, 0.0158), (0.0397, 0.0144), (0.0357, 0.0002), (0.0375, 0.0002), (0.0378, -0.0009), (0.0384, -0.0014), (0.0389, -0.0009), (0.0396, 0.0002), (0.0410, -0.0001), (0.0411, 0.0011), (0.0412, 0.0016), (0.0420, 0.0022), (0.0433, 0.0028), (0.0436, 0.0034), (0.0433, 0.0040), (0.0428, 0.0041), (0.0409, 0.0037), (0.0402, 0.0034), (0.0393, 0.0032), (0.0387, 0.0028), (0.0382, 0.0024), (0.0374, 0.0021), (0.0364, 0.0016), (0.0359, 0.0010), (0.0174, 0.0149), (0.0176, 0.0132), (0.0191, 0.0136), (0.0202, 0.0135), (0.0221, 0.0132), (0.0261, 0.0122), (0.0277, 0.0120), (0.0287, 0.0121), (0.0306, 0.0117), (0.0314, 0.0116), (0.0319, 0.0121), (0.0303, 0.0136), (0.0296, 0.0141), (0.0292, 0.0147), (0.0288, 0.0151), (0.0283, 0.0155), (0.0274, 0.0161), (0.0261, 0.0167), (0.0246, 0.0171), (0.0231, 0.0174), (0.0216, 0.0175), (0.0200, 0.0175), (0.0185, 0.0173), (0.0170, 0.0169), (0.0153, 0.0162), (0.0140, 0.0156), (0.0123, 0.0146), (0.0106, 0.0140), (0.0103, 0.0136), (0.0105, 0.0127), (0.0108, 0.0122), (0.0113, 0.0121), (0.0124, 0.0130), (0.0131, 0.0134), (0.0158, 0.0137), (0.0168, 0.0140), (0.0171, 0.0144)],
     "rings": [212, 22, 108, 22, 37],
     "tris": [(192, 212, 233), (192, 233, 232), (192, 232, 231), (231, 230, 229), (231, 229, 228), (231, 228, 227), (231, 227, 226), (231, 226, 225), (215, 214, 213), (213, 212, 192), (213, 192, 191), (213, 191, 190), (213, 190, 189), (213, 189, 188), (213, 188, 187), (213, 187, 186), (213, 186, 185), (213, 185, 184), (213, 184, 183), (213, 183, 182), (213, 182, 181), (213, 181, 180), (213, 180, 179), (213, 179, 178), (213, 178, 177), (213, 177, 176), (213, 176, 175), (213, 175, 174), (213, 174, 173), (213, 173, 172), (213, 172, 171), (213, 171, 170), (213, 170, 169), (213, 169, 168), (213, 168, 167), (213, 167, 166), (213, 166, 165), (213, 165, 164), (213, 164, 163), (213, 163, 162), (162, 161, 160), (162, 160, 159), (162, 159, 158), (162, 158, 157), (162, 157, 156), (150, 149, 148), (146, 145, 144), (146, 144, 143), (146, 143, 142), (140, 139, 138), (140, 138, 137), (140, 137, 136), (140, 136, 135), (135, 134, 133), (135, 133, 132), (135, 132, 131), (135, 131, 130), (135, 130, 129), (135, 129, 128), (135, 128, 127), (135, 127, 126), (135, 126, 125), (135, 125, 124), (135, 124, 123), (135, 123, 122), (135, 122, 121), (121, 120, 119), (121, 119, 118), (121, 118, 117), (121, 117, 116), (121, 116, 115), (121, 115, 114), (121, 114, 113), (121, 113, 112), (121, 112, 111), (121, 111, 110), (121, 110, 109), (121, 109, 108), (121, 108, 107), (121, 107, 106), (121, 106, 105), (121, 105, 104), (121, 104, 103), (121, 103, 102), (121, 102, 101), (121, 101, 100), (121, 100, 99), (121, 99, 98), (121, 98, 97), (121, 97, 96), (121, 96, 95), (121, 95, 94), (121, 94, 93), (121, 93, 92), (121, 92, 91), (121, 91, 90), (121, 90, 89), (121, 89, 88), (121, 88, 87), (121, 87, 86), (121, 86, 85), (121, 85, 84), (121, 84, 83), (121, 83, 82), (121, 82, 81), (121, 81, 80), (121, 80, 79), (121, 79, 78), (121, 78, 77), (121, 77, 76), (121, 76, 75), (121, 75, 74), (74, 73, 72), (74, 72, 71), (74, 71, 70), (74, 70, 69), (74, 69, 68), (74, 68, 67), (66, 65, 64), (66, 64, 63), (66, 63, 62), (66, 62, 61), (66, 61, 60), (66, 60, 59), (66, 59, 58), (66, 58, 57), (66, 57, 56), (66, 56, 55), (66, 55, 54), (66, 54, 53), (66, 53, 52), (66, 52, 51), (66, 51, 50), (50, 49, 48), (50, 48, 47), (50, 47, 46), (50, 46, 45), (50, 45, 44), (50, 44, 43), (50, 43, 42), (50, 42, 41), (50, 41, 40), (50, 40, 39), (50, 39, 38), (36, 35, 34), (36, 34, 33), (32, 31, 30), (32, 30, 29), (32, 29, 28), (27, 26, 25), (27, 25, 24), (27, 24, 23), (27, 23, 22), (27, 22, 21), (17, 16, 15), (291, 290, 289), (264, 263, 262), (259, 258, 257), (259, 257, 256), (259, 256, 255), (259, 255, 254), (259, 254, 253), (259, 253, 252), (259, 252, 251), (259, 251, 250), (239, 238, 237), (239, 237, 236), (239, 236, 235), (239, 235, 234), (340, 339, 338), (340, 338, 337), (324, 323, 322), (324, 322, 321), (324, 321, 320), (324, 320, 319), (324, 319, 318), (324, 318, 317), (324, 317, 316), (324, 316, 315), (324, 315, 314), (324, 314, 313), (324, 313, 312), (324, 312, 311), (324, 311, 310), (324, 310, 309), (324, 309, 308), (324, 308, 307), (324, 307, 306), (324, 306, 305), (324, 305, 304), (324, 304, 303), (324, 303, 302), (324, 302, 301), (324, 301, 300), (324, 300, 299), (324, 299, 298), (324, 298, 297), (324, 297, 296), (324, 296, 295), (324, 295, 294), (324, 294, 293), (292, 291, 14), (13, 12, 11), (13, 11, 10), (13, 10, 9), (13, 9, 8), (13, 8, 7), (13, 7, 6), (13, 6, 5), (13, 5, 392), (13, 392, 391), (13, 391, 390), (13, 390, 389), (13, 389, 388), (13, 388, 387), (13, 387, 386), (13, 386, 385), (13, 385, 384), (13, 384, 383), (13, 383, 382), (13, 382, 381), (13, 381, 380), (377, 376, 375), (377, 375, 374), (372, 371, 370), (372, 370, 369), (369, 368, 367), (369, 367, 366), (369, 366, 365), (365, 364, 400), (365, 400, 399), (365, 399, 398), (365, 398, 397), (365, 397, 396), (365, 396, 395), (393, 392, 5), (5, 342, 363), (5, 363, 362), (5, 362, 361), (5, 361, 360), (5, 360, 359), (5, 359, 358), (5, 358, 357), (5, 357, 356), (5, 356, 355), (352, 351, 350), (352, 350, 349), (352, 349, 348), (348, 347, 346), (348, 346, 345), (344, 343, 342), (344, 342, 5), (5, 4, 3), (2, 1, 0), (2, 0, 211), (2, 211, 210), (2, 210, 209), (2, 209, 208), (2, 208, 207), (2, 207, 206), (2, 206, 205), (2, 205, 204), (193, 192, 231), (193, 231, 225), (193, 225, 224), (213, 162, 156), (213, 156, 155), (213, 155, 154), (213, 154, 153), (213, 153, 152), (213, 152, 151), (213, 151, 150), (213, 150, 148), (213, 148, 147), (213, 147, 146), (213, 146, 142), (213, 142, 141), (140, 135, 121), (121, 74, 67), (67, 66, 50), (37, 36, 33), (28, 27, 21), (28, 21, 20), (260, 259, 250), (240, 239, 234), (341, 340, 337), (325, 324, 293), (293, 292, 14), (14, 13, 380), (378, 377, 374), (373, 372, 369), (369, 365, 395), (394, 393, 5), (394, 5, 355), (345, 344, 5), (3, 2, 204), (3, 204, 203), (194, 193, 224), (215, 213, 141), (141, 140, 121), (38, 37, 33), (32, 28, 20), (32, 20, 19), (32, 19, 18), (32, 18, 17), (32, 17, 15), (32, 15, 14), (32, 14, 291), (261, 260, 250), (241, 240, 234), (326, 325, 293), (326, 293, 14), (373, 369, 395), (395, 394, 355), (5, 3, 203), (5, 203, 202), (5, 202, 201), (5, 201, 200), (195, 194, 224), (216, 215, 141), (216, 141, 121), (33, 32, 291), (33, 291, 289), (33, 289, 288), (33, 288, 287), (33, 287, 286), (33, 286, 285), (242, 241, 234), (327, 326, 14), (327, 14, 380), (373, 395, 355), (373, 355, 354), (345, 5, 200), (345, 200, 199), (345, 199, 198), (345, 198, 197), (345, 197, 196), (345, 196, 195), (345, 195, 224), (217, 216, 121), (38, 33, 285), (38, 285, 284), (38, 284, 283), (38, 283, 282), (38, 282, 281), (38, 281, 280), (328, 327, 380), (328, 380, 379), (328, 379, 378), (374, 373, 354), (348, 345, 224), (218, 217, 121), (50, 38, 280), (50, 280, 279), (50, 279, 278), (50, 278, 277), (50, 277, 276), (50, 276, 275), (50, 275, 274), (50, 274, 273), (50, 273, 272), (50, 272, 271), (50, 271, 270), (50, 270, 269), (50, 269, 268), (50, 268, 267), (50, 267, 266), (50, 266, 265), (50, 265, 264), (50, 264, 262), (329, 328, 378), (378, 374, 354), (352, 348, 224), (219, 218, 121), (67, 50, 262), (67, 262, 261), (67, 261, 250), (67, 250, 249), (67, 249, 248), (67, 248, 247), (67, 247, 246), (67, 246, 245), (330, 329, 378), (353, 352, 224), (220, 219, 121), (121, 67, 245), (121, 245, 244), (121, 244, 243), (121, 243, 242), (121, 242, 234), (331, 330, 378), (354, 353, 224), (221, 220, 121), (332, 331, 378), (378, 354, 224), (378, 224, 223), (222, 221, 121), (333, 332, 378), (223, 222, 121), (223, 121, 234), (334, 333, 378), (378, 223, 234), (378, 234, 341), (378, 341, 337), (378, 337, 336), (378, 336, 335), (378, 335, 334)]},
]
GUARD_SWIRLS = [
    {"pts": [(0.0779, 0.0285), (0.0775, 0.0284), (0.0770, 0.0284), (0.0766, 0.0285), (0.0763, 0.0288), (0.0760, 0.0291), (0.0758, 0.0294), (0.0756, 0.0300), (0.0755, 0.0307), (0.0755, 0.0318), (0.0757, 0.0329), (0.0759, 0.0336), (0.0763, 0.0346), (0.0767, 0.0352), (0.0772, 0.0357), (0.0775, 0.0359), (0.0778, 0.0360), (0.0782, 0.0361), (0.0787, 0.0361), (0.0791, 0.0360), (0.0794, 0.0358), (0.0797, 0.0355), (0.0799, 0.0352), (0.0801, 0.0348), (0.0803, 0.0342), (0.0803, 0.0335), (0.0803, 0.0327), (0.0801, 0.0320), (0.0800, 0.0313), (0.0797, 0.0306), (0.0794, 0.0299), (0.0788, 0.0291), (0.0782, 0.0286)],
     "rings": [33],
     "tris": [(1, 0, 32), (1, 32, 31), (1, 31, 30), (1, 30, 29), (1, 29, 28), (1, 28, 27), (1, 27, 26), (1, 26, 25), (1, 25, 24), (1, 24, 23), (1, 23, 22), (1, 22, 21), (1, 21, 20), (1, 20, 19), (1, 19, 18), (1, 18, 17), (1, 17, 16), (1, 16, 15), (1, 15, 14), (1, 14, 13), (1, 13, 12), (1, 12, 11), (1, 11, 10), (1, 10, 9), (1, 9, 8), (1, 8, 7), (1, 7, 6), (1, 6, 5), (1, 5, 4), (1, 4, 3), (1, 3, 2)]},
    {"pts": [(0.0157, 0.0195), (0.0154, 0.0198), (0.0151, 0.0202), (0.0149, 0.0206), (0.0149, 0.0210), (0.0149, 0.0215), (0.0150, 0.0219), (0.0152, 0.0223), (0.0154, 0.0226), (0.0160, 0.0231), (0.0167, 0.0234), (0.0174, 0.0237), (0.0185, 0.0239), (0.0192, 0.0239), (0.0200, 0.0238), (0.0207, 0.0236), (0.0214, 0.0232), (0.0216, 0.0229), (0.0219, 0.0226), (0.0221, 0.0221), (0.0222, 0.0217), (0.0222, 0.0212), (0.0220, 0.0208), (0.0218, 0.0204), (0.0213, 0.0198), (0.0210, 0.0196), (0.0204, 0.0193), (0.0193, 0.0190), (0.0185, 0.0188), (0.0178, 0.0188), (0.0167, 0.0190), (0.0160, 0.0193)],
     "rings": [32],
     "tris": [(1, 0, 31), (1, 31, 30), (1, 30, 29), (1, 29, 28), (1, 28, 27), (1, 27, 26), (1, 26, 25), (1, 25, 24), (1, 24, 23), (1, 23, 22), (1, 22, 21), (1, 21, 20), (1, 20, 19), (1, 19, 18), (1, 18, 17), (1, 17, 16), (1, 16, 15), (1, 15, 14), (1, 14, 13), (1, 13, 12), (1, 12, 11), (1, 11, 10), (1, 10, 9), (1, 9, 8), (1, 8, 7), (1, 7, 6), (1, 6, 5), (1, 5, 4), (1, 4, 3), (1, 3, 2)]},
    {"pts": [(0.0416, 0.0123), (0.0414, 0.0128), (0.0413, 0.0130), (0.0413, 0.0136), (0.0415, 0.0141), (0.0416, 0.0144), (0.0420, 0.0148), (0.0427, 0.0154), (0.0437, 0.0158), (0.0468, 0.0166), (0.0482, 0.0171), (0.0495, 0.0178), (0.0504, 0.0184), (0.0515, 0.0194), (0.0520, 0.0199), (0.0527, 0.0208), (0.0536, 0.0224), (0.0552, 0.0257), (0.0555, 0.0263), (0.0559, 0.0267), (0.0563, 0.0271), (0.0565, 0.0272), (0.0570, 0.0273), (0.0572, 0.0273), (0.0574, 0.0272), (0.0578, 0.0268), (0.0580, 0.0264), (0.0582, 0.0259), (0.0583, 0.0253), (0.0583, 0.0246), (0.0583, 0.0238), (0.0582, 0.0227), (0.0580, 0.0220), (0.0577, 0.0208), (0.0574, 0.0201), (0.0569, 0.0190), (0.0561, 0.0176), (0.0556, 0.0169), (0.0549, 0.0160), (0.0544, 0.0154), (0.0535, 0.0146), (0.0526, 0.0138), (0.0519, 0.0134), (0.0509, 0.0127), (0.0502, 0.0124), (0.0491, 0.0119), (0.0484, 0.0116), (0.0468, 0.0112), (0.0457, 0.0111), (0.0449, 0.0110), (0.0442, 0.0111), (0.0435, 0.0112), (0.0429, 0.0114), (0.0423, 0.0117), (0.0418, 0.0121)],
     "rings": [55],
     "tris": [(1, 0, 54), (1, 54, 53), (1, 53, 52), (1, 52, 51), (1, 51, 50), (1, 50, 49), (1, 49, 48), (1, 48, 47), (1, 47, 46), (1, 46, 45), (1, 45, 44), (1, 44, 43), (1, 43, 42), (1, 42, 41), (1, 41, 40), (1, 40, 39), (1, 39, 38), (1, 38, 37), (1, 37, 36), (1, 36, 35), (1, 35, 34), (1, 34, 33), (1, 33, 32), (1, 32, 31), (31, 30, 29), (31, 29, 28), (31, 28, 27), (31, 27, 26), (31, 26, 25), (31, 25, 24), (31, 24, 23), (31, 23, 22), (31, 22, 21), (31, 21, 20), (31, 20, 19), (31, 19, 18), (31, 18, 17), (31, 17, 16), (31, 16, 15), (31, 15, 14), (31, 14, 13), (31, 13, 12), (31, 12, 11), (9, 8, 7), (9, 7, 6), (9, 6, 5), (9, 5, 4), (9, 4, 3), (9, 3, 2), (9, 2, 1), (1, 31, 11), (1, 11, 10), (1, 10, 9)]},
    {"pts": [(0.0043, 0.0083), (0.0043, 0.0088), (0.0044, 0.0093), (0.0046, 0.0099), (0.0050, 0.0104), (0.0056, 0.0112), (0.0062, 0.0117), (0.0067, 0.0121), (0.0073, 0.0125), (0.0080, 0.0127), (0.0087, 0.0130), (0.0101, 0.0133), (0.0122, 0.0135), (0.0156, 0.0137), (0.0183, 0.0138), (0.0206, 0.0137), (0.0224, 0.0134), (0.0256, 0.0126), (0.0270, 0.0123), (0.0284, 0.0122), (0.0311, 0.0122), (0.0319, 0.0121), (0.0325, 0.0119), (0.0327, 0.0118), (0.0331, 0.0114), (0.0333, 0.0112), (0.0336, 0.0107), (0.0338, 0.0098), (0.0338, 0.0092), (0.0337, 0.0085), (0.0335, 0.0078), (0.0332, 0.0067), (0.0329, 0.0060), (0.0324, 0.0049), (0.0318, 0.0039), (0.0313, 0.0033), (0.0308, 0.0027), (0.0303, 0.0022), (0.0297, 0.0018), (0.0290, 0.0014), (0.0280, 0.0010), (0.0273, 0.0008), (0.0266, 0.0007), (0.0258, 0.0007), (0.0250, 0.0008), (0.0243, 0.0009), (0.0232, 0.0012), (0.0221, 0.0016), (0.0214, 0.0019), (0.0207, 0.0023), (0.0201, 0.0027), (0.0193, 0.0034), (0.0189, 0.0040), (0.0185, 0.0046), (0.0180, 0.0056), (0.0172, 0.0078), (0.0168, 0.0086), (0.0163, 0.0091), (0.0157, 0.0094), (0.0151, 0.0096), (0.0145, 0.0096), (0.0139, 0.0096), (0.0128, 0.0094), (0.0110, 0.0089), (0.0074, 0.0077), (0.0062, 0.0074), (0.0053, 0.0074), (0.0049, 0.0076), (0.0045, 0.0079)],
     "rings": [69],
     "tris": [(1, 0, 68), (1, 68, 67), (1, 67, 66), (1, 66, 65), (1, 65, 64), (1, 64, 63), (1, 63, 62), (1, 62, 61), (55, 54, 53), (55, 53, 52), (55, 52, 51), (55, 51, 50), (55, 50, 49), (55, 49, 48), (55, 48, 47), (55, 47, 46), (55, 46, 45), (55, 45, 44), (55, 44, 43), (55, 43, 42), (55, 42, 41), (55, 41, 40), (55, 40, 39), (55, 39, 38), (55, 38, 37), (55, 37, 36), (55, 36, 35), (55, 35, 34), (55, 34, 33), (55, 33, 32), (55, 32, 31), (55, 31, 30), (55, 30, 29), (55, 29, 28), (55, 28, 27), (55, 27, 26), (55, 26, 25), (55, 25, 24), (55, 24, 23), (55, 23, 22), (55, 22, 21), (55, 21, 20), (55, 20, 19), (55, 19, 18), (55, 18, 17), (55, 17, 16), (55, 16, 15), (55, 15, 14), (55, 14, 13), (13, 12, 11), (13, 11, 10), (13, 10, 9), (13, 9, 8), (13, 8, 7), (13, 7, 6), (13, 6, 5), (13, 5, 4), (13, 4, 3), (13, 3, 2), (13, 2, 1), (13, 1, 61), (13, 61, 60), (13, 60, 59), (13, 59, 58), (13, 58, 57), (13, 57, 56), (13, 56, 55)]},
    {"pts": [(0.0660, 0.0040), (0.0658, 0.0052), (0.0659, 0.0061), (0.0662, 0.0066), (0.0664, 0.0072), (0.0673, 0.0084), (0.0712, 0.0129), (0.0721, 0.0139), (0.0728, 0.0144), (0.0733, 0.0146), (0.0738, 0.0146), (0.0740, 0.0145), (0.0742, 0.0143), (0.0745, 0.0139), (0.0747, 0.0132), (0.0747, 0.0126), (0.0747, 0.0115), (0.0745, 0.0105), (0.0742, 0.0089), (0.0737, 0.0074), (0.0734, 0.0063), (0.0729, 0.0052), (0.0724, 0.0041), (0.0717, 0.0027), (0.0711, 0.0017), (0.0704, 0.0008), (0.0697, -0.0001), (0.0691, -0.0007), (0.0686, -0.0010), (0.0681, -0.0011), (0.0676, -0.0011), (0.0672, -0.0009), (0.0669, -0.0005), (0.0667, 0.0002), (0.0663, 0.0024)],
     "rings": [35],
     "tris": [(1, 0, 34), (34, 33, 32), (34, 32, 31), (34, 31, 30), (34, 30, 29), (34, 29, 28), (34, 28, 27), (34, 27, 26), (34, 26, 25), (34, 25, 24), (34, 24, 23), (34, 23, 22), (34, 22, 21), (34, 21, 20), (34, 20, 19), (34, 19, 18), (34, 18, 17), (34, 17, 16), (34, 16, 15), (34, 15, 14), (34, 14, 13), (34, 13, 12), (34, 12, 11), (34, 11, 10), (34, 10, 9), (34, 9, 8), (34, 8, 7), (34, 7, 6), (34, 6, 5), (34, 5, 4), (34, 4, 3), (34, 3, 2), (34, 2, 1)]},
    {"pts": [(0.0343, -0.0037), (0.0345, -0.0031), (0.0346, -0.0028), (0.0349, -0.0022), (0.0353, -0.0017), (0.0361, -0.0011), (0.0370, -0.0006), (0.0389, 0.0003), (0.0398, 0.0008), (0.0407, 0.0014), (0.0424, 0.0026), (0.0433, 0.0031), (0.0439, 0.0034), (0.0445, 0.0036), (0.0452, 0.0036), (0.0459, 0.0036), (0.0465, 0.0034), (0.0474, 0.0029), (0.0482, 0.0022), (0.0489, 0.0014), (0.0492, 0.0007), (0.0496, -0.0003), (0.0498, -0.0014), (0.0502, -0.0035), (0.0503, -0.0041), (0.0505, -0.0047), (0.0508, -0.0053), (0.0511, -0.0058), (0.0517, -0.0064), (0.0522, -0.0067), (0.0528, -0.0069), (0.0534, -0.0071), (0.0541, -0.0072), (0.0554, -0.0072), (0.0581, -0.0069), (0.0587, -0.0069), (0.0592, -0.0070), (0.0596, -0.0072), (0.0600, -0.0074), (0.0600, -0.0076), (0.0600, -0.0081), (0.0599, -0.0085), (0.0596, -0.0089), (0.0591, -0.0092), (0.0583, -0.0098), (0.0574, -0.0103), (0.0563, -0.0108), (0.0549, -0.0114), (0.0538, -0.0118), (0.0519, -0.0123), (0.0499, -0.0126), (0.0480, -0.0127), (0.0469, -0.0126), (0.0462, -0.0125), (0.0452, -0.0123), (0.0442, -0.0119), (0.0414, -0.0107), (0.0384, -0.0095), (0.0374, -0.0090), (0.0367, -0.0086), (0.0362, -0.0082), (0.0356, -0.0076), (0.0352, -0.0071), (0.0348, -0.0065), (0.0345, -0.0058), (0.0343, -0.0051), (0.0343, -0.0044)],
     "rings": [67],
     "tris": [(1, 0, 66), (1, 66, 65), (1, 65, 64), (1, 64, 63), (1, 63, 62), (1, 62, 61), (1, 61, 60), (1, 60, 59), (1, 59, 58), (1, 58, 57), (1, 57, 56), (1, 56, 55), (1, 55, 54), (1, 54, 53), (1, 53, 52), (1, 52, 51), (1, 51, 50), (1, 50, 49), (1, 49, 48), (1, 48, 47), (1, 47, 46), (1, 46, 45), (1, 45, 44), (1, 44, 43), (1, 43, 42), (42, 41, 40), (42, 40, 39), (42, 39, 38), (42, 38, 37), (42, 37, 36), (42, 36, 35), (42, 35, 34), (42, 34, 33), (42, 33, 32), (42, 32, 31), (42, 31, 30), (23, 22, 21), (23, 21, 20), (23, 20, 19), (23, 19, 18), (23, 18, 17), (23, 17, 16), (23, 16, 15), (23, 15, 14), (23, 14, 13), (23, 13, 12), (23, 12, 11), (23, 11, 10), (23, 10, 9), (23, 9, 8), (23, 8, 7), (23, 7, 6), (23, 6, 5), (23, 5, 4), (23, 4, 3), (23, 3, 2), (23, 2, 1), (1, 42, 30), (1, 30, 29), (1, 29, 28), (1, 28, 27), (1, 27, 26), (1, 26, 25), (1, 25, 24), (1, 24, 23)]},
]

if __name__ == "__main__":
    main()
