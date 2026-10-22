"""
刀 (雷電将軍の元素爆発の刀「夢想の一太刀」風, ファンメイド) 用のテクスチャを生成するスクリプト。

1 回の実行で、同じ UV 配置の 3 枚を作ります (色とノーマルは 8192x8192、発光は 4096x4096):
    Katana_Atlas.png     … 色 (ベースカラー)
    Katana_Emission.png  … 発光 (光らせたい所だけ明るい。黒は光らない)
    Katana_Normal.png    … ノーマルマップ (OpenGL 形式 = Unity / Blender と同じ。凹凸の見え方)

Blender ではなく通常の Python で実行します:
    pip install pillow numpy
    python make_katana_texture.py

刃の色は参考画像 (ゲーム画面) から、鍔・柄は参考画像 (コスプレ用の刀の写真) から拾っています。
刃の付け根の飾り板は guard_tone.png、柄の模様は handle_tone.png (どちらも写真からなぞった塗り分け) を使います。

アトラスのレイアウト (UV は左下原点):
    v 0.00-0.36 / u 0.00-1.00 : 刃 (横 = 根元→切っ先, 縦 = 刃先→峰)
    v 0.38-0.66 / u 0.00-1.00 : 柄 (横 = 鍔側→柄頭, 縦 = 一周。紫の地・金の線)
    v 0.78-0.98 / u 0.00-0.20 : 刃の付け根の飾り板 (濃い紫と薄い紫の炎の模様。上の余白は側面用の薄紫)
    v 0.78-0.98 / u 0.22-0.30 : 白い光 (白い巴)
    v 0.78-0.98 / u 0.32-0.52 : 鍔 (金色の楕円の面)
    v 0.78-0.98 / u 0.54-0.64 : 柄の白い鋲
    v 0.78-0.98 / u 0.66-0.76 : 柄に巻いた赤い紐 (横 = 紐の一周, 縦 = 紐の長さ。撚りの筋)
    それ以外                    : 濃い紫 (使っていない)
make_katana.py の UV 割り当てはこのレイアウトに合わせてあります。
"""

import math
import os
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

Image.MAX_IMAGE_PIXELS = None

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_ALBEDO = os.path.join(HERE, "Katana_Atlas.png")
OUT_EMISSION = os.path.join(HERE, "Katana_Emission.png")
OUT_NORMAL = os.path.join(HERE, "Katana_Normal.png")
SIZE = 8192            # 実用上の最大 (Unity の Max Size で 4096 / 2048 などに下げられる)
F = SIZE / 2048        # 線の太さ・ぼかしの量を解像度に合わせる係数
NORMAL_STRENGTH = 20.0

UV_BLADE = (0.0, 0.0, 1.0, 0.36)
UV_HANDLE = (0.0, 0.38, 1.0, 0.66)
UV_GUARD = (0.0, 0.78, 0.20, 0.98)     # 刃の付け根の飾り板
UV_PAD = 0.002                         # make_katana.py と同じ (UV の四辺の余白)
GUARD_TONE = os.path.join(HERE, "guard_tone.png")   # 飾り板の塗り分け (参考画像からなぞったもの)
GUARD_A_MIN, GUARD_A_MAX, GUARD_E_MIN, GUARD_E_MAX = 0.0016, 0.1040, -0.0345, 0.0491
UV_WHITE = (0.22, 0.78, 0.30, 0.98)
UV_TSUBA = (0.32, 0.78, 0.52, 0.98)
UV_STUD = (0.54, 0.78, 0.64, 0.98)
UV_CORD = (0.66, 0.78, 0.76, 0.98)     # 柄に巻いた赤い紐
# 柄 (make_katana.py の HANDLE_RINGS と一致させる)。参考画像の写真を柄に沿ってまっすぐにした座標 (px) で配置
HANDLE_TONE = os.path.join(HERE, "handle_tone.png")   # 柄の塗り分け (写真からなぞったもの)
HANDLE_S0, HANDLE_S1 = 8.2, 363.5      # 柄の始まり (鍔の裏) と柄頭
INLAY_S, INLAY_V = 333.0, 0.21         # 柄頭の薄紫の象眼

# 色 (参考画像のゲーム画面から)
EDGE_WHITE = (226, 222, 230)     # 刃先・刃文 (写真: 銀白)
BLADE_LAV = (230, 198, 253)      # 刃の地 (白〜ピンク寄りの薄紫)
BLADE_LAV_HI = (245, 216, 254)
PANEL = (166, 127, 240)          # 刃の中央の紫の模様
PANEL_DARK = (124, 86, 226)
PANEL_LIGHT = (205, 170, 250)
DEEP = (62, 22, 100)             # 深い紫 (写真: 刃の模様・飾り板の濃い部分)
DEEP_LIGHT = (157, 117, 245)
HANDLE_PURPLE = (152, 115, 174)  # 写真: 灰みのある赤紫    # 柄の地 (つやのある深い紫)
CORD_RED = (228, 16, 32)         # 紐の赤 (写真: 202, 10, 26。撚りの陰影込み)
GOLD_PIPE = ((176, 140, 116), (242, 212, 188), (252, 234, 218))   # 写真: 淡いシャンパン色   # 柄の金の線 (ふち → 中 → 明るい中央)
GLOW_WHITE = (255, 250, 255)
SWIRL_WHITE = (234, 230, 236)    # 白い巴 (写真: 少し灰みのある白)
TSUBA_GOLD = [(0.0, (104, 78, 56)), (0.35, (164, 132, 104)), (0.55, (204, 172, 146)), (0.8, (230, 198, 172)), (1.0, (248, 222, 200))]   # 写真: ブロンズ寄りの金

random.seed(37)


# ---------------------------------------------------------------- 共通
def uv_box(rect):
    """UV 矩形 (左下原点) を PIL のピクセル矩形 (左上原点) に変換。"""
    u0, v0, u1, v1 = rect
    return (round(u0 * SIZE), round((1 - v1) * SIZE), round(u1 * SIZE), round((1 - v0) * SIZE))


