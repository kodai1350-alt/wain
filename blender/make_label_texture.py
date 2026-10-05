"""
ワインボトル (シェリー型 / PEARCHAN OLOROSO) 用テクスチャアトラス
WineBottle_Atlas.png を生成するスクリプト。
ラベルのデザインと色は参考画像 (PEARCHAN OLOROSO) に合わせています。

Blender ではなく通常の Python + Pillow で実行します:
    pip install pillow
    python make_label_texture.py

フォントは fonts/ フォルダの Playfair Display と Cormorant Garamond (どちらも SIL OFL) を使います。

アトラスのレイアウト (UV は左下原点, 2048x2048):
    v 0.00-0.66 / u 0.00-1.00 : 正面ラベル (ボトル正面の円周 35% ぶん)
    v 0.68-0.86 / u 0.00-1.00 : キャップシール側面 (一周)
    v 0.88-1.00 / u 0.00-0.70 : ガラス (縦方向 = 高さのグラデーション)
    v 0.88-1.00 / u 0.74-0.86 : キャップシール天面
make_wine_bottle.py の UV 割り当てはこのレイアウトと下の寸法に合わせてあります。
"""

import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "WineBottle_Atlas.png")
SIZE = 2048
YEAR = "2007"

# make_wine_bottle.py と同じ寸法 (高さ 0.30m / 直径 0.07m 基準)
LABEL_Z = (0.0750, 0.1430)      # ラベル帯の下端 (出っ張りの下) / 上端
LABEL_MAIN_BOTTOM = 0.0815      # 出っ張り以外のラベル下辺
LABEL_FRACTION = 0.35           # ラベルが覆う円周の割合
CAPSULE_Z = (0.2410, 0.3000)
CAPSULE_RADIUS = 0.0138
RADIUS = 0.035

UV_LABEL = (0.0, 0.0, 1.0, 0.66)
UV_CAPSULE = (0.0, 0.68, 1.0, 0.86)
UV_GLASS = (0.0, 0.88, 0.70, 1.0)
UV_CAP_TOP = (0.74, 0.88, 0.86, 1.0)

# 色 (参考画像から)
PAPER = (240, 222, 216)          # 淡いピンクの紙
INK = (66, 58, 58)               # PEARCHAN の濃いグレー
INK_SOFT = (122, 112, 110)       # OLOROSO などの薄いグレー
RED_INK = (192, 66, 58)          # JEREZ - XÉRÈS - SHERRY
CAPSULE = (30, 28, 26)
CAPSULE_DARK = (12, 11, 10)
CAPSULE_HI = (60, 57, 54)
# ガラス: 高さ (m) ごとの色。参考画像の胴の色をそのまま拾ったもの。
# 底は厚みで暗く、ラベルの上に明るい帯、肩は暗く、首はまた少し明るい。
GLASS_STOPS = [
    (0.000, (46, 8, 4)),
    (0.025, (54, 10, 6)),
    (0.070, (68, 17, 11)),
    (0.145, (72, 19, 14)),
    (0.160, (100, 36, 32)),
    (0.175, (80, 27, 25)),
    (0.190, (54, 14, 15)),
    (0.215, (75, 25, 26)),
    (0.241, (89, 31, 30)),
]

FONT_DIR = os.path.join(HERE, "fonts")
PLAYFAIR = os.path.join(FONT_DIR, "PlayfairDisplay-Variable.ttf")
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond-Variable.ttf")

random.seed(2007)


# ---------------------------------------------------------------- 共通
def font(path, size, weight):
    f = ImageFont.truetype(path, round(size))
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


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


def glass_color(z):
    return lerp_color(GLASS_STOPS, z)


def text_width(s, f, spacing):
    return sum(f.getlength(c) for c in s) + spacing * (len(s) - 1)


def draw_text(d, x, y, s, f, fill, spacing=0, align="left"):
    """字間つきで文字を描く (y は文字の上端、align は left / center)。"""
    if align == "center":
        x -= text_width(s, f, spacing) / 2
    for c in s:
        d.text((x, y), c, font=f, fill=fill)
        x += f.getlength(c) + spacing


def fit_size(s, path, weight, max_w, spacing_em, start):
    size = start
    while size > 8:
        if text_width(s, font(path, size, weight), size * spacing_em) <= max_w:
            return size
        size -= 2
    return size


