"""
刀 (雷電将軍の元素爆発の刀「夢想の一太刀」風, ファンメイド) 用のテクスチャを生成するスクリプト。

1 回の実行で、同じ UV 配置の 3 枚を作ります (どれも 8192x8192):
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
    v 0.38-0.66 / u 0.00-1.00 : 柄 (横 = 鍔側→柄頭, 縦 = 一周。紫の地・金の線・赤い柄巻き)
    v 0.78-0.98 / u 0.00-0.20 : 刃の付け根の飾り板 (濃い紫と薄い紫の炎の模様。上の余白は側面用の薄紫)
    v 0.78-0.98 / u 0.22-0.30 : 白い光 (白い巴)
    v 0.78-0.98 / u 0.32-0.52 : 鍔 (金色の楕円の面)
    v 0.78-0.98 / u 0.54-0.64 : 柄の薄紫の鋲
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
GUARD_TONE = os.path.join(HERE, "guard_tone.png")   # 飾り板の塗り分け (参考画像からなぞったもの)
GUARD_A_MIN, GUARD_A_MAX, GUARD_E_MIN, GUARD_E_MAX = 0.0016, 0.1040, -0.0345, 0.0491
UV_WHITE = (0.22, 0.78, 0.30, 0.98)
UV_TSUBA = (0.32, 0.78, 0.52, 0.98)
UV_STUD = (0.54, 0.78, 0.64, 0.98)
# 柄 (make_katana.py の HANDLE_RINGS と一致させる)。参考画像の写真を柄に沿ってまっすぐにした座標 (px) で配置
HANDLE_TONE = os.path.join(HERE, "handle_tone.png")   # 柄の塗り分け (写真からなぞったもの)
HANDLE_S0, HANDLE_S1 = 8.2, 363.5      # 柄の始まり (鍔の裏) と柄頭
WRAP_S0, WRAP_PERIOD = 144.0, 36.0     # 柄巻きの組紐が表の中央で交差する位置と間隔
WRAP_WINDOWS = ((0, 0), (1, 1), (2, -2), (3, -1))   # 紫がのぞく菱形の窓 (表に 2 つ, 裏に 2 つ)
WIN_HALF_S, WIN_HALF_V = 7.5, 0.105   # 窓の大きさの半分 (長さ方向 px, 一周に対して)。写真では縦長の菱形
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
WRAP_RED = (238, 14, 32)         # 組紐の陰影込みで写真の赤 (202, 10, 26) になる明るさ         # 柄巻きの赤い組紐
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


def draw_blade(maps):
    x0, y0, x1, y1 = uv_box(UV_BLADE)
    w, h = x1 - x0, y1 - y0
    rng = random.Random(11)

    def Y(v):  # v (0 = 刃先, 1 = 峰) → 行
        return h - 1 - v * (h - 1)

    # 地: 根元から切っ先へ、オーロラのようにほのかに色が移ろう (薄紫 → 桜色 → 青みの薄紫)
    tint = hgradient((w, h), [(0.0, (184, 142, 196)), (0.40, (180, 138, 192)), (0.72, (182, 140, 194)),
                              (0.92, (186, 146, 200)), (1.0, (196, 162, 208))])   # 写真: 灰みのある薄紫
    shade = vgradient((w, h), [(0.0, (255, 255, 255)), (0.18, (250, 248, 252)), (0.5, (244, 240, 248)),
                               (0.86, (252, 250, 255)), (1.0, (255, 255, 255))])
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
    hm_soft = blur(hm, 2)        # 写真: 刃先の銀白ははっきりした帯
    img.paste(EDGE_WHITE, (0, 0), hm_soft)
    nioi = Image.new("L", (w, h), 0)                    # 匂口: ごく淡い薄紫のにじみ
    ImageDraw.Draw(nioi).line(hamon[1:-1], fill=255, width=int(4 * F))
    img.paste((204, 186, 216), (0, 0), blur(nioi, 3).point(lambda a: a * 0.5))
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
    img.paste((150, 108, 178), (0, 0), halo.point(lambda a: min(255, a * 0.6)))

    # 模様の中: 中心は深い紫、縁ほど明るく光る宝石のようなグラデーション
    depth = blur(hard, 16).point(lambda a: max(0, a - 128) * 2)
    core = Image.composite(Image.new("RGB", (w, h), (46, 8, 78)), Image.new("RGB", (w, h), (80, 40, 118)), depth)
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
    core.paste((112, 70, 152), (0, 0), silk.point(lambda a: a * 0.35))
    img.paste(core, (0, 0), mask)
    # 縁の内側の光るライン
    rim = ImageChops.subtract(hard, blur(hard, 3).point(lambda a: 255 if a > 240 else 0))
    rim = blur(rim, 0.8)
    img.paste((124, 84, 160), (0, 0), rim)

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
    img.paste((130, 92, 176), (0, 0), bolt_glow.point(lambda a: min(255, a * 1.2)))
    img.paste((200, 176, 230), (0, 0), blur(bolt, 0.6).point(lambda a: a * 0.6))

    # 星屑: 刀身全体に薄く、模様の中は多め
    dust_all = stardust((w, h), rng, 900, 30)
    dust_in = stardust((w, h), rng, 1400, 70, area=hard)
    dust = ImageChops.lighter(dust_all.point(lambda a: a * 0.6), dust_in)
    img.paste((236, 226, 244), (0, 0), ImageChops.lighter(blur(dust, 0.5), blur(dust, 3).point(lambda a: a * 0.3)).point(lambda a: a * 0.5))

    # 根元: 紋のまわりは深い紫のグラデーション
    base = Image.new("L", (w, h), 0)
    ImageDraw.Draw(base).rectangle([0, Y(0.95), w * 0.07, Y(0.05)], fill=255)
    img.paste(DEEP, (0, 0), blur(base, 24).point(lambda a: a * 0.6))
    img.paste(GLOW_WHITE, (0, 0), blur(nie, 0.6).point(lambda a: a * 0.4))

    # 発光: 地はほのかに、模様の縁・稲妻・星屑・刃文は強く
    # 地はピンク寄りの薄紫にほのかに光る (白っぽく濁らないよう色を乗せる)
    emis = scale_rgb(img, 0.14)
    emis.paste(scale_rgb(core, 0.25), (0, 0), mask)
    emis.paste((80, 48, 130), (0, 0), halo.point(lambda a: a * 0.5))
    emis.paste((150, 110, 200), (0, 0), rim)
    emis.paste(scale_rgb(Image.new("RGB", (w, h), EDGE_WHITE), 0.35), (0, 0), hm_soft.point(lambda a: a * 0.6))
    emis.paste((150, 110, 220), (0, 0), bolt_glow.point(lambda a: min(255, a * 1.2)))
    emis.paste(GLOW_WHITE, (0, 0), blur(bolt, 0.6))
    emis.paste(GLOW_WHITE, (0, 0), ImageChops.lighter(blur(dust, 0.5), blur(nie, 0.6)))
    maps.put(UV_BLADE, img, emis)

    # 凹凸: 模様はなめらかにわずか彫り込み (はめ込み細工)
    maps.bump(UV_BLADE, blur(hard, 2.5), -0.04)
    maps.noise(UV_BLADE, 0.006, 3 * F)


# ---------------------------------------------------------------- 柄
def soft_mask(small, size, r=2.0):
    """低い解像度の 0/255 マスクを拡大して、なめらかな輪郭にする。"""
    m = small.resize(size, Image.BILINEAR)
    m = blur(m, r).point(lambda a: 255 if a > 127 else 0)
    return blur(m, 0.7)


def draw_handle(maps):
    """柄。handle_tone.png (参考画像の写真から: 0 = 紫, 80 = 金の線, 160 = 赤い柄巻き) をもとに描く。
    横 = 鍔側 → 柄頭 (u)、縦 = 一周 (下から 0 = 峰, 0.25 = 表, 0.5 = 刃側, 0.75 = 裏)。"""
    x0, y0, x1, y1 = uv_box(UV_HANDLE)
    w, h = x1 - x0, y1 - y0
    rng = random.Random(23)
    tone = Image.open(HANDLE_TONE).convert("L") if os.path.isfile(HANDLE_TONE) else Image.new("L", (64, 64), 0)
    gold = soft_mask(tone.point(lambda v: 255 if 40 <= v < 120 else 0), (w, h))
    red = soft_mask(tone.point(lambda v: 255 if 120 <= v < 200 else 0), (w, h), 1.0)

    def X(s):   # 写真の長さ (px) → 列
        return (s - HANDLE_S0) / (HANDLE_S1 - HANDLE_S0) * w

    def Y(v):   # 一周の位置 → 行 (上が v = 1)
        return (1 - v) * h

    # 紫の地: つやのある深い紫 (ごく淡いマーブル)
    img = ImageChops.multiply(marble((w, h), (226, 218, 232), (255, 255, 255), scale=90), Image.new("RGB", (w, h), HANDLE_PURPLE))
    img = seamless_v(Image.blend(img, blur(img, 10), 0.6))

    # ---- 赤い柄巻き: 斜めに交差する組紐 (菱形の目)。表と裏の中央に、紫がのぞく菱形の窓が 2 つずつ
    hv = 0.125                       # 菱形の高さの半分 (一周に対して)
    m = hv / (WRAP_PERIOD / 2)       # 組紐の傾き (一周 / 写真 px)
    xa, xb = int(X(WRAP_S0 - 20)), int(X(WRAP_S0 + 4 * WRAP_PERIOD + 20))   # 柄巻きのあたりだけ計算する
    yy, xx = np.mgrid[0:h, xa:xb].astype(np.float32)
    S = HANDLE_S0 + xx / w * (HANDLE_S1 - HANDLE_S0)
    V = 1 - yy / h
    p = (S - WRAP_S0) + (V - 0.25) / m
    q = (S - WRAP_S0) - (V - 0.25) / m
    del S, V, yy, xx
    fp, fq = p / WRAP_PERIOD, q / WRAP_PERIOD
    ci, cj = np.floor(fp), np.floor(fq)
    edge = np.maximum(np.abs(fp - ci - 0.5), np.abs(fq - cj - 0.5))   # 目のふちほど 0.5
    fam = ((ci + cj) % 2 == 0)                                   # 組紐の向き (交互)
    # 絹糸の細かい筋 (組紐の向きに沿って)
    thread = np.where(fam, np.sin(fp * math.tau * 14), np.sin(fq * math.tau * 14)) * 0.5 + 0.5
    del p, q, fp, fq, ci, cj, fam
    bulge = np.clip(1 - (edge / 0.5) ** 2, 0, 1)                 # 目ごとのふくらみ
    groove = np.clip((edge - 0.43) / 0.07, 0, 1)                 # 目の境目の溝
    shade = (0.62 + 0.30 * bulge + 0.10 * thread) * (1 - 0.55 * groove)
    rimg = np.stack([c * shade for c in WRAP_RED], -1)
    red_img = Image.new("RGB", (w, h), WRAP_RED)
    red_img.paste(Image.fromarray(np.clip(rimg, 0, 255).astype(np.uint8), "RGB"), (xa, 0))
    rh_part = Image.fromarray(np.clip((0.55 * bulge + 0.12 * thread - 0.5 * groove) * 255, 0, 255).astype(np.uint8), "L")
    rh = Image.new("L", (w, h), 0)
    rh.paste(rh_part, (xa, 0))
    del rimg, shade, bulge, groove, thread, edge
    # 窓の中: 深い紫 + 金のふち + 金の飾り (縦に並ぶ 3 つの玉)
    win_img = Image.new("RGB", (w, h), (78, 40, 104))
    wf = Image.new("L", (w, h), 0)
    wd = ImageDraw.Draw(wf)
    orn = Image.new("L", (w, h), 0)
    od = ImageDraw.Draw(orn)
    for i, j in WRAP_WINDOWS:
        sc = WRAP_S0 + (i + j + 1) * WRAP_PERIOD / 2
        vc = (0.25 + m * (i - j) * WRAP_PERIOD / 2) % 1.0
        hs = WIN_HALF_S
        poly = [(X(sc - hs), Y(vc)), (X(sc), Y(vc + WIN_HALF_V)), (X(sc + hs), Y(vc)), (X(sc), Y(vc - WIN_HALF_V))]
        wd.polygon(poly, outline=255, width=int(5 * F))
        sgn = -1 if vc < 0.5 else 1          # 峰側 (表は v が小さい側, 裏は大きい側)
        bx = X(sc)
        rs = (X(sc + 1) - X(sc))             # 写真 1px の幅
        for dv, rr in ((-0.42, 1.4), (-0.08, 2.0), (0.30, 1.7)):
            by = Y(vc + sgn * dv * WIN_HALF_V)
            od.ellipse([bx - rr * rs, by - rr * rs, bx + rr * rs, by + rr * rs], fill=255)
        by0, by1 = Y(vc + sgn * 0.30 * WIN_HALF_V), Y(vc + sgn * 0.62 * WIN_HALF_V)  # 下の玉からしずく形にすぼまる
        od.polygon([(bx - 1.7 * rs, by0), (bx + 1.7 * rs, by0), (bx, by1)], fill=255)
    win_m = Image.new("L", (w, h), 0)
    wmd = ImageDraw.Draw(win_m)
    for i, j in WRAP_WINDOWS:
        sc = WRAP_S0 + (i + j + 1) * WRAP_PERIOD / 2
        vc = (0.25 + m * (i - j) * WRAP_PERIOD / 2) % 1.0
        wmd.polygon([(X(sc - WIN_HALF_S), Y(vc)), (X(sc), Y(vc + WIN_HALF_V)), (X(sc + WIN_HALF_S), Y(vc)), (X(sc), Y(vc - WIN_HALF_V))], fill=255)
    win_m = blur(win_m, 0.6)
    wf = blur(wf, 0.8)
    orn = blur(orn, 0.8)
    win_img.paste(GOLD_PIPE[1], (0, 0), wf)
    red_img.paste(win_img, (0, 0), win_m)

    # ---- 金の線: ふちは濃く、中央は明るい (丸く盛り上がった線)
    core = blur(gold, 10)   # 線の中央ほど明るい
    gold_img = Image.merge("RGB", [core.point([round(lerp_color(list(zip((0.0, 0.5, 1.0), GOLD_PIPE)), v / 255)[k])
                                               for v in range(256)]) for k in range(3)])
    shadow = ImageChops.subtract(blur(gold, 6), gold)              # 線のまわりの影
    img.paste((60, 28, 70), (0, 0), shadow.point(lambda a: min(255, a * 1.2)))
    outline = ImageChops.subtract(blur(gold, 2.5).point(lambda a: 255 if a > 20 else 0), gold)   # 線のふちの細い濃い縁
    img.paste((46, 26, 52), (0, 0), blur(outline, 0.8).point(lambda a: a * 0.85))

    img.paste(red_img, (0, 0), red)
    for orn_m in (orn,):
        orn_img = Image.merge("RGB", [blur(orn_m, 3).point([round(lerp_color(list(zip((0.0, 0.5, 1.0), GOLD_PIPE)), v / 255)[k])
                                                           for v in range(256)]) for k in range(3)])
        img.paste(orn_img, (0, 0), ImageChops.multiply(orn_m, red))
    img.paste(gold_img, (0, 0), gold)

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
    maps.put(UV_HANDLE, img, Image.new("RGB", (w, h), (0, 0, 0)))

    # 凹凸: 金の線は丸く盛り上がる / 柄巻きは目ごとにふくらみ、境目は溝 / 窓は一段低い / 象眼はふくらむ
    maps.bump(UV_HANDLE, blur(gold, 4), 0.16)
    maps.bump(UV_HANDLE, ImageChops.multiply(rh, red), 0.10)
    maps.bump(UV_HANDLE, ImageChops.multiply(win_m, red), -0.10)
    maps.bump(UV_HANDLE, ImageChops.multiply(blur(orn, 3), red), 0.14)
    maps.bump(UV_HANDLE, blur(inl, 6), 0.10)
    maps.noise(UV_HANDLE, 0.006, 6 * F)


# ---------------------------------------------------------------- 小物
def draw_guard(maps):
    """刃の付け根の飾り板。guard_tone.png (1 = 薄い紫, 2 = 濃い紫, 3 = 白い巴の下) を幻想的な配色で描く。"""
    x0, y0, x1, y1 = uv_box(UV_GUARD)
    S = x1 - x0
    span = max(GUARD_A_MAX - GUARD_A_MIN, GUARD_E_MAX - GUARD_E_MIN)
    w = round(S * (GUARD_A_MAX - GUARD_A_MIN) / span)
    h = round(S * (GUARD_E_MAX - GUARD_E_MIN) / span)
    rng = random.Random(53)
    light_col = (184, 144, 200)          # 写真: 灰みのある薄紫
    img = Image.new("RGB", (S, S), light_col)             # 余白 (側面) は薄紫
    emis = scale_rgb(img, 0.14)
    if os.path.isfile(GUARD_TONE):
        tone = Image.open(GUARD_TONE).convert("L").resize((w, h), Image.NEAREST)
        dark = tone.point(lambda v: 255 if 120 <= v < 200 else 0)
        dark = blur(dark, 4).point(lambda a: 255 if a > 127 else 0)    # 濃い紫の形をなめらかに
        dark = blur(dark, 0.8)
        # 薄い紫: 桜色寄りのグラデーション / 濃い紫: 星雲のような深い紫
        # 薄い紫は白い巴より一段濃く (巴が浮き立つように)
        lt = vgradient((w, h), [(0.0, (190, 150, 206)), (1.0, (176, 136, 194))])
        dk = ImageChops.multiply(marble((w, h), (120, 90, 210), (255, 255, 255), scale=40),
                                 Image.new("RGB", (w, h), (60, 20, 96)))
        dk = Image.blend(dk, blur(dk, 4), 0.5)
        part = lt.copy()
        halo = ImageChops.subtract(blur(dark, 10), dark)     # 濃い紫のまわりの光のにじみ
        part.paste((160, 118, 182), (0, 0), halo.point(lambda a: a * 0.4))
        part.paste(dk, (0, 0), dark)
        dust = stardust((w, h), rng, 260, 10, area=dark)
        part.paste((220, 206, 232), (0, 0), blur(dust, 0.5).point(lambda a: a * 0.5))
        # 上下反転なし: tone の上 = e の大きい側 (刃側) = UV の上
        img.paste(part, (0, S - h))
        e_part = scale_rgb(part, 0.14)
        e_part.paste(scale_rgb(dk, 0.20), (0, 0), dark)
        e_part.paste((90, 56, 140), (0, 0), halo.point(lambda a: a * 0.4))
        e_part.paste(GLOW_WHITE, (0, 0), blur(dust, 0.5))
        emis.paste(e_part, (0, S - h))
        full_dark = Image.new("L", (S, S), 0)
        full_dark.paste(dark, (0, S - h))
        maps.put(UV_GUARD, img, emis)
        maps.bump(UV_GUARD, blur(full_dark, 2), -0.05)    # 濃い紫は彫り込んだように
    else:
        maps.put(UV_GUARD, img, emis)


def draw_white(maps):
    """白く光る巴。"""
    x0, y0, x1, y1 = uv_box(UV_WHITE)
    img = Image.new("RGB", (x1 - x0, y1 - y0), SWIRL_WHITE)
    maps.put(UV_WHITE, img, scale_rgb(img, 0.55))


def draw_tsuba(maps):
    """金色の楕円の鍔 (参考画像の写真どおり)。UV は鍔の楕円を正方形に広げたもの (中心 = 鍔の中心)。
    同心円の細かい磨き目と、ごく細かい槌目 (つちめ)、外側の耳は明るく磨いた金、耳の内側に細い溝。"""
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
    maps.put(UV_TSUBA, img, Image.new("RGB", (w, h), (0, 0, 0)))
    hgt = Image.fromarray(np.clip((0.5 + hammer * 0.3 * (1 - rim) - 0.8 * groove) * 255, 0, 255).astype(np.uint8), "L")
    maps.bump(UV_TSUBA, hgt, 0.08)


def draw_stud(maps):
    """柄の薄紫の鋲 (真珠のような丸い玉)。中心が明るい放射状のグラデーション。"""
    x0, y0, x1, y1 = uv_box(UV_STUD)
    w, h = x1 - x0, y1 - y0
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.clip(np.hypot((xx + 0.5) / w * 2 - 1, (yy + 0.5) / h * 2 - 1), 0, 1)
    c0, c1 = np.array((252, 250, 252), np.float32), np.array((196, 190, 206), np.float32)   # 写真: 白い鋲
    img = c0 + (c1 - c0) * (r[..., None] ** 1.6)
    maps.put(UV_STUD, Image.fromarray(img.astype(np.uint8), "RGB"), Image.new("RGB", (w, h), (0, 0, 0)))


def main():
    maps = Maps()
    draw_blade(maps)
    draw_handle(maps)
    draw_guard(maps)
    draw_white(maps)
    draw_tsuba(maps)
    draw_stud(maps)
    maps.albedo.save(OUT_ALBEDO, optimize=True)
    maps.emission.save(OUT_EMISSION, optimize=True)
    maps.normal_map().save(OUT_NORMAL, optimize=True)
    for p in (OUT_ALBEDO, OUT_EMISSION, OUT_NORMAL):
        print("saved:", p)


if __name__ == "__main__":
    main()
