"""
刀 (雷電将軍の元素爆発の刀「夢想の一太刀」風, ファンメイド) 用テクスチャアトラス
Katana_Atlas.png を生成するスクリプト。

Blender ではなく通常の Python + Pillow で実行します:
    pip install pillow
    python make_katana_texture.py

アトラスのレイアウト (UV は左下原点, 8192x8192):
    v 0.00-0.36 / u 0.00-1.00 : 刃 (横 = 根元→切っ先, 縦 = 刃先→峰)
    v 0.38-0.66 / u 0.00-1.00 : 柄巻き (横 = 鍔側→柄頭, 縦 = 一周)
    v 0.68-0.76 / u 0.00-1.00 : 金具 (金)
    v 0.78-0.98 / u 0.00-0.20 : 三つ巴の紋 (予備。今のモデルは紋を立体で作るので白い光を使う)
    v 0.78-0.98 / u 0.22-0.30 : 白い光 (紋のふち・光る玉)
    v 0.78-0.98 / u 0.32-0.52 : 鍔
    v 0.78-0.98 / u 0.54-0.64 : 柄頭の炎 (下 = 根元の白 → 上 = 先端の黄色)
    v 0.78-0.98 / u 0.66-0.86 : 紫の炎のヒレ
make_katana.py の UV 割り当てはこのレイアウトに合わせてあります。
"""

import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "Katana_Atlas.png")
SIZE = 8192            # 実用上の最大 (Unity の Max Size で 4096 / 2048 などに下げられる)
F = SIZE / 2048        # 線の太さ・ぼかしの量を解像度に合わせる係数

UV_BLADE = (0.0, 0.0, 1.0, 0.36)
UV_HANDLE = (0.0, 0.38, 1.0, 0.66)
UV_GOLD = (0.0, 0.68, 1.0, 0.76)
UV_EMBLEM = (0.0, 0.78, 0.20, 0.98)
UV_WHITE = (0.22, 0.78, 0.30, 0.98)
UV_TSUBA = (0.32, 0.78, 0.52, 0.98)
UV_FLAME = (0.54, 0.78, 0.64, 0.98)
UV_FIN = (0.66, 0.78, 0.86, 0.98)

# 色 (参考画像から)
EDGE_WHITE = (250, 244, 255)
BLADE_LAV = (228, 214, 252)
PANEL = (150, 122, 232)
PANEL_DARK = (116, 88, 210)
PANEL_LIGHT = (184, 160, 244)
WRAP_DARK = (92, 72, 180)
WRAP_LIGHT = (168, 148, 236)
SILVER = (222, 220, 236)
SILVER_DARK = (150, 146, 176)
GLOW_WHITE = (252, 248, 255)
GOLD_STOPS = [(0.0, (250, 226, 150)), (0.4, (214, 170, 82)), (0.6, (160, 116, 44)), (1.0, (236, 200, 120))]

random.seed(37)


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


# ---------------------------------------------------------------- 刃
def flame_edge(x0, x1, base, amp, step, rng):
    """炎のような境界線 (x0→x1)。base(x) が基準の行、炎の先は切っ先側へなびく。"""
    pts = []
    x = x0
    while x < x1:
        a = amp * rng.uniform(0.35, 1.0)
        s = step * rng.uniform(0.6, 1.4)
        # 根元からゆるく立ち上がり、先へ鋭く伸びて、急に戻る (なめらかな炎の舌)
        for k in range(8):
            t = k / 8
            lift = math.sin(t * math.pi / 2) ** 2
            pts.append((x + s * t * 0.85, base(x + s * t * 0.85) + a * lift))
        pts.append((x + s * 0.85, base(x + s * 0.85) + a))
        pts.append((x + s, base(x + s)))
        x += s
    pts.append((x1, base(x1)))
    return pts


