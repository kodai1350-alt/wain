"""
ワインボトル (シェリー型 / YŪGEN OLOROSO 2007) 用テクスチャアトラス
WineBottle_Atlas.png を生成するスクリプト。
ボトルの形と質感は参考画像に合わせ、ラベルはオリジナル (架空の銘柄 YŪGEN、2007 年)。

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
BRAND = "YŪGEN"                 # 架空の銘柄 (幽玄)

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
INK = (44, 36, 34)               # 銘柄
INK_SOFT = (118, 102, 92)        # 小さな文字・年号
DEEP_RED = (128, 30, 38)         # 枠・紋章・OLOROSO (シェリーの赤)
GOLD_STOPS = [(0.0, (240, 210, 134)), (0.38, (202, 152, 64)), (0.55, (142, 98, 32)),
              (0.75, (192, 142, 60)), (1.0, (228, 190, 108))]
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


# ---------------------------------------------------------------- 金箔・紋章
def foil(canvas, mask, emboss=3):
    """mask (L) の形に金箔を押したように描く: 影 + ハイライト + 金のグラデーション。"""
    bbox = mask.getbbox()
    if not bbox:
        return
    w, h = canvas.size
    shadow = ImageChops.offset(mask, emboss, emboss).filter(ImageFilter.GaussianBlur(emboss * 0.8))
    canvas.paste((90, 64, 34), (0, 0), shadow.point(lambda a: a * 0.45))
    k = max(1, emboss // 2)
    hi = ImageChops.offset(mask, -k, -k)
    canvas.paste((255, 246, 214), (0, 0), hi.point(lambda a: a * 0.6))
    grad = Image.new("RGB", (1, h))
    y0, y1 = bbox[1], bbox[3]
    for y in range(h):
        t = min(1.0, max(0.0, (y - y0) / max(1, y1 - y0)))
        grad.putpixel((0, y), lerp_color(GOLD_STOPS, t))
    grad = grad.resize((w, h))
    noise = Image.effect_noise((w, h), 30).filter(ImageFilter.GaussianBlur(1.2))  # 金箔の細かいムラ
    grad = Image.blend(grad, Image.merge("RGB", (noise, noise, noise)), 0.06)
    canvas.paste(grad, (0, 0), mask)


def laurel(mask, cx, cy, r, side, leaves=7, leaf=(30, 11)):
    """月桂樹の枝 (片側) を mask に描く。side=-1 で左、1 で右。"""
    lw, lh = leaf
    draw = ImageDraw.Draw(mask)
    # 下 (根元) から上へ円弧に沿って枝を伸ばし、葉を枝の両側に対で付ける
    angles = [-95 + i * (100 / max(1, leaves - 1)) for i in range(leaves)]
    pts = []

    def put_leaf(x, y, rot, w2, h2):
        img = Image.new("L", (w2 * 2 + 4, w2 * 2 + 4), 0)
        ImageDraw.Draw(img).ellipse([2, w2 - h2 + 2, 2 * w2 + 2, w2 + h2 + 2], fill=255)
        img = img.rotate(rot, resample=Image.BICUBIC)
        ox = x + math.cos(math.radians(rot)) * w2 * 0.9
        oy = y - math.sin(math.radians(rot)) * w2 * 0.9
        mask.paste(255, (round(ox - img.width / 2), round(oy - img.height / 2)), img)

    for i, deg in enumerate(angles):
        a = math.radians(deg if side > 0 else 180 - deg)
        x, y = cx + r * math.cos(a), cy - r * math.sin(a)
        pts.append((x, y))
        k = 1.0 - 0.4 * i / max(1, leaves - 1)          # 先端ほど小さく
        w2, h2 = max(2, round(lw * k)), max(1, round(lh * k))
        tangent = math.degrees(a) + (90 if side > 0 else -90)   # 枝の先へ向かう方向
        if i == leaves - 1:
            put_leaf(x, y, tangent, w2, h2)
        else:
            put_leaf(x, y, tangent + 38, w2, h2)
            put_leaf(x, y, tangent - 38, w2, h2)
    draw.line(pts, fill=255, width=max(2, lh // 3), joint="curve")  # 枝


def crest(canvas, cx, cy, s):
    """紋章: 深い赤の盾に金の Y、周りに月桂樹、上に三日月 (幽玄の月)。"""
    w, h = canvas.size
    pts = [(cx - 0.5 * s, cy - 0.55 * s), (cx + 0.5 * s, cy - 0.55 * s), (cx + 0.5 * s, cy + 0.05 * s),
           (cx, cy + 0.62 * s), (cx - 0.5 * s, cy + 0.05 * s)]
    ImageDraw.Draw(canvas).polygon(pts, fill=DEEP_RED)
    m = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(m)
    md.polygon(pts, outline=255, width=max(3, round(s * 0.06)))
    draw_text(md, cx, cy - 0.50 * s, "Y", font(PLAYFAIR, s * 0.70, 700), 255, align="center")
    for side in (-1, 1):
        laurel(m, cx, cy + 0.02 * s, s * 0.78, side, leaves=6, leaf=(round(s * 0.085), round(s * 0.032)))
    # 三日月: 円から少しずらした円を抜く
    mr = s * 0.13
    my = cy - 0.78 * s
    moon = Image.new("L", (w, h), 0)
    ImageDraw.Draw(moon).ellipse([cx - mr, my - mr, cx + mr, my + mr], fill=255)
    ImageDraw.Draw(moon).ellipse([cx - mr + mr * 0.45, my - mr - mr * 0.15, cx + mr + mr * 0.45, my + mr - mr * 0.15], fill=0)
    m = ImageChops.lighter(m, moon)
    foil(canvas, m, emboss=max(2, round(s * 0.02)))


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

    # 画像座標 (y 下向き)。各角を中心に内側へ四分円を回る
    arc(x0, y0, 90, 0)
    arc(x1, y0, 180, 90)
    arc(x1, y1, 270, 180)
    arc(x0, y1, 0, -90)
    return pts


def diamond_rule(md, cx, y, half, thick, gap):
    """中央にひし形の付いた細い罫線。"""
    md.line([(cx - half, y), (cx - gap, y)], fill=255, width=thick)
    md.line([(cx + gap, y), (cx + half, y)], fill=255, width=thick)
    r = thick * 3
    md.polygon([(cx - r, y), (cx, y - r), (cx + r, y), (cx, y + r)], fill=255)


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

    # 枠: 外側に深い赤の太線と細線 (角の切り欠きに沿う)、内側に細い金線、四隅に赤いひし形
    m = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(m)
    for inset, width in ((40, 8), (62, 2)):
        pts = notched_rect(W, H, inset)
        md.line(pts + [pts[0]], fill=255, width=width, joint="curve")
    for x, y in ((150, 150), (W - 151, 150), (W - 151, H - 151), (150, H - 151)):
        r = 14
        md.polygon([(x - r, y), (x, y - r), (x + r, y), (x, y + r)], fill=255)
    ink_texture(canvas, m, DEEP_RED, strength=0.1)
    m = Image.new("L", (W, H), 0)
    pts = notched_rect(W, H, 84)
    ImageDraw.Draw(m).line(pts + [pts[0]], fill=255, width=2, joint="curve")
    foil(canvas, m, emboss=1)

    crest(canvas, cx, H * 0.185, H * 0.135)

    # 銘柄 YŪGEN (長音記号つき)
    m = Image.new("L", (W, H), 0)
    f = font(PLAYFAIR, H * 0.150, 800)
    draw_text(ImageDraw.Draw(m), cx, H * 0.320, BRAND, f, 255, spacing=H * 0.030, align="center")
    ink_texture(canvas, m, INK)

    m = Image.new("L", (W, H), 0)
    diamond_rule(ImageDraw.Draw(m), cx, H * 0.535, W * 0.26, 4, W * 0.02)
    foil(canvas, m, emboss=1)

    d = ImageDraw.Draw(canvas)
    draw_text(d, cx, H * 0.560, "OLOROSO", font(CORMORANT, H * 0.072, 600), DEEP_RED,
              spacing=H * 0.030, align="center")
    draw_text(d, cx, H * 0.665, "SOLERA  GRAN  RESERVA", font(CORMORANT, H * 0.038, 700), INK_SOFT,
              spacing=H * 0.010, align="center")
    draw_text(d, cx, H * 0.725, "JEREZ \u00b7 XÉRÈS \u00b7 SHERRY", font(CORMORANT, H * 0.040, 700), DEEP_RED,
              spacing=H * 0.008, align="center")
    # 年号は控えめに小さく
    draw_text(d, cx, H * 0.792, "\u2014  " + YEAR + "  \u2014", font(CORMORANT, H * 0.036, 600), INK_SOFT,
              spacing=H * 0.006, align="center")
    draw_text(d, cx, H * 0.862, "BODEGAS " + BRAND + "  \u00b7  JEREZ DE LA FRONTERA", font(CORMORANT, H * 0.028, 600),
              INK_SOFT, spacing=H * 0.005, align="center")

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
