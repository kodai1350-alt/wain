"""
刀 (雷電将軍の元素爆発の刀「夢想の一太刀」風, ファンメイド) 用のテクスチャを生成するスクリプト。

1 回の実行で、同じ UV 配置の 3 枚を作ります (どれも 8192x8192):
    Katana_Atlas.png     … 色 (ベースカラー)
    Katana_Emission.png  … 発光 (光らせたい所だけ明るい。黒は光らない)
    Katana_Normal.png    … ノーマルマップ (OpenGL 形式 = Unity / Blender と同じ。凹凸の見え方)

Blender ではなく通常の Python で実行します:
    pip install pillow numpy
    python make_katana_texture.py

色は参考画像 (ゲーム画面) から拾っています。

アトラスのレイアウト (UV は左下原点):
    v 0.00-0.36 / u 0.00-1.00 : 刃 (横 = 根元→切っ先, 縦 = 刃先→峰)
    v 0.38-0.66 / u 0.00-1.00 : 柄巻き (横 = 鍔側→柄頭, 縦 = 一周)
    v 0.68-0.76 / u 0.00-1.00 : 金具 (金、唐草の彫り)
    v 0.78-0.98 / u 0.00-0.20 : 三つ巴の紋 (予備)
    v 0.78-0.98 / u 0.22-0.30 : 白い光 (三つ巴・光る玉)
    v 0.78-0.98 / u 0.32-0.52 : 鍔
    v 0.78-0.98 / u 0.54-0.64 : 柄頭の炎 (下 = 根元の白 → 上 = 先端の黄色)
    v 0.78-0.98 / u 0.66-0.86 : 紫のトゲ
    それ以外                    : 濃い紫 (紋の台座・鎺・縁)
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
UV_GOLD = (0.0, 0.68, 1.0, 0.76)
UV_EMBLEM = (0.0, 0.78, 0.20, 0.98)
UV_WHITE = (0.22, 0.78, 0.30, 0.98)
UV_TSUBA = (0.32, 0.78, 0.52, 0.98)
UV_FLAME = (0.54, 0.78, 0.64, 0.98)
UV_FIN = (0.66, 0.78, 0.86, 0.98)

# 色 (参考画像のゲーム画面から)
EDGE_WHITE = (252, 240, 255)     # 刃先・刃文
BLADE_LAV = (230, 198, 253)      # 刃の地 (白〜ピンク寄りの薄紫)
BLADE_LAV_HI = (245, 216, 254)
PANEL = (166, 127, 240)          # 刃の中央の紫の模様
PANEL_DARK = (124, 86, 226)
PANEL_LIGHT = (205, 170, 250)
DEEP = (88, 59, 181)             # トゲ・紋の台座・鎺 (深い紫)
DEEP_LIGHT = (157, 117, 245)
WRAP_DARK = (70, 48, 158)        # 柄のマーブル
WRAP_LIGHT = (142, 112, 226)
SILVER = (230, 224, 240)         # 柄巻きの銀の組紐
SILVER_DARK = (150, 142, 178)
GLOW_WHITE = (255, 250, 255)
GOLD_STOPS = [(0.0, (250, 226, 150)), (0.4, (214, 170, 82)), (0.6, (160, 116, 44)), (1.0, (236, 200, 120))]
GOLD_ENGRAVE = (128, 88, 30)
GOLD_SHINE = (255, 240, 184)

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


def draw_blade(maps):
    x0, y0, x1, y1 = uv_box(UV_BLADE)
    w, h = x1 - x0, y1 - y0
    rng = random.Random(11)

    def Y(v):  # v (0 = 刃先, 1 = 峰) → 行
        return h - 1 - v * (h - 1)

    # 地: 根元から切っ先へ、オーロラのようにほのかに色が移ろう (薄紫 → 桜色 → 青みの薄紫)
    tint = hgradient((w, h), [(0.0, (236, 204, 255)), (0.40, (247, 208, 252)), (0.72, (232, 210, 255)),
                              (0.92, (222, 216, 255)), (1.0, (242, 234, 255))])
    shade = vgradient((w, h), [(0.0, (255, 255, 255)), (0.18, (246, 240, 252)), (0.5, (236, 228, 248)),
                               (0.86, (250, 246, 255)), (1.0, (255, 255, 255))])
    img = ImageChops.multiply(tint, shade)

    # 刃文: 刃先に沿って白く柔らかに光る帯 (のたれ + 互の目)
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
    hm_soft = blur(hm, 5)
    img.paste(EDGE_WHITE, (0, 0), hm_soft)
    nioi = Image.new("L", (w, h), 0)                    # 匂口: ごく淡い薄紫のにじみ
    ImageDraw.Draw(nioi).line(hamon[1:-1], fill=255, width=int(4 * F))
    img.paste((222, 192, 255), (0, 0), blur(nioi, 3).point(lambda a: a * 0.5))
    nie = Image.new("L", (w, h), 0)                     # 沸: 刃文の境目のきらめき
    nd = ImageDraw.Draw(nie)
    for (xa, ya) in hamon[1:-1:2]:
        for _ in range(3):
            r = rng.uniform(0.6, 1.6) * F
            yy = ya + rng.uniform(-8, 8) * F
            nd.ellipse([xa - r, yy - r, xa + r, yy + r], fill=255)

    # 中央の紫の模様: なめらかに揺らめく炎の形
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
    for _ in range(8):  # 切っ先近くで模様がほどけた炎のすじ (なめらかな細い舌)
        xs, ln = w * rng.uniform(0.78, 0.88), w * rng.uniform(0.05, 0.10)
        v, th = rng.uniform(0.42, 0.64), h * rng.uniform(0.03, 0.06)
        tongue = []
        for k in range(17):
            t = k / 16
            tongue.append((xs + ln * t, Y(v + 0.04 * t * t) - th / 2 * (1 - t) ** 1.3))
        for k in range(16, -1, -1):
            t = k / 16
            tongue.append((xs + ln * t, Y(v + 0.04 * t * t) + th / 2 * (1 - t) ** 1.3))
        hd.polygon(tongue, fill=255)
    mask = blur(hard, 1.0)

    # 模様の外側の光のにじみ (ハロー)
    halo = ImageChops.subtract(blur(hard, 22), hard)
    img.paste((226, 176, 255), (0, 0), halo.point(lambda a: min(255, a * 1.4)))

    # 模様の中: 中心は深い紫、縁ほど明るく光る宝石のようなグラデーション
    depth = blur(hard, 16).point(lambda a: max(0, a - 128) * 2)
    core = Image.composite(Image.new("RGB", (w, h), (108, 66, 222)), Image.new("RGB", (w, h), (192, 156, 252)), depth)
    # 模様の中をゆっくり流れる光の帯 (シルクのような)
    silk = Image.new("L", (w, h), 0)
    sd = ImageDraw.Draw(silk)
    for k in range(6):
        v = 0.40 + 0.05 * k
        ph = rng.uniform(0, math.tau)
        pts = [(x, Y(v + 0.05 * math.sin(x / w * 11 + ph) + 0.02 * math.sin(x / w * 37 + ph)))
               for x in range(int(start), int(end), int(8 * F))]
        sd.line(pts, fill=255, width=int(rng.uniform(10, 22) * F))
    silk = blur(silk, 8)
    core.paste((206, 176, 255), (0, 0), silk.point(lambda a: a * 0.35))
    img.paste(core, (0, 0), mask)
    # 縁の内側の光るライン
    rim = ImageChops.subtract(hard, blur(hard, 3).point(lambda a: 255 if a > 240 else 0))
    rim = blur(rim, 0.8)
    img.paste((238, 214, 255), (0, 0), rim)

    # 稲妻: 模様の中を走る、枝分かれする細い光の筋
    bolt = Image.new("L", (w, h), 0)
    bd = ImageDraw.Draw(bolt)
    x = start + w * 0.03
    while x < end - w * 0.08:
        L = w * rng.uniform(0.07, 0.14)
        va, vb = rng.uniform(0.44, 0.62), rng.uniform(0.44, 0.62)
        lightning(bd, (x, Y(va)), (x + L, Y(vb)), rng, 2.2 * F)
        x += L * rng.uniform(0.6, 1.0)
    bolt = ImageChops.multiply(bolt, hard)
    bolt_glow = blur(bolt, 5)
    img.paste((214, 180, 255), (0, 0), bolt_glow.point(lambda a: min(255, a * 2)))
    img.paste((250, 244, 255), (0, 0), blur(bolt, 0.6))

    # 星屑: 刀身全体に薄く、模様の中は多め
    dust_all = stardust((w, h), rng, 900, 30)
    dust_in = stardust((w, h), rng, 1400, 70, area=hard)
    dust = ImageChops.lighter(dust_all.point(lambda a: a * 0.6), dust_in)
    img.paste((255, 250, 255), (0, 0), ImageChops.lighter(blur(dust, 0.5), blur(dust, 3).point(lambda a: a * 0.5)))

    # 根元: 紋のまわりは深い紫のグラデーション
    base = Image.new("L", (w, h), 0)
    ImageDraw.Draw(base).rectangle([0, Y(0.95), w * 0.07, Y(0.05)], fill=255)
    img.paste(DEEP, (0, 0), blur(base, 24).point(lambda a: a * 0.6))
    img.paste(GLOW_WHITE, (0, 0), blur(nie, 0.6).point(lambda a: a * 0.6))

    # 発光: 地はほのかに、模様の縁・稲妻・星屑・刃文は強く
    # 地はピンク寄りの薄紫にほのかに光る (白っぽく濁らないよう色を乗せる)
    emis = scale_rgb(ImageChops.multiply(img, Image.new("RGB", (w, h), (215, 165, 255))), 0.40)
    emis.paste(scale_rgb(core, 0.45), (0, 0), mask)
    emis.paste((150, 96, 230), (0, 0), halo.point(lambda a: a * 0.7))
    emis.paste((236, 210, 255), (0, 0), rim)
    emis.paste(scale_rgb(Image.new("RGB", (w, h), EDGE_WHITE), 0.8), (0, 0), hm_soft.point(lambda a: a * 0.6))
    emis.paste((200, 160, 255), (0, 0), bolt_glow.point(lambda a: min(255, a * 2)))
    emis.paste(GLOW_WHITE, (0, 0), blur(bolt, 0.6))
    emis.paste(GLOW_WHITE, (0, 0), ImageChops.lighter(blur(dust, 0.5), blur(nie, 0.6)))
    maps.put(UV_BLADE, img, emis)

    # 凹凸: 模様はなめらかにわずか彫り込み (はめ込み細工)
    maps.bump(UV_BLADE, blur(hard, 2.5), -0.04)
    maps.noise(UV_BLADE, 0.006, 3 * F)


# ---------------------------------------------------------------- 柄
def draw_handle(maps):
    x0, y0, x1, y1 = uv_box(UV_HANDLE)
    w, h = x1 - x0, y1 - y0
    # 星雲のような柔らかい紫 (大きくゆっくりした雲 + 星のきらめき)
    rng = random.Random(23)
    clouds = marble((w, h), (58, 34, 146), (150, 116, 236), scale=150)
    glow = hgradient((w, h), [(0.0, (255, 255, 255)), (0.5, (232, 226, 246)), (1.0, (214, 204, 238))])
    img = seamless_v(ImageChops.multiply(clouds, glow))
    img = Image.blend(img, blur(img, 12), 0.5)
    stars = seamless_v(stardust((w, h), rng, 700, 25))
    img.paste((236, 222, 255), (0, 0), ImageChops.lighter(blur(stars, 0.5), blur(stars, 3).point(lambda a: a * 0.5)))

    # 銀の組紐: 斜めに交差する帯 (縦方向に一周するので上下でつながる)
    period = w / 9
    band_w = int(h * 0.075)
    masks = []
    for sgn in (1, -1):
        m = Image.new("L", (w, h * 3), 0)
        d = ImageDraw.Draw(m)
        for k in range(-12, 22):
            xa = k * period
            d.line([(xa, 0), (xa + sgn * period * 3, h * 3)], fill=255, width=band_w)
        # 柄の継ぎ目は峰側にあるので、正面 (UV の 1/4 周) で X 字に交差するよう 1/4 周ずらす
        masks.append(ImageChops.offset(m.crop((0, h, w, h * 2)), 0, -(h // 4)))
    band = ImageChops.lighter(*masks)
    # 帯の影 (柄の地に落ちる)
    img.paste(WRAP_DARK, (0, 0), blur(ImageChops.offset(band, int(3 * F), int(4 * F)), 3).point(lambda a: a * 0.6))
    # 組紐の織り目: 帯の向きに対して斜めに細かい縞
    weave = []
    for sgn, m in zip((1, -1), masks):
        band_dir = math.degrees(math.atan2(h * 3, sgn * period * 3))   # 帯の向き
        st = stripes((w, h), band_dir + sgn * 30, 7 * F, sharp=1.5)     # 帯を斜めに横切る縞
        weave.append(ImageChops.multiply(st, m))
    weave_all = ImageChops.lighter(*weave)
    # 真珠のような銀: 長さ方向に淡いピンクと水色がゆらぐ
    pearl = hgradient((w, h), [(i / 18, ((244, 230, 252), (228, 236, 254), (240, 226, 250))[i % 3]) for i in range(19)])
    silver = Image.composite(Image.new("RGB", (w, h), SILVER_DARK), pearl, weave_all.point(lambda a: a * 0.5))
    img.paste(silver, (0, 0), band)
    # 交差点は上を通る帯を少し明るく
    cross = ImageChops.multiply(*masks)
    img.paste(GLOW_WHITE, (0, 0), blur(cross, 1).point(lambda a: a * 0.25))
    maps.put(UV_HANDLE, img, Image.new("RGB", (w, h), (0, 0, 0)))

    # 凹凸: 組紐は盛り上がり、織り目の筋、交差点はさらに高く、マーブルは平ら
    maps.bump(UV_HANDLE, blur(band, 1.5), 0.14)
    maps.bump(UV_HANDLE, weave_all, 0.04)
    maps.bump(UV_HANDLE, blur(cross, 1.5), 0.04)
    maps.noise(UV_HANDLE, 0.01, 6 * F)


# ---------------------------------------------------------------- 金具
def draw_gold(maps):
    x0, y0, x1, y1 = uv_box(UV_GOLD)
    w, h = x1 - x0, y1 - y0
    img = vgradient((w, h), GOLD_STOPS)
    # 唐草の彫り: 波打つ蔓と、交互に巻く渦
    eng = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(eng)
    lw = int(3 * F)
    cy, amp, period = h * 0.5, h * 0.22, h * 1.6
    vine = [(x, cy + amp * math.sin(x / period * math.tau)) for x in range(0, w + 1, int(4 * F))]
    d.line(vine, fill=255, width=lw)
    k = 0
    for x in np.arange(period * 0.25, w, period * 0.5):
        side = 1 if k % 2 == 0 else -1
        k += 1
        bx, by = x, cy + amp * math.sin(x / period * math.tau)
        pts = []
        for i in range(40):
            t = i / 39
            a = side * (t * 2.2 * math.pi)
            r = h * 0.20 * (1 - t * 0.8)
            pts.append((bx + r * math.sin(a) + t * h * 0.12, by - side * (h * 0.20 - r * math.cos(a))))
        d.line(pts, fill=255, width=lw)
        # 小さな葉
        lx, ly = pts[len(pts) // 3]
        d.ellipse([lx - 6 * F, ly - 3 * F, lx + 6 * F, ly + 3 * F], fill=255)
    eng = blur(eng, 0.7)
    img.paste(GOLD_ENGRAVE, (0, 0), eng.point(lambda a: a * 0.8))
    img.paste(GOLD_SHINE, (0, 0), ImageChops.offset(eng, int(-2 * F), int(-2 * F)).point(lambda a: a * 0.35))
    maps.put(UV_GOLD, img, Image.new("RGB", (w, h), (0, 0, 0)))
    maps.bump(UV_GOLD, eng, -0.12)


# ---------------------------------------------------------------- 小物
def draw_white(maps):
    x0, y0, x1, y1 = uv_box(UV_WHITE)
    img = Image.new("RGB", (x1 - x0, y1 - y0), GLOW_WHITE)
    maps.put(UV_WHITE, img, img)


def draw_tsuba(maps):
    """真珠のような光沢の鍔。内側に淡く光る線、縁に彫りの二重線。"""
    x0, y0, x1, y1 = uv_box(UV_TSUBA)
    w, h = x1 - x0, y1 - y0
    img = ImageChops.multiply(
        hgradient((w, h), [(0.0, (250, 236, 255)), (0.35, (238, 226, 255)), (0.65, (252, 236, 250)), (1.0, (236, 230, 255))]),
        vgradient((w, h), [(0.0, (236, 226, 250)), (0.5, (255, 255, 255)), (1.0, (232, 222, 248))]))
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    for inset, lw in ((10, 6), (26, 3)):
        d.rectangle([inset * F, inset * F, w - inset * F, h - inset * F], outline=255, width=int(lw * F))
    m = blur(m, 0.8)
    img.paste((206, 176, 250), (0, 0), m)
    line = Image.new("L", (w, h), 0)
    ImageDraw.Draw(line).line([(40 * F, h / 2), (w - 40 * F, h / 2)], fill=255, width=int(4 * F))
    line = blur(line, 3)
    img.paste((226, 196, 255), (0, 0), line)
    emis = scale_rgb(img, 0.8)
    emis.paste((240, 220, 255), (0, 0), line)
    maps.put(UV_TSUBA, img, emis)
    maps.bump(UV_TSUBA, m, -0.08)


def draw_flame(maps):
    x0, y0, x1, y1 = uv_box(UV_FLAME)
    # 下 (v 小) = 根元の白、上 = 先端の黄色
    img = vgradient((x1 - x0, y1 - y0), [(0.0, (255, 236, 150)), (0.45, (255, 246, 200)), (1.0, (255, 255, 248))])
    maps.put(UV_FLAME, img, img)


def draw_fin(maps):
    """紫のトゲ (横 = 付け根→先端)。付け根は深い紫、先端ほど明るい星雲の色。中央に光る筋、縁は明るく。"""
    x0, y0, x1, y1 = uv_box(UV_FIN)
    w, h = x1 - x0, y1 - y0
    rng = random.Random(41)
    img = ImageChops.multiply(marble((w, h), (120, 90, 210), (255, 255, 255), scale=60),
                              hgradient((w, h), [(0.0, (88, 56, 182)), (0.6, (150, 110, 244)), (1.0, (214, 184, 255))]))
    img = Image.blend(img, blur(img, 6), 0.5)
    vein = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(vein)
    d.line([(0, h * 0.5), (w, h * 0.5)], fill=255, width=int(8 * F))
    for k in range(6):
        xa = w * (0.1 + 0.14 * k)
        d.line([(xa, h * 0.5), (xa + w * 0.12, h * 0.18)], fill=255, width=int(3 * F))
        d.line([(xa, h * 0.5), (xa + w * 0.12, h * 0.82)], fill=255, width=int(3 * F))
    vein = blur(vein, 2)
    rim = Image.new("L", (w, h), 0)
    ImageDraw.Draw(rim).rectangle([0, 0, w - 1, h - 1], outline=255, width=int(14 * F))
    rim = blur(rim, 6)
    img.paste((214, 186, 255), (0, 0), vein.point(lambda a: a * 0.8))
    img.paste((226, 200, 255), (0, 0), rim.point(lambda a: a * 0.6))
    dust = stardust((w, h), rng, 160, 6)
    img.paste((255, 250, 255), (0, 0), blur(dust, 0.5))
    emis = scale_rgb(img, 0.35)
    emis.paste((214, 180, 255), (0, 0), vein)
    emis.paste(GLOW_WHITE, (0, 0), blur(dust, 0.5))
    maps.put(UV_FIN, img, emis)
    maps.bump(UV_FIN, vein, 0.10)


def main():
    maps = Maps()
    draw_blade(maps)
    draw_handle(maps)
    draw_gold(maps)
    draw_white(maps)
    draw_tsuba(maps)
    draw_flame(maps)
    draw_fin(maps)
    maps.albedo.save(OUT_ALBEDO, optimize=True)
    maps.emission.save(OUT_EMISSION, optimize=True)
    maps.normal_map().save(OUT_NORMAL, optimize=True)
    for p in (OUT_ALBEDO, OUT_EMISSION, OUT_NORMAL):
        print("saved:", p)


if __name__ == "__main__":
    main()