def draw_blade(atlas):
    x0, y0, x1, y1 = uv_box(UV_BLADE)
    w, h = x1 - x0, y1 - y0

    def Y(v):  # v (0 = 刃先, 1 = 峰) → 行
        return h - 1 - v * (h - 1)

    # 地: 刃先は白、中ほどは薄紫、峰に向かってわずかに濃く
    img = vgradient((w, h), [(0.0, (232, 216, 254)), (0.12, BLADE_LAV), (0.86, (240, 232, 255)), (1.0, EDGE_WHITE)])
    d = ImageDraw.Draw(img)

    # 中央の紫の帯 (上下の縁が炎のようにギザギザ)
    rng = random.Random(5)
    start, end = w * 0.075, w * 0.84

    def squeeze(x):  # 根元はとがって始まり、先 (切っ先側) へ行くほど帯が細くなる
        head = min(1.0, max(0.05, (x - start) / (w * 0.07))) ** 0.6
        return head * (1.0 - max(0.0, (x - w * 0.60) / (end - w * 0.60)) * 0.85)

    top = flame_edge(start, end, lambda x: Y(0.52 + 0.22 * squeeze(x)), -h * 0.10, w * 0.055, rng)
    bot = flame_edge(start, end, lambda x: Y(0.52 - 0.22 * squeeze(x)), h * 0.10, w * 0.062, rng)
    panel = [(start, Y(0.52))] + top + [(end + w * 0.04, Y(0.53))] + list(reversed(bot))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).polygon(panel, fill=255)
    img.paste(PANEL, (0, 0), mask)

    # 帯の中の濃い筋と明るい筋 (なびく炎)
    streak = Image.new("L", (w, h), 0)
    sd = ImageDraw.Draw(streak)
    for k in range(7):
        v = 0.36 + 0.06 * k
        ph = rng.uniform(0, math.tau)
        pts = [(x, Y(v + 0.035 * math.sin(x / w * 18 + ph))) for x in range(int(start), int(end), int(6 * F))]
        sd.line(pts, fill=255, width=int(rng.randint(6, 14) * F))
    streak = ImageChops.multiply(streak, mask).filter(ImageFilter.GaussianBlur(3 * F))
    img.paste(PANEL_DARK, (0, 0), streak.point(lambda a: a * 0.7))
    light = Image.new("L", (w, h), 0)
    ld = ImageDraw.Draw(light)
    for k in range(4):
        v = 0.42 + 0.08 * k
        ph = rng.uniform(0, math.tau)
        pts = [(x, Y(v + 0.03 * math.sin(x / w * 23 + ph))) for x in range(int(start), int(end), int(6 * F))]
        ld.line(pts, fill=255, width=int(4 * F))
    light = ImageChops.multiply(light, mask).filter(ImageFilter.GaussianBlur(1.5 * F))
    img.paste(PANEL_LIGHT, (0, 0), light)

    # 切っ先近く: 帯がほどけて炎のすじになる
    wisp = Image.new("L", (w, h), 0)
    wd = ImageDraw.Draw(wisp)
    for k in range(9):
        xs = w * rng.uniform(0.78, 0.90)
        ln = w * rng.uniform(0.04, 0.09)
        v = rng.uniform(0.38, 0.66)
        th = h * rng.uniform(0.04, 0.08)
        wd.polygon([(xs, Y(v) - th / 2), (xs + ln, Y(v + 0.05)), (xs, Y(v) + th / 2)], fill=255)
    img.paste(PANEL, (0, 0), wisp.filter(ImageFilter.GaussianBlur(1 * F)))

    # 根元: 紫を濃くして三つ巴の紋のまわりに影
    base = Image.new("L", (w, h), 0)
    ImageDraw.Draw(base).rectangle([0, Y(0.95), w * 0.07, Y(0.05)], fill=255)
    img.paste(PANEL_DARK, (0, 0), base.filter(ImageFilter.GaussianBlur(20 * F)).point(lambda a: a * 0.5))

    # 全体をほんの少しぼかして光っている感じに
    glow = img.filter(ImageFilter.GaussianBlur(4 * F))
    img = Image.blend(img, glow, 0.25)
    atlas.paste(img, (x0, y0))