def lerp_color(stops, t):
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            k = max(0.0, (t - t0) / (t1 - t0))
            return tuple(round(c0[i] + (c1[i] - c0[i]) * k) for i in range(3))
    return stops[-1][1]


def vgradient(size, stops):
    w, h = size
    img = Image.new("RGB", (1, h))
    for y in range(h):
        img.putpixel((0, y), lerp_color(stops, y / max(1, h - 1)))
    return img.resize((w, h))


def blur(img, r):
    return img.filter(ImageFilter.GaussianBlur(r * F))


def scale_rgb(img, k):
    return img.point(lambda v: min(255, int(v * k)))


class Maps:
    """色・発光・高さの 3 枚を同じ配置で描くための入れ物。"""

    def __init__(self):
        self.albedo = Image.new("RGB", (SIZE, SIZE), DEEP)
        self.emission = Image.new("RGB", (SIZE, SIZE), tuple(int(c * 0.25) for c in DEEP))
        self.height = np.full((SIZE, SIZE), 0.5, dtype=np.float32)

    def put(self, rect, albedo=None, emission=None):
        x0, y0, _, _ = uv_box(rect)
        if albedo is not None:
            self.albedo.paste(albedo, (x0, y0))
        if emission is not None:
            self.emission.paste(emission, (x0, y0))

    def bump(self, rect, mask, amount):
        """mask (L, 領域の大きさ) の形に高さを足す (負なら彫る)。"""
        x0, y0, x1, y1 = uv_box(rect)
        self.height[y0:y1, x0:x1] += np.asarray(mask, dtype=np.float32) * (amount / 255.0)

    def noise(self, rect, amount, scale):
        x0, y0, x1, y1 = uv_box(rect)
        w, h = x1 - x0, y1 - y0
        n = Image.effect_noise((max(1, int(w / scale)), max(1, int(h / scale))), 60).resize((w, h), Image.BICUBIC)
        self.height[y0:y1, x0:x1] += (np.asarray(n, dtype=np.float32) / 255.0 - 0.5) * amount

    def normal_map(self):
        h = self.height
        gy, gx = np.gradient(h)                       # 画像の y は下向き
        s = NORMAL_STRENGTH * F
        nx, ny = -gx * s, gy * s                      # OpenGL 形式 (緑 = UV の上方向)
        nz = np.ones_like(h)
        inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
        rgb = np.stack([(nx * inv * 0.5 + 0.5), (ny * inv * 0.5 + 0.5), (nz * inv * 0.5 + 0.5)], axis=-1)
        return Image.fromarray((rgb * 255 + 0.5).astype(np.uint8), "RGB")