def paper(size, base=PAPER):
    """細かい繊維感のある紙 (印刷面はマット)。"""
    w, h = size
    noise = Image.effect_noise((w, h), 40).filter(ImageFilter.GaussianBlur(0.8))
    grain = ImageChops.multiply(Image.merge("RGB", (noise,) * 3), Image.new("RGB", size, base))
    img = Image.blend(Image.new("RGB", size, base), grain, 0.10)
    img = Image.blend(img, Image.new("RGB", size, base), 0.3)
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(w * h // 9000):
        x, y = random.uniform(0, w), random.uniform(0, h)
        a = random.uniform(0, math.pi)
        ln = random.uniform(6, 22)
        d.line([(x, y), (x + ln * math.cos(a), y + ln * math.sin(a))], fill=(170, 130, 125, 20), width=1)
    return img


def ink_texture(canvas, mask, color, strength=0.18):
    """活版印刷のような、わずかにかすれたインク。"""
    w, h = canvas.size
    noise = Image.effect_noise((w, h), 60).filter(ImageFilter.GaussianBlur(1.0))
    worn = ImageChops.multiply(mask, noise.point(lambda v: 255 if v > 70 else 150))
    layer = Image.new("RGB", (w, h), color)
    canvas.paste(layer, (0, 0), Image.blend(mask, worn, strength))


# ---------------------------------------------------------------- ラベル
def label_shape(W, H, main_bottom):
    """長方形 + 下辺中央の出っ張り (丸い肩でつながる)。"""
    tab_l, tab_r = W * 0.27, W * 0.75
    curve = W * 0.07
    mb, bot = main_bottom, H - 1
    pts = [(0, 0), (W - 1, 0), (W - 1, mb)]
    steps = 24
    for i in range(steps + 1):
        t = i / steps
        pts.append((tab_r + curve * (1 - t), mb + (bot - mb) * (0.5 - 0.5 * math.cos(math.pi * t))))
    for i in range(steps + 1):
        t = i / steps
        pts.append((tab_l - curve * t, bot - (bot - mb) * (0.5 - 0.5 * math.cos(math.pi * t))))
    pts.append((0, mb))
    return pts


def label_canvas():
    label_w = 2 * math.pi * RADIUS * LABEL_FRACTION   # 約 0.077m
    label_h = LABEL_Z[1] - LABEL_Z[0]                  # 約 0.068m
    W = 2600
    H = round(W * label_h / label_w)
    main_bottom = round(H * (LABEL_Z[1] - LABEL_MAIN_BOTTOM) / label_h)

    shape = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shape).polygon(label_shape(W, H, main_bottom), fill=255)
    canvas = paper((W, H))
    # ふちをごくわずかに暗く (紙の厚み感)
    edge = shape.filter(ImageFilter.GaussianBlur(18))
    canvas = ImageChops.multiply(canvas, Image.merge("RGB", [edge.point(lambda a: 220 + a * 35 // 255)] * 3))

    # 参考画像どおり左寄せ (左端から約 8%)
    x0 = W * 0.08

    # PEARCHAN: コントラストの強い太いセリフ体、ラベル幅の約 85%
    sp = 0.02
    size = fit_size("PEARCHAN", PLAYFAIR, 800, W * 0.85, sp, 700)
    m = Image.new("L", (W, H), 0)
    draw_text(ImageDraw.Draw(m), x0, H * 0.205, "PEARCHAN", font(PLAYFAIR, size, 800), 255, spacing=size * sp)
    ink_texture(canvas, m, INK)

    d = ImageDraw.Draw(canvas)
    # OLOROSO: 細めのセリフ、薄いグレー、字間広め
    draw_text(d, x0 + W * 0.005, H * 0.405, "OLOROSO", font(CORMORANT, H * 0.090, 500), INK_SOFT,
              spacing=H * 0.012)
    # 赤い小さな文字 (少し右に下げて配置)
    draw_text(d, W * 0.17, H * 0.585, "JEREZ – XÉRÈS – SHERRY", font(CORMORANT, H * 0.044, 700),
              RED_INK, spacing=H * 0.004)

    # 中央の小さな年号 (参考画像の小さな印の位置)
    cx = W * 0.505
    draw_text(d, cx, H * 0.735, "· " + YEAR + " ·", font(CORMORANT, H * 0.042, 600), INK_SOFT,
              spacing=H * 0.006, align="center")

    # 下の出っ張り: 3 行 (小さい行 / 太字の蔵元名 / 小さい行)
    draw_text(d, cx, H * 0.825, "VINO DE JEREZ", font(CORMORANT, H * 0.032, 600), INK_SOFT,
              spacing=H * 0.008, align="center")
    draw_text(d, cx, H * 0.872, "BODEGAS PEARCHAN", font(PLAYFAIR, H * 0.040, 700), INK,
              spacing=H * 0.006, align="center")
    draw_text(d, cx, H * 0.935, "JEREZ DE LA FRONTERA", font(CORMORANT, H * 0.027, 600), INK_SOFT,
              spacing=H * 0.004, align="center")

    out = Image.new("RGBA", (W, H))
    out.paste(canvas, (0, 0), shape)
    return out


def draw_label(atlas):
    x0, y0, x1, y1 = uv_box(UV_LABEL)
    w, h = x1 - x0, y1 - y0
    bg = Image.new("RGB", (w, h))
    bd = ImageDraw.Draw(bg)
    for y in range(h):  # ラベルの外 (出っ張りの左右) はその高さのガラス色
        z = LABEL_Z[1] - (LABEL_Z[1] - LABEL_Z[0]) * (y + 0.5) / h
        bd.line([(0, y), (w, y)], fill=glass_color(z))
    lab = label_canvas().resize((w, h), Image.LANCZOS)
    bg.paste(lab, (0, 0), lab)
    atlas.paste(bg, (x0, y0))


# ---------------------------------------------------------------- キャップ
def draw_capsule_side(atlas):
    """参考画像どおりの黒いキャップシール。上の方に 2 本の細い溝。"""
    x0, y0, x1, y1 = uv_box(UV_CAPSULE)
    w, h = x1 - x0, y1 - y0
    W = 3000
    H = round(W * (CAPSULE_Z[1] - CAPSULE_Z[0]) / (2 * math.pi * CAPSULE_RADIUS))
    # わずかなムラ (つや消しのフィルム感)
    noise = Image.effect_noise((W, H), 30).filter(ImageFilter.GaussianBlur(2))
    canvas = Image.blend(Image.new("RGB", (W, H), CAPSULE), Image.merge("RGB", (noise,) * 3), 0.03)

    def row(z):  # v は高さに比例して割り当て (make_wine_bottle.py と同じ)
        return H * (CAPSULE_Z[1] - z) / (CAPSULE_Z[1] - CAPSULE_Z[0])

    d = ImageDraw.Draw(canvas)
    for z in (0.2866, 0.2814):
        r = row(z)
        d.line([(0, r - 3), (W, r - 3)], fill=CAPSULE_DARK, width=6)
        d.line([(0, r + 4), (W, r + 4)], fill=CAPSULE_HI, width=3)
    # 下端のふち (少しめくれた感じ)
    d.line([(0, H - 6), (W, H - 6)], fill=CAPSULE_HI, width=4)
    atlas.paste(canvas.resize((w, h), Image.LANCZOS), (x0, y0))


def draw_capsule_top(atlas):
    x0, y0, x1, y1 = uv_box(UV_CAP_TOP)
    pad = 8
    W = 800
    canvas = Image.new("RGB", (W, W), CAPSULE)
    d = ImageDraw.Draw(canvas)
    c = W / 2
    # 天面のふちの、ごく浅い円 (コルクの頭の段差)
    for rr, col in ((0.80, CAPSULE_DARK), (0.77, CAPSULE_HI)):
        d.ellipse([c - c * rr, c - c * rr, c + c * rr, c + c * rr], outline=col, width=4)
    atlas.paste(Image.new("RGB", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), CAPSULE), (x0 - pad, y0 - pad))
    atlas.paste(canvas.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))


def draw_glass(atlas):
    d = ImageDraw.Draw(atlas)
    x0, y0, x1, y1 = uv_box(UV_GLASS)
    h = y1 - y0
    for y in range(y0 - 8, y1):
        t = min(1.0, max(0.0, (y1 - 1 - y) / (h - 1)))  # 下 = 底 (z=0), 上 = キャップ下端
        d.line([x0, y, x1, y], fill=glass_color(t * CAPSULE_Z[0]))


def main():
    atlas = Image.new("RGB", (SIZE, SIZE), glass_color(0.1))
    draw_label(atlas)
    draw_capsule_side(atlas)
    draw_glass(atlas)
    draw_capsule_top(atlas)
    atlas.save(OUT, optimize=True)
    print("saved:", OUT)


if __name__ == "__main__":
    main()