# ---------------------------------------------------------------- 柄
def marble(size, c0, c1, scale=40):
    w, h = size
    scale = int(scale * F)
    n1 = Image.effect_noise((max(1, w // scale), max(1, h // scale)), 80).resize((w, h), Image.BICUBIC)
    n2 = Image.effect_noise((max(1, w // (scale // 3)), max(1, h // (scale // 3))), 60).resize((w, h), Image.BICUBIC)
    n = ImageChops.add(n1.point(lambda v: v * 0.7), n2.point(lambda v: v * 0.3))
    n = n.filter(ImageFilter.GaussianBlur(3 * F))
    lut = [lerp_color([(0.0, c0), (0.5, ((c0[0] + c1[0]) // 2, (c0[1] + c1[1]) // 2, (c0[2] + c1[2]) // 2)), (1.0, c1)],
                      min(1.0, max(0.0, (v - 70) / 120))) for v in range(256)]
    r = n.point([c[0] for c in lut])
    g = n.point([c[1] for c in lut])
    b = n.point([c[2] for c in lut])
    return Image.merge("RGB", (r, g, b))


def draw_handle(atlas):
    x0, y0, x1, y1 = uv_box(UV_HANDLE)
    w, h = x1 - x0, y1 - y0
    img = marble((w, h), WRAP_DARK, WRAP_LIGHT)
    # 銀の柄巻き: 斜めに交差する帯 (縦方向に一周するので上下でつながる)
    band = Image.new("L", (w, h * 3), 0)
    bd = ImageDraw.Draw(band)
    period = w / 9
    for k in range(-12, 22):
        xa = k * period
        for sgn in (1, -1):
            bd.line([(xa, 0), (xa + sgn * period * 3, h * 3)], fill=255, width=int(h * 0.075))
    band = band.crop((0, h, w, h * 2))
    img.paste(SILVER_DARK, (0, 0), ImageChops.offset(band, int(2 * F), int(3 * F)).filter(ImageFilter.GaussianBlur(2 * F)))
    img.paste(SILVER, (0, 0), band)
    # 帯の上の細かい模様 (点線)
    dots = Image.new("L", (w, h), 0)
    dd = ImageDraw.Draw(dots)
    step = int(9 * F)
    for x in range(0, w, step):
        for y in range(0, h, step):
            dd.rectangle([x, y, x + F - 1, y + F - 1], fill=255)
    img.paste(SILVER_DARK, (0, 0), ImageChops.multiply(dots, band))
    atlas.paste(img, (x0, y0))


# ---------------------------------------------------------------- 小物
def draw_gold(atlas):
    x0, y0, x1, y1 = uv_box(UV_GOLD)
    atlas.paste(vgradient((x1 - x0, y1 - y0), GOLD_STOPS), (x0, y0))


def tomoe(d, cx, cy, R, rot, fill):
    """巴 1 つ (頭の円 + 尾)。"""
    # 尾は頭から外周に沿って伸び、外側の線と内側の線が外周近くで合わさって細くなる
    pts = []
    n = 48
    sweep = math.radians(105)
    for i in range(n + 1):           # 外側の線 (頭 → 尾の先)
        t = i / n
        a = rot + t * sweep
        r = R * (0.84 - 0.04 * t)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    for i in range(n, -1, -1):       # 内側の線 (尾の先 → 頭)
        t = i / n
        a = rot + t * sweep
        r = R * (0.28 + 0.52 * t ** 0.8)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=fill)
    hx, hy = cx + R * 0.56 * math.cos(rot), cy + R * 0.56 * math.sin(rot)
    hr = R * 0.28
    d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=fill)


def draw_emblem(atlas):
    x0, y0, x1, y1 = uv_box(UV_EMBLEM)
    S = x1 - x0
    W = S * 3
    img = Image.new("RGB", (W, W), PANEL_DARK)
    d = ImageDraw.Draw(img)
    c = W / 2
    d.ellipse([c - c * 0.96, c - c * 0.96, c + c * 0.96, c + c * 0.96], fill=PANEL)
    m = Image.new("L", (W, W), 0)
    md = ImageDraw.Draw(m)
    md.ellipse([c - c * 0.96, c - c * 0.96, c + c * 0.96, c + c * 0.96], outline=255, width=int(W * 0.035))
    for i in range(3):
        tomoe(md, c, c, c * 0.88, math.radians(90 + 120 * i), 255)
    glow = m.filter(ImageFilter.GaussianBlur(W * 0.02))
    img.paste((214, 196, 255), (0, 0), glow)
    img.paste(GLOW_WHITE, (0, 0), m)
    atlas.paste(img.resize((S, y1 - y0), Image.LANCZOS), (x0, y0))


def draw_white(atlas):
    x0, y0, x1, y1 = uv_box(UV_WHITE)
    ImageDraw.Draw(atlas).rectangle([x0, y0, x1, y1], fill=GLOW_WHITE)


def draw_tsuba(atlas):
    x0, y0, x1, y1 = uv_box(UV_TSUBA)
    w, h = x1 - x0, y1 - y0
    img = vgradient((w, h), [(0.0, (236, 226, 255)), (0.5, GLOW_WHITE), (1.0, (230, 218, 252))])
    d = ImageDraw.Draw(img)
    d.rectangle([6 * F, 6 * F, w - 7 * F, h - 7 * F], outline=(200, 182, 246), width=int(6 * F))
    atlas.paste(img, (x0, y0))


def draw_flame(atlas):
    x0, y0, x1, y1 = uv_box(UV_FLAME)
    # 下 (v 小) = 根元の白、上 = 先端の黄色
    img = vgradient((x1 - x0, y1 - y0), [(0.0, (255, 236, 150)), (0.45, (255, 246, 200)), (1.0, (255, 255, 248))])
    atlas.paste(img, (x0, y0))


def draw_fin(atlas):
    x0, y0, x1, y1 = uv_box(UV_FIN)
    w, h = x1 - x0, y1 - y0
    img = marble((w, h), PANEL_DARK, PANEL_LIGHT, scale=20)
    atlas.paste(img, (x0, y0))


def main():
    atlas = Image.new("RGB", (SIZE, SIZE), PANEL_DARK)
    draw_blade(atlas)
    draw_handle(atlas)
    draw_gold(atlas)
    draw_emblem(atlas)
    draw_white(atlas)
    draw_tsuba(atlas)
    draw_flame(atlas)
    draw_fin(atlas)
    atlas.save(OUT, optimize=True)
    print("saved:", OUT)


if __name__ == "__main__":
    main()