def seamless_v(img):
    """上下の端がつながるようにする (柄は縦方向に一周するので継ぎ目を消す)。"""
    w, h = img.size
    shifted = ImageChops.offset(img, 0, h // 2)
    ramp = Image.new("L", (1, h))
    for y in range(h):
        ramp.putpixel((0, y), int(255 * abs(y / (h - 1) - 0.5) * 2))
    return Image.composite(shifted, img, ramp.resize((w, h)))


def marble(size, c0, c1, scale=40):
    w, h = size
    scale = max(2, int(scale * F))
    n1 = Image.effect_noise((max(1, w // scale), max(1, h // scale)), 80).resize((w, h), Image.BICUBIC)
    n2 = Image.effect_noise((max(1, w // (scale // 3)), max(1, h // (scale // 3))), 60).resize((w, h), Image.BICUBIC)
    n = ImageChops.add(n1.point(lambda v: v * 0.7), n2.point(lambda v: v * 0.3))
    n = blur(n, 3)
    mid = tuple((c0[i] + c1[i]) // 2 for i in range(3))
    lut = [lerp_color([(0.0, c0), (0.5, mid), (1.0, c1)], min(1.0, max(0.0, (v - 70) / 120))) for v in range(256)]
    return Image.merge("RGB", tuple(n.point([c[k] for c in lut]) for k in range(3)))


def stripes(size, angle_deg, period, sharp=1.0):
    """斜めの縞 (0..255)。組紐の織り目などに使う。"""
    w, h = size
    a = math.radians(angle_deg)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    phase = (xx * math.cos(a) + yy * math.sin(a)) / period * 2 * math.pi
    v = (np.sin(phase) * 0.5 + 0.5) ** sharp
    return Image.fromarray((v * 255).astype(np.uint8), "L")


# ---------------------------------------------------------------- 刃
def flame_edge(x0, x1, base, amp, step, rng):
    """なめらかに揺らめく炎の境界線 (x0→x1)。ゆっくり立ち上がり、切っ先側へなびいて柔らかく戻る。"""
    pts = []
    x = x0
    while x < x1:
        a = amp * rng.uniform(0.4, 1.0)
        s = step * rng.uniform(0.7, 1.3)
        for k in range(16):
            t = k / 16
            if t < 0.72:
                lift = 0.5 - 0.5 * math.cos(math.pi * t / 0.72)
            else:
                lift = 0.5 + 0.5 * math.cos(math.pi * (t - 0.72) / 0.28)
            xx = x + s * t
            pts.append((xx, base(xx) + a * lift))
        x += s
    pts.append((x1, base(x1)))
    return pts


def hgradient(size, stops):
    w, h = size
    img = Image.new("RGB", (w, 1))
    for x in range(w):
        img.putpixel((x, 0), lerp_color(stops, x / max(1, w - 1)))
    return img.resize((w, h))


def lightning(d, p0, p1, rng, width, depth=6, spread=0.22, branch=0.35):
    """枝分かれする細い稲妻 (中点をずらして再帰的に描く)。"""
    (xa, ya), (xb, yb) = p0, p1
    if depth == 0:
        d.line([p0, p1], fill=255, width=max(1, int(width)))
        return
    ln = math.hypot(xb - xa, yb - ya)
    mx = (xa + xb) / 2 + rng.uniform(-spread, spread) * ln * (-(yb - ya) / max(ln, 1e-6))
    my = (ya + yb) / 2 + rng.uniform(-spread, spread) * ln * ((xb - xa) / max(ln, 1e-6))
    lightning(d, p0, (mx, my), rng, width, depth - 1, spread, branch)
    lightning(d, (mx, my), p1, rng, width, depth - 1, spread, branch)
    if depth >= 3 and rng.random() < branch:  # 枝
        ang = math.atan2(yb - ya, xb - xa) + rng.choice((-1, 1)) * rng.uniform(0.4, 0.9)
        L = ln * rng.uniform(0.3, 0.6)
        lightning(d, (mx, my), (mx + math.cos(ang) * L, my + math.sin(ang) * L), rng, width * 0.6, depth - 2, spread, 0)


def sparkle(d, x, y, r):
    """4 本の光の筋をもつ星のきらめき。"""
    t = max(1.0, r * 0.18)
    d.polygon([(x - r, y), (x, y - t), (x + r, y), (x, y + t)], fill=255)
    d.polygon([(x, y - r), (x + t, y), (x, y + r), (x - t, y)], fill=255)
    d.ellipse([x - t * 1.6, y - t * 1.6, x + t * 1.6, y + t * 1.6], fill=255)


def stardust(size, rng, count, stars, area=None):
    """星屑 (小さな点) と、ところどころの星のきらめき。area は散らす範囲の L マスク。"""
    w, h = size
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    for _ in range(count):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.uniform(0.5, 1.5) * F
        d.ellipse([x - r, y - r, x + r, y + r], fill=rng.randint(150, 255))
    for _ in range(stars):
        sparkle(d, rng.uniform(0, w), rng.uniform(0, h), rng.uniform(4, 11) * F)
    if area is not None:
        m = ImageChops.multiply(m, area)
    return m


def nebula(size, rng, cols, scale=60, detail=3):
    """星雲のような雲: 大きさの違う雲を重ね、cols (暗い → 明るい) の色で塗る。"""
    w, h = size
    acc = None
    for k in range(detail):
        sc = max(2, int(scale * F / (2.2 ** k)))
        n = Image.effect_noise((max(1, w // sc), max(1, h // sc)), 70).resize((w, h), Image.BICUBIC)
        n = n.point(lambda v, k=k: v * (0.62 / (k + 1)))
        acc = n if acc is None else ImageChops.add(acc, n)
    acc = blur(acc, 2)
    lo, hi = np.percentile(np.asarray(acc), (3, 97))
    stops = [(i / (len(cols) - 1), c) for i, c in enumerate(cols)]
    lut = [lerp_color(stops, min(1.0, max(0.0, (v - lo) / max(1.0, hi - lo)))) for v in range(256)]
    return Image.merge("RGB", tuple(acc.point([c[k] for c in lut]) for k in range(3)))


def grain(size, along=40, across=1.2, amount=1.0):
    """刀身の地肌: 長さ方向に流れる細かい木目のような筋 (0..255, 中央 128)。"""
    w, h = size
    n = Image.effect_noise((max(1, int(w / (along * F))), max(1, int(h / (across * F)))), 50)
    n = n.resize((w, h), Image.BICUBIC)
    return n.point(lambda v: int(128 + (v - 128) * amount))


def draw_blade(maps):
    """刀身。写真の配色 (灰みのある薄紫の地・深い紫の炎の模様・銀白の刃先) を土台に、
    真珠のような地の移ろい、地肌の流れ、星雲の模様、光る縁取り、稲妻、星のきらめきで幻想的に。"""
    x0, y0, x1, y1 = uv_box(UV_BLADE)
    w, h = x1 - x0, y1 - y0
    rng = random.Random(11)

    def Y(v):  # v (0 = 刃先, 1 = 峰) → 行
        return h - 1 - v * (h - 1)

    # ---- 地: 真珠のように根元 → 切っ先へ移ろう薄紫 (桜色寄り → 青み → 切っ先は明るく)
    tint = hgradient((w, h), [(0.0, (188, 142, 200)), (0.25, (194, 144, 204)), (0.50, (182, 142, 206)),
                              (0.72, (174, 148, 212)), (0.90, (190, 160, 218)), (1.0, (214, 190, 230))])
    # 鎬 (v 0.36) に沿った磨きの光の筋と、峰側のわずかな陰
    shade = vgradient((w, h), [(0.0, (255, 255, 255)), (0.30, (250, 248, 254)), (0.36, (255, 255, 255)),
                               (0.42, (246, 242, 250)), (0.80, (240, 236, 248)), (1.0, (250, 248, 255))])
    img = ImageChops.multiply(tint, shade)
    gr = blur(grain((w, h), along=140, across=3.0, amount=0.9), 1.5)       # 地肌のやわらかな流れ
    img = ImageChops.multiply(img, Image.merge("RGB", [gr.point(lambda v: int(248 + (v - 128) * 0.05))] * 3))

    # ---- 刃文: 刃先の銀白の帯 (のたれ + 互の目)。刃先ほど明るく、境目に淡い紫の匂と光る沸
    hamon = [(0, Y(0.0))]
    ph = rng.uniform(0, math.tau)
    for xi in range(0, w + 1, int(8 * F)):
        u = xi / w
        v = 0.15 + 0.025 * math.sin(u * 46 + ph) + 0.012 * math.sin(u * 151 + ph * 2) + 0.008 * math.sin(u * 377)
        v *= 1.0 if u < 0.9 else max(0.2, 1 - (u - 0.9) * 6)
        hamon.append((xi, Y(v)))
    hamon.append((w, Y(0.0)))
    hm = Image.new("L", (w, h), 0)
    ImageDraw.Draw(hm).polygon(hamon, fill=255)
    hm_soft = blur(hm, 2)
    edge_col = ImageChops.multiply(vgradient((w, h), [(0.0, (244, 242, 250)), (0.12, (228, 224, 236)), (0.2, (214, 208, 228)), (1.0, (214, 208, 228))]),
                                   Image.merge("RGB", [gr.point(lambda v: int(252 + (v - 128) * 0.03))] * 3))
    img.paste(edge_col, (0, 0), hm_soft)
    utsuri = ImageChops.subtract(blur(hm, 18), hm)                     # 刃文の上の霞のような映り
    img.paste((214, 196, 232), (0, 0), utsuri.point(lambda a: a * 0.35))
    nioi = Image.new("L", (w, h), 0)                                     # 匂口: 淡い紫に光る細い線
    ImageDraw.Draw(nioi).line(hamon[1:-1], fill=255, width=int(3 * F))
    nioi = blur(nioi, 2)
    img.paste((206, 180, 236), (0, 0), nioi.point(lambda a: a * 0.6))
    nie = Image.new("L", (w, h), 0)                                      # 沸: 刃文の境目のきらめき
    nd = ImageDraw.Draw(nie)
    for (xa, ya) in hamon[1:-1]:
        for _ in range(2):
            r = rng.uniform(0.5, 1.5) * F
            yy = ya + rng.uniform(-10, 6) * F
            nd.ellipse([xa - r, yy - r, xa + r, yy + r], fill=rng.randint(140, 255))

    # ---- 中央の紫の模様: なめらかに揺らめく炎の形 (形は前と同じ)
    start, end = w * 0.075, w * 0.84

    def squeeze(x):
        head = min(1.0, max(0.05, (x - start) / (w * 0.07))) ** 0.6
        return head * (1.0 - max(0.0, (x - w * 0.60) / (end - w * 0.60)) * 0.85)

    top = flame_edge(start, end, lambda x: Y(0.53 + 0.20 * squeeze(x)), -h * 0.09, w * 0.06, rng)
    bot = flame_edge(start, end, lambda x: Y(0.53 - 0.20 * squeeze(x)), h * 0.09, w * 0.066, rng)
    panel = [(start, Y(0.53))] + top + [(end + w * 0.04, Y(0.54))] + list(reversed(bot))
    hard = Image.new("L", (w, h), 0)
    hd = ImageDraw.Draw(hard)
    hd.polygon(panel, fill=255)
    for _ in range(8):  # 切っ先近くで模様がほどけた炎のすじ
        xs, ln = w * rng.uniform(0.78, 0.88), w * rng.uniform(0.05, 0.10)
        v, th = rng.uniform(0.42, 0.64), h * rng.uniform(0.03, 0.06)
        tongue = []
        for k in range(17):
            tt = k / 16
            tongue.append((xs + ln * tt, Y(v + 0.04 * tt * tt) - th / 2 * (1 - tt) ** 1.3))
        for k in range(16, -1, -1):
            tt = k / 16
            tongue.append((xs + ln * tt, Y(v + 0.04 * tt * tt) + th / 2 * (1 - tt) ** 1.3))
        hd.polygon(tongue, fill=255)
    mask = blur(hard, 1.0)

    # 模様のまわりの淡い紫のオーラ
    halo = ImageChops.subtract(blur(hard, 26), hard)
    img.paste((158, 112, 196), (0, 0), halo.point(lambda a: min(255, a * 0.7)))

    # 模様の中: 星雲 (深い紫に、赤紫と青紫の雲がゆらぐ)。中心ほど深く、縁ほど明るい
    neb = nebula((w, h), rng, [(30, 4, 58), (52, 10, 92), (84, 30, 136), (112, 46, 168), (150, 90, 214)], scale=90)
    tintm = hgradient((w, h), [(0.0, (255, 220, 255)), (0.35, (255, 236, 255)), (0.6, (220, 230, 255)), (1.0, (236, 226, 255))])
    neb = ImageChops.multiply(neb, tintm)
    depth = blur(hard, 18).point(lambda a: max(0, a - 120) * 2)
    rimgrad = Image.new("RGB", (w, h), (104, 58, 156))
    core = Image.composite(neb, Image.blend(neb, rimgrad, 0.6), depth)
    silk = Image.new("L", (w, h), 0)                                     # 模様の中を流れる光の帯
    sd = ImageDraw.Draw(silk)
    for k in range(6):
        v = 0.40 + 0.05 * k
        ph = rng.uniform(0, math.tau)
        pts = [(x, Y(v + 0.05 * math.sin(x / w * 11 + ph) + 0.02 * math.sin(x / w * 37 + ph)))
               for x in range(int(start), int(end), int(8 * F))]
        sd.line(pts, fill=255, width=int(rng.uniform(8, 18) * F))
    silk = blur(silk, 9)
    core.paste((150, 104, 210), (0, 0), silk.point(lambda a: a * 0.30))
    img.paste(core, (0, 0), mask)
    # 縁取り: 内側の細く明るい線 + その内側のやわらかな光
    inner = blur(hard, 3).point(lambda a: 255 if a > 240 else 0)
    rim = blur(ImageChops.subtract(hard, inner), 0.7)
    rim_soft = ImageChops.multiply(blur(rim, 6), hard)
    img.paste((150, 108, 210), (0, 0), rim_soft.point(lambda a: min(255, a * 1.4)))
    img.paste((214, 186, 250), (0, 0), rim)

    # 稲妻: 模様の中を走る、枝分かれする細い光の筋
    bolt = Image.new("L", (w, h), 0)
    bd = ImageDraw.Draw(bolt)
    x = start + w * 0.03
    while x < end - w * 0.08:
        L = w * rng.uniform(0.07, 0.14)
        va, vb = rng.uniform(0.44, 0.62), rng.uniform(0.44, 0.62)
        lightning(bd, (x, Y(va)), (x + L, Y(vb)), rng, 2.0 * F)
        x += L * rng.uniform(0.6, 1.0)
    bolt = ImageChops.multiply(bolt, hard)
    bolt_glow = blur(bolt, 6)
    img.paste((150, 108, 220), (0, 0), bolt_glow.point(lambda a: min(255, a * 1.4)))
    img.paste((236, 222, 255), (0, 0), blur(bolt, 0.6).point(lambda a: a * 0.85))

    # 星: 模様の中は星屑と大小のきらめき、地にはごくまばらな光の粒
    dust_in = stardust((w, h), rng, 2200, 90, area=hard)
    dust_out = stardust((w, h), rng, 500, 12).point(lambda a: a * 0.5)
    dust = ImageChops.lighter(dust_in, dust_out)
    dust_glow = blur(dust, 3)
    img.paste((246, 238, 255), (0, 0), ImageChops.lighter(blur(dust, 0.5), dust_glow.point(lambda a: a * 0.4)))

    # 根元: 飾り板につながる深い紫のグラデーション
    base = Image.new("L", (w, h), 0)
    ImageDraw.Draw(base).rectangle([0, Y(0.95), w * 0.07, Y(0.05)], fill=255)
    img.paste(DEEP, (0, 0), blur(base, 24).point(lambda a: a * 0.6))
    img.paste(GLOW_WHITE, (0, 0), blur(nie, 0.6).point(lambda a: a * 0.7))

    # ---- 発光: 昼は写真の色のまま、暗い所では模様の縁・稲妻・星・刃文が光る
    emis = scale_rgb(ImageChops.multiply(tint, shade), 0.10)   # 地のほのかな光 (地肌の細部は省いてファイルを軽く)
    emis.paste(scale_rgb(edge_col, 0.10), (0, 0), hm_soft)
    emis.paste(scale_rgb(blur(core, 3), 0.35), (0, 0), mask)
    emis.paste((96, 60, 160), (0, 0), halo.point(lambda a: a * 0.6))
    emis.paste((150, 110, 230), (0, 0), rim_soft.point(lambda a: min(255, a * 1.4)))
    emis.paste((226, 200, 255), (0, 0), rim)
    emis.paste(scale_rgb(Image.new("RGB", (w, h), (226, 222, 240)), 0.32), (0, 0), hm_soft.point(lambda a: a * 0.7))
    emis.paste((190, 160, 250), (0, 0), nioi.point(lambda a: a * 0.7))
    emis.paste((160, 120, 240), (0, 0), bolt_glow.point(lambda a: min(255, a * 1.5)))
    emis.paste(GLOW_WHITE, (0, 0), blur(bolt, 0.6))
    emis.paste((200, 180, 255), (0, 0), dust_glow.point(lambda a: a * 0.5))
    emis.paste(GLOW_WHITE, (0, 0), ImageChops.lighter(blur(dust, 0.5), blur(nie, 0.6)))
    maps.put(UV_BLADE, img, emis)

    # 凹凸: 模様はなめらかに彫り込み、縁取りはわずかに盛り上がる。地肌の流れ
    maps.bump(UV_BLADE, blur(hard, 2.5), -0.05)
    maps.bump(UV_BLADE, rim, 0.03)
    maps.bump(UV_BLADE, gr, 0.008)


# ---------------------------------------------------------------- 柄
def soft_mask(small, size, r=2.0):
    """低い解像度の 0/255 マスクを拡大して、なめらかな輪郭にする。"""
    m = small.resize(size, Image.BILINEAR)
    m = blur(m, r).point(lambda a: 255 if a > 127 else 0)
    return blur(m, 0.7)


def draw_handle(maps):
    """柄。handle_tone.png (参考画像の写真から: 0 = 紫, 80 = 金の線, 160 = 前の写真の赤い帯の範囲 = 今は紫) をもとに描く。
    赤い紐は make_katana.py で立体として巻くので、ここでは描かない。
    横 = 鍔側 → 柄頭 (u)、縦 = 一周 (下から 0 = 峰, 0.25 = 表, 0.5 = 刃側, 0.75 = 裏)。"""
    x0, y0, x1, y1 = uv_box(UV_HANDLE)
    w, h = x1 - x0, y1 - y0
    tone = Image.open(HANDLE_TONE).convert("L") if os.path.isfile(HANDLE_TONE) else Image.new("L", (64, 64), 0)
    gold = soft_mask(tone.point(lambda v: 255 if 40 <= v < 120 else 0), (w, h))

    def X(s):   # 写真の長さ (px) → 列
        return (s - HANDLE_S0) / (HANDLE_S1 - HANDLE_S0) * w

    def Y(v):   # 一周の位置 → 行 (上が v = 1)
        return (1 - v) * h

    # 紫の地: つやのある深い紫 (ごく淡いマーブル)
    rng = random.Random(23)
    img = ImageChops.multiply(marble((w, h), (226, 218, 232), (255, 255, 255), scale=90), Image.new("RGB", (w, h), HANDLE_PURPLE))
    img = Image.blend(img, blur(img, 10), 0.6)
    # ごく淡い星雲のゆらぎ (赤紫と青紫) と、かすかな星のきらめき
    # 星雲のゆらぎ (赤紫 → 紫 → 青紫)、細い稲妻、星のきらめき
    neb = nebula((w, h), rng, [(196, 168, 222), (236, 222, 246), (255, 255, 255), (214, 220, 255)], scale=150, detail=3)
    img = seamless_v(ImageChops.multiply(img, neb))
    vein = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vein)
    for k in range(10):                                     # 柄の長さに沿って走る細い稲妻
        xa = rng.uniform(0.02, 0.85) * w
        ya = rng.uniform(0.05, 0.95) * h
        lightning(vd, (xa, ya), (xa + rng.uniform(0.08, 0.16) * w, ya + rng.uniform(-0.12, 0.12) * h), rng, 1.6 * F, depth=6, spread=0.18, branch=0.3)
    vein = seamless_v(ImageChops.multiply(vein, ImageChops.invert(blur(gold, 8).point(lambda a: 255 if a > 10 else 0))))
    vein_glow = blur(vein, 5)
    img.paste((176, 140, 232), (0, 0), vein_glow.point(lambda a: min(255, a * 1.2)))
    img.paste((236, 224, 255), (0, 0), blur(vein, 0.6).point(lambda a: a * 0.75))
    stars = seamless_v(stardust((w, h), rng, 1600, 40))
    star_glow = blur(stars, 3)
    img.paste((240, 230, 255), (0, 0), ImageChops.lighter(blur(stars, 0.5), star_glow.point(lambda a: a * 0.35)).point(lambda a: a * 0.7))

    # ---- 金の線: ふちは濃く、中央は明るい (丸く盛り上がった線)
    core = blur(gold, 10)   # 線の中央ほど明るい
    gold_img = Image.merge("RGB", [core.point([round(lerp_color(list(zip((0.0, 0.5, 1.0), GOLD_PIPE)), v / 255)[k])
                                               for v in range(256)]) for k in range(3)])
    shadow = ImageChops.subtract(blur(gold, 6), gold)              # 線のまわりの影
    img.paste((60, 28, 70), (0, 0), shadow.point(lambda a: min(255, a * 1.2)))
    outline = ImageChops.subtract(blur(gold, 2.5).point(lambda a: 255 if a > 20 else 0), gold)   # 線のふちの細い濃い縁
    img.paste((46, 26, 52), (0, 0), blur(outline, 0.8).point(lambda a: a * 0.85))

    img.paste(gold_img, (0, 0), gold)
    # 金の線の中央の磨いた光の筋と、ところどころのきらめき
    shine = ImageChops.multiply(core.point(lambda a: 255 if a > 225 else 0), gold)
    img.paste((255, 246, 232), (0, 0), blur(shine, 1.2).point(lambda a: a * 0.6))
    glint = ImageChops.multiply(stardust((w, h), rng, 0, 120), gold)
    img.paste((255, 250, 240), (0, 0), blur(glint, 0.6))

    # ---- 柄頭の金の巻きの中の、薄紫の楕円の象眼 (表と裏)
    inl = Image.new("L", (w, h), 0)
    il = ImageDraw.Draw(inl)
    for vc in (INLAY_V, 1 - INLAY_V):
        cx, cy = X(INLAY_S), Y(vc)
        rx, ry = X(INLAY_S + 5) - cx, h * 0.040
        il.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
    inl = blur(inl, 0.8)
    inl_img = ImageChops.multiply(vgradient((w, h), [(0.0, (236, 226, 252)), (1.0, (206, 190, 240))]),
                                  Image.new("RGB", (w, h), (255, 255, 255)))
    img.paste((150, 110, 50), (0, 0), ImageChops.subtract(blur(inl, 5), inl))   # 象眼のふちの影
    img.paste(inl_img, (0, 0), inl)
    # 発光: 地はほのかな紫、金の線はやわらかな金色の光、稲妻と星は強く、象眼は淡く
    emis = Image.new("RGB", (w, h), (8, 5, 12))    # 地のほのかな光 (一色にしてファイルを軽く)
    gold_halo = ImageChops.subtract(blur(gold, 9), gold)
    emis.paste((150, 110, 170), (0, 0), gold_halo.point(lambda a: min(255, a * 1.1)))
    emis.paste(scale_rgb(gold_img, 0.88), (0, 0), gold)
    emis.paste((255, 236, 210), (0, 0), blur(shine, 1.2).point(lambda a: a * 0.6))
    emis.paste((150, 110, 230), (0, 0), vein_glow.point(lambda a: min(255, a * 1.3)))
    emis.paste(GLOW_WHITE, (0, 0), blur(vein, 0.6))
    emis.paste((190, 170, 255), (0, 0), star_glow.point(lambda a: a * 0.5))
    emis.paste(GLOW_WHITE, (0, 0), ImageChops.lighter(blur(stars, 0.5), blur(glint, 0.6)))
    emis.paste((200, 186, 240), (0, 0), inl.point(lambda a: a * 0.7))
    maps.put(UV_HANDLE, img, emis)

    # 凹凸: 金の線は丸く盛り上がる / 象眼はふくらむ
    maps.bump(UV_HANDLE, blur(gold, 4), 0.16)
    maps.bump(UV_HANDLE, blur(inl, 6), 0.10)


# ---------------------------------------------------------------- 小物
def draw_guard(maps):
    """刃の付け根の飾り板。guard_tone.png (80 = 薄い紫, 160 = 濃い紫, 240 = 白い巴の下, 0 = 外・抜け) を描く。
    塗り分けはなめらかな曲線に整えてあり、縁の光る線は太さをそろえて引く。"""
    x0, y0, x1, y1 = uv_box(UV_GUARD)
    S = x1 - x0
    span = max(GUARD_A_MAX - GUARD_A_MIN, GUARD_E_MAX - GUARD_E_MIN)
    w = round(S * (GUARD_A_MAX - GUARD_A_MIN) / span)
    h = round(S * (GUARD_E_MAX - GUARD_E_MIN) / span)
    pad = UV_PAD / (UV_GUARD[2] - UV_GUARD[0])   # make_katana.py の UV は四辺を UV_PAD だけ内側に寄せている
    off = round(S * pad)
    w, h = round(w * (1 - 2 * pad)), round(h * (1 - 2 * pad))
    rng = random.Random(53)
    light_col = (184, 144, 200)          # 写真: 灰みのある薄紫
    img = Image.new("RGB", (S, S), light_col)             # 余白 (側面) は薄紫
    emis = scale_rgb(img, 0.10)
    if not os.path.isfile(GUARD_TONE):
        maps.put(UV_GUARD, img, emis)
        return
    tone = Image.open(GUARD_TONE).convert("L").resize((w, h), Image.BOX)

    def cls(lo, hi):
        m = tone.point(lambda v: 255 if lo <= v < hi else 0)
        return blur(m, 0.25).point(lambda a: 255 if a > 127 else 0)
    body = tone.point(lambda v: 255 if v >= 40 else 0)
    dark = cls(120, 200)
    swirl = cls(200, 256)

    def ring(m, px):                     # 形のふちの、太さ px の線 (外へはみ出さない)
        k = 2 * px + 1
        return blur(ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(k))), 0.5)

    # 薄い紫: 刀身の地とつながる真珠のような薄紫 / 濃い紫: 赤紫と青紫がゆらぐ星雲
    lt = ImageChops.multiply(hgradient((w, h), [(0.0, (190, 146, 204)), (0.5, (184, 144, 206)), (1.0, (188, 142, 200))]),
                             vgradient((w, h), [(0.0, (255, 255, 255)), (1.0, (238, 234, 246))]))
    dk = nebula((w, h), rng, [(30, 4, 58), (50, 12, 90), (78, 28, 128), (104, 48, 160)], scale=45)
    part = lt.copy()
    halo = ImageChops.multiply(ImageChops.subtract(blur(dark, 10), dark), body)   # 濃い紫のまわりの淡いオーラ
    part.paste((160, 116, 200), (0, 0), halo.point(lambda a: a * 0.5))
    part.paste(dk, (0, 0), blur(dark, 0.6))
    rim = ring(dark, int(1.6 * F))                                  # 濃い紫の縁: 太さのそろった光る線
    rim_soft = ImageChops.multiply(blur(rim, 5), dark)              # 線の内側のやわらかな光
    outline = ring(body, int(1.2 * F))                              # 飾り板の輪郭と抜けのふちの細い線
    fade = hgradient((w, h), [(0.0, (255, 255, 255)), ((0.072 - GUARD_A_MIN) / (GUARD_A_MAX - GUARD_A_MIN), (255, 255, 255)),
                              ((0.084 - GUARD_A_MIN) / (GUARD_A_MAX - GUARD_A_MIN), (0, 0, 0)), (1.0, (0, 0, 0))]).convert("L")
    outline = ImageChops.multiply(outline, fade)                    # 刀身と重なる先の方には引かない
    s_halo = ImageChops.multiply(ImageChops.subtract(blur(swirl, 9), swirl), body)   # 白い巴のまわりの光
    part.paste((140, 96, 200), (0, 0), rim_soft.point(lambda a: min(255, a * 1.3)))
    part.paste((176, 140, 236), (0, 0), s_halo.point(lambda a: min(255, a * 1.2)))
    part.paste((222, 198, 255), (0, 0), rim)
    part.paste((214, 190, 252), (0, 0), outline.point(lambda a: a * 0.8))
    dust = stardust((w, h), rng, 700, 26, area=dark)
    dust_glow = blur(dust, 3)
    part.paste((244, 236, 255), (0, 0), ImageChops.lighter(blur(dust, 0.5), dust_glow.point(lambda a: a * 0.4)))
    # 上下反転なし: tone の上 = e の大きい側 (刃側) = UV の上
    img.paste(part, (off, S - off - h))
    e_part = scale_rgb(part, 0.10)
    e_part.paste(scale_rgb(dk, 0.35), (0, 0), dark)
    e_part.paste((96, 60, 160), (0, 0), halo.point(lambda a: a * 0.5))
    e_part.paste((150, 110, 230), (0, 0), rim_soft.point(lambda a: min(255, a * 1.3)))
    e_part.paste((170, 130, 255), (0, 0), s_halo.point(lambda a: min(255, a * 1.4)))
    e_part.paste((232, 212, 255), (0, 0), rim)
    e_part.paste((190, 160, 250), (0, 0), outline.point(lambda a: a * 0.7))
    e_part.paste((200, 180, 255), (0, 0), dust_glow.point(lambda a: a * 0.5))
    e_part.paste(GLOW_WHITE, (0, 0), blur(dust, 0.5))
    emis.paste(e_part, (off, S - off - h))
    maps.put(UV_GUARD, img, emis)
    full = Image.new("L", (S, S), 0)
    full.paste(dark, (off, S - off - h))
    maps.bump(UV_GUARD, blur(full, 2), -0.05)    # 濃い紫は彫り込んだように
    full = Image.new("L", (S, S), 0)
    full.paste(ImageChops.lighter(rim, outline), (off, S - off - h))
    maps.bump(UV_GUARD, full, 0.03)


def draw_white(maps):
    """白く光る巴。"""
    x0, y0, x1, y1 = uv_box(UV_WHITE)
    img = Image.new("RGB", (x1 - x0, y1 - y0), SWIRL_WHITE)
    maps.put(UV_WHITE, img, scale_rgb(img, 0.85))   # 暗い所で白く光る


def draw_tsuba(maps):
    """金色の楕円の鍔 (参考画像の写真どおり)。UV は鍔の楕円を正方形に広げたもの (中心 = 鍔の中心)。
    同心円の細かい磨き目と、ごく細かい槌目 (つちめ)、外側の耳は明るく磨いた金、耳の内側に細い溝。
    面には稲妻の輪の象嵌 (深い紫の漆) と金の小さな星。"""
    x0, y0, x1, y1 = uv_box(UV_TSUBA)
    w, h = x1 - x0, y1 - y0
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.hypot((xx + 0.5) / w * 2 - 1, (yy + 0.5) / h * 2 - 1)          # 0 = 中心, 1 = 外周
    ang = np.arctan2(yy / h - 0.5, xx / w - 0.5)
    rings = np.sin(r * 900 + np.sin(ang * 3) * 0.6) * 0.5 + 0.5            # 磨き目
    hammer = np.asarray(blur(Image.effect_noise((w // int(3 * F), h // int(3 * F)), 60).resize((w, h), Image.BICUBIC), 1.5),
                        dtype=np.float32) / 255.0 - 0.5
    rim = np.clip((r - 0.86) / 0.03, 0, 1)                                 # 耳
    groove = np.exp(-((r - 0.855) / 0.006) ** 2)                            # 耳の内側の溝
    t_col = np.clip(0.42 + 0.08 * (rings - 0.5) + 0.12 * hammer * (1 - rim) + 0.30 * rim - 0.30 * groove, 0, 1)
    del rings, ang
    lut = np.array([lerp_color(TSUBA_GOLD, v / 255) for v in range(256)], dtype=np.uint8)
    img = Image.fromarray(lut[(t_col * 255).astype(np.uint8)], "RGB")
    # 稲妻の輪の象嵌: 二重の細い彫り線の間を、ジグザグの稲妻が一周する。彫りには刀身と同じ深い紫の漆
    rng = random.Random(71)
    inlay = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(inlay)

    def P(rad, a):
        return (w / 2 + rad * w / 2 * math.cos(a), h / 2 + rad * h / 2 * math.sin(a))
    for rad, lw in ((0.575, 3), (0.600, 1.5), (0.800, 1.5), (0.825, 3)):   # 二重の細い彫り線
        d.ellipse([w / 2 - rad * w / 2, h / 2 - rad * h / 2, w / 2 + rad * w / 2, h / 2 + rad * h / 2], outline=255, width=max(1, int(lw * F)))
    dots = Image.new("L", (w, h), 0)
    dd = ImageDraw.Draw(dots)
    nb = 6
    for k in range(nb):                                                # 輪に沿って走る 6 本の稲妻
        a0 = math.tau * k / nb + 0.12
        span = math.tau / nb - 0.34
        segs = 9
        pts = []
        for i in range(segs + 1):
            f = i / segs
            rad = 0.70 + (0.055 if i % 2 else -0.055) * (1 - abs(2 * f - 1)) ** 0.5 + rng.uniform(-0.01, 0.01)
            pts.append(P(rad, a0 + span * f))
        d.line(pts, fill=255, width=int(4 * F), joint="curve")
        bx, by = pts[segs // 2]                                          # 枝
        tx, ty = P(0.70 + rng.choice((-1, 1)) * 0.085, a0 + span * 0.62)
        d.line([(bx, by), ((bx + tx) / 2 + rng.uniform(-4, 4) * F, (by + ty) / 2), (tx, ty)], fill=255, width=int(2.5 * F))
        cx, cy = P(0.70, a0 + span + 0.17)                               # 稲妻の間の金の星
        sparkle(dd, cx, cy, 12 * F)
        dd.ellipse([cx - 2.5 * F, cy - 2.5 * F, cx + 2.5 * F, cy + 2.5 * F], fill=255)
    lac = blur(inlay, 0.8)
    lacquer = ImageChops.multiply(vgradient((w, h), [(0.0, (92, 44, 140)), (1.0, (62, 22, 104))]),
                                  Image.new("RGB", (w, h), (255, 255, 255)))
    img.paste(lacquer, (0, 0), lac)
    img.paste((150, 112, 210), (0, 0), ImageChops.offset(lac, int(-2 * F), int(-2 * F)).point(lambda a: a // 5))   # 漆のつや
    img.paste((252, 228, 196), (0, 0), blur(dots, 0.7))
    emis = Image.new("RGB", (w, h), (0, 0, 0))                          # 暗い所で稲妻の象嵌が紫に、星が金に光る
    emis.paste((80, 50, 150), (0, 0), blur(lac, 6).point(lambda a: min(255, a * 1.2)))
    emis.paste((170, 120, 255), (0, 0), lac)
    emis.paste((255, 220, 170), (0, 0), blur(dots, 0.7))
    emis.paste((150, 110, 70), (0, 0), blur(dots, 5).point(lambda a: min(255, a * 1.5)))
    maps.put(UV_TSUBA, img, emis)
    hgt = Image.fromarray(np.clip((0.5 + hammer * 0.3 * (1 - rim) - 0.8 * groove) * 255, 0, 255).astype(np.uint8), "L")
    maps.bump(UV_TSUBA, hgt, 0.08)
    maps.bump(UV_TSUBA, blur(lac, 1.2), -0.10)
    maps.bump(UV_TSUBA, blur(dots, 1.0), 0.08)


def draw_stud(maps):
    """柄の白い鋲 (真珠のような丸い玉)。中心が明るい放射状のグラデーション。"""
    x0, y0, x1, y1 = uv_box(UV_STUD)
    w, h = x1 - x0, y1 - y0
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.clip(np.hypot((xx + 0.5) / w * 2 - 1, (yy + 0.5) / h * 2 - 1), 0, 1)
    # 写真の白い鋲を真珠のように: 中心は白、外へ淡い桜色 → 薄紫 → ふちにかすかな水色の遊色
    stops = [(0.0, (255, 254, 255)), (0.45, (246, 238, 250)), (0.7, (230, 216, 244)), (0.88, (212, 214, 240)), (1.0, (196, 188, 220))]
    lut = np.array([lerp_color(stops, i / 255) for i in range(256)], np.float32)
    img = lut[(r ** 1.3 * 255).astype(np.uint8)]
    im = Image.fromarray(img.astype(np.uint8), "RGB")
    maps.put(UV_STUD, im, scale_rgb(im, 0.6))          # 真珠のように淡く光る


def draw_cord(maps):
    """赤い紐: 撚った紐の斜めの筋 (縦 = 紐の長さ。紐 1 本の長さ約 33cm を縦いっぱいに)。"""
    x0, y0, x1, y1 = uv_box(UV_CORD)
    w, h = x1 - x0, y1 - y0
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    twist = np.sin((xx / w * 2 + yy / h * 110) * math.tau) * 0.5 + 0.5     # 撚りの筋 (一周に 2 本)
    fine = np.sin((xx / w * 12 - yy / h * 900) * math.tau) * 0.5 + 0.5     # 細い糸
    shade = 0.88 + 0.08 * twist + 0.04 * fine
    img = np.stack([c * shade for c in CORD_RED], -1)
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")
    maps.put(UV_CORD, im, scale_rgb(im, 0.12))         # 暗い所でもほのかに赤が見える
    maps.bump(UV_CORD, Image.fromarray((twist * 255).astype(np.uint8), "L"), 0.035)


def main():
    maps = Maps()
    draw_blade(maps)
    draw_handle(maps)
    draw_guard(maps)
    draw_white(maps)
    draw_tsuba(maps)
    draw_stud(maps)
    draw_cord(maps)
    maps.albedo.save(OUT_ALBEDO, optimize=True)
    # 発光は 4096 で十分 (光のにじみは細部が見えない)。ファイルを軽くするため半分の大きさで保存
    maps.emission.resize((SIZE // 2, SIZE // 2), Image.LANCZOS).save(OUT_EMISSION, optimize=True)
    maps.normal_map().save(OUT_NORMAL, optimize=True)
    for p in (OUT_ALBEDO, OUT_EMISSION, OUT_NORMAL):
        print("saved:", p)


if __name__ == "__main__":
    main()
