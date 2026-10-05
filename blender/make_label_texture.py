"""
ワインボトル (シェリー型 / WAIN OLOROSO 2007) 用テクスチャアトラス
WineBottle_Atlas.png を生成するスクリプト。
ボトルの形と質感は参考画像に合わせ、ラベルはオリジナル (架空の銘柄 WAIN、2007 年)。

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
BRAND = "WAIN"                  # 架空の銘柄

# make_wine_bottle.py と同じ寸法 (高さ 0.30m / 直径 0.07m 基準)
LABEL_Z = (0.0750, 0.1430)      # ラベル帯の下端 (出っ張りの下) / 上端
LABEL_FRACTION = 0.35           # ラベルが覆う円周の割合
CAPSULE_Z = (0.2410, 0.3000)
CAPSULE_RADIUS = 0.0155
RADIUS = 0.035

UV_LABEL = (0.0, 0.0, 1.0, 0.66)
UV_CAPSULE = (0.0, 0.68, 1.0, 0.86)
UV_GLASS = (0.0, 0.88, 0.70, 1.0)
UV_CAP_TOP = (0.74, 0.88, 0.86, 1.0)

# 色
PAPER = (242, 233, 216)          # クリーム色の紙
INK = (44, 36, 34)               # 銘柄・年号
SEPIA = (112, 84, 62)            # 樽の線画
DEEP_RED = (128, 30, 38)         # 枠・OLOROSO・下の帯 (シェリーの赤)
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
def notched_rect(W, H, inset=0, corner=0.045):
    """四隅が凹んだ長方形 (時計回りの点列)。"""
    r = W * corner
    x0, y0, x1, y1 = inset, inset, W - 1 - inset, H - 1 - inset
    steps = 14
    pts = []

    def arc(cx, cy, a_from, a_to):
        for i in range(steps + 1):
            a = math.radians(a_from + (a_to - a_from) * i / steps)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    # 画像座標 (y 下向き)。左上の角は (x0, y0) を中心に 90°→0° で内側を回る
    arc(x0, y0, 90, 0)          # 左辺上端 → 上辺左端
    arc(x1, y0, 180, 90)        # 上辺右端 → 右辺上端
    arc(x1, y1, 270, 180)       # 右辺下端 → 下辺右端
    arc(x0, y1, 0, -90)         # 下辺左端 → 左辺下端
    return pts


def barrels(md, cx, base_y, s, width):
    """ソレラ (積み重ねた熟成樽) の線画。2 段: 下 3 樽、上 2 樽。"""
    r = s * 0.5
    rows = [(-1, 0, 1), (-0.5, 0.5)]
    for k, row in enumerate(rows):
        cy = base_y - r - k * (r * 1.72)
        for i in row:
            x = cx + i * r * 2.08
            md.ellipse([x - r, cy - r, x + r, cy + r], outline=255, width=width)
            md.ellipse([x - r * 0.80, cy - r * 0.80, x + r * 0.80, cy + r * 0.80], outline=255, width=max(1, width // 2))
            # 鏡板の板目 (縦線) と栓
            for t in (-0.45, 0.0, 0.45):
                h = math.sqrt(max(0.0, 0.64 - t * t)) * r
                md.line([(x + t * r, cy - h), (x + t * r, cy + h)], fill=255, width=max(1, width // 2))
            md.ellipse([x - r * 0.08, cy + r * 0.42, x + r * 0.08, cy + r * 0.58], fill=255)
    # 床の線
    md.line([(cx - r * 3.6, base_y), (cx + r * 3.6, base_y)], fill=255, width=width)


def rule(md, cx, y, half, thick, gap):
    md.line([(cx - half, y), (cx - gap, y)], fill=255, width=thick)
    md.line([(cx + gap, y), (cx + half, y)], fill=255, width=thick)


def label_canvas():
    label_w = 2 * math.pi * RADIUS * LABEL_FRACTION   # 約 0.077m
    label_h = LABEL_Z[1] - LABEL_Z[0]                  # 約 0.068m
    W = 2600
    H = round(W * label_h / label_w)
    cx = W / 2

    shape = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shape).polygon(notched_rect(W, H), fill=255)
    canvas = paper((W, H))
    edge = shape.filter(ImageFilter.GaussianBlur(18))
    canvas = ImageChops.multiply(canvas, Image.merge("RGB", [edge.point(lambda a: 220 + a * 35 // 255)] * 3))

    # 枠: 外側に細い赤線、内側にさらに細い線 (どちらも角の切り欠きに沿う)
    m = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(m)
    for inset, width in ((40, 7), (60, 2)):
        pts = notched_rect(W, H, inset)
        md.line(pts + [pts[0]], fill=255, width=width, joint="curve")
    ink_texture(canvas, m, DEEP_RED, strength=0.1)

    # 下の赤い帯
    band_top, band_bot = H * 0.790, H - 1 - 60
    band = Image.new("L", (W, H), 0)
    ImageDraw.Draw(band).rectangle([60, band_top, W - 61, band_bot], fill=255)
    band = ImageChops.multiply(band, shape)
    canvas.paste(DEEP_RED, (0, 0), band)

    d = ImageDraw.Draw(canvas)
    draw_text(d, cx, H * 0.080, "SOLERA  ESPECIAL", font(CORMORANT, H * 0.048, 700), DEEP_RED,
              spacing=H * 0.012, align="center")

    # ソレラの樽 (セピアの線画)
    m = Image.new("L", (W, H), 0)
    barrels(ImageDraw.Draw(m), cx, H * 0.345, H * 0.098, 5)
    ink_texture(canvas, m, SEPIA, strength=0.12)

    # 銘柄
    m = Image.new("L", (W, H), 0)
    f = font(PLAYFAIR, H * 0.175, 800)
    draw_text(ImageDraw.Draw(m), cx, H * 0.345, BRAND, f, 255, spacing=H * 0.020, align="center")
    ink_texture(canvas, m, INK)

    draw_text(d, cx, H * 0.548, "OLOROSO", font(CORMORANT, H * 0.068, 600), DEEP_RED,
              spacing=H * 0.030, align="center")

    # 年号 (左右に細い線)
    m = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(m)
    f = font(PLAYFAIR, H * 0.085, 700)
    draw_text(md, cx, H * 0.640, YEAR, f, 255, spacing=H * 0.012, align="center")
    yw = text_width(YEAR, f, H * 0.012)
    rule(md, cx, H * 0.695, W * 0.36, 3, yw / 2 + W * 0.03)
    ink_texture(canvas, m, INK, strength=0.1)

    # 赤い帯の中の文字 (クリーム色)
    draw_text(d, cx, H * 0.815, "JEREZ \u00b7 XÉRÈS \u00b7 SHERRY", font(CORMORANT, H * 0.050, 700), PAPER,
              spacing=H * 0.010, align="center")
    draw_text(d, cx, H * 0.885, "BODEGAS " + BRAND + "  \u00b7  JEREZ DE LA FRONTERA", font(CORMORANT, H * 0.030, 600),
              PAPER, spacing=H * 0.005, align="center")

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
