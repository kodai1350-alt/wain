"""
ワインボトル (シェリー型 / PEARCHAN OLOROSO) 用テクスチャアトラス
WineBottle_Atlas.png を生成するスクリプト。

Blender ではなく通常の Python + Pillow で実行します:
    pip install pillow
    python make_label_texture.py

フォントは fonts/ フォルダの Cinzel と Cormorant Garamond (どちらも SIL OFL) を使います。

アトラスのレイアウト (UV は左下原点, 2048x2048):
    v 0.00-0.56 / u 0.00-1.00 : 正面ラベル (ボトル正面の円周 35% ぶん)
    v 0.58-0.68 / u 0.00-1.00 : ネックラベル (首を一周)
    v 0.70-0.86 / u 0.00-1.00 : キャップシール側面 (一周)
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
NECK_Z = (0.2140, 0.2360)       # ネックラベル
NECK_RADIUS = 0.0152            # ネックラベル部分の平均半径
CAPSULE_Z = (0.2410, 0.3000)
CAPSULE_RADIUS = 0.0138
RADIUS = 0.035

UV_LABEL = (0.0, 0.0, 1.0, 0.56)
UV_NECK = (0.0, 0.58, 1.0, 0.68)
UV_CAPSULE = (0.0, 0.70, 1.0, 0.86)
UV_GLASS = (0.0, 0.88, 0.70, 1.0)
UV_CAP_TOP = (0.74, 0.88, 0.86, 1.0)

# 色
IVORY = (236, 227, 207)
INK = (30, 25, 23)
INK_SOFT = (88, 76, 68)
BURGUNDY = (112, 22, 30)
BLACK = (10, 9, 9)
BLACK_HI = (36, 34, 33)
GOLD_STOPS = [(0.0, (240, 210, 134)), (0.38, (202, 152, 64)), (0.55, (142, 98, 32)),
              (0.75, (192, 142, 60)), (1.0, (228, 190, 108))]
# ガラス: 高さ (m) ごとの色。オロロソの深いマホガニー、底は厚みで暗く、首は少し明るく。
GLASS_STOPS = [
    (0.000, (20, 5, 3)),
    (0.025, (30, 8, 4)),
    (0.070, (44, 12, 6)),
    (0.150, (48, 14, 7)),
    (0.185, (42, 11, 6)),
    (0.205, (58, 19, 11)),
    (0.241, (70, 25, 15)),
]

FONT_DIR = os.path.join(HERE, "fonts")
CINZEL = os.path.join(FONT_DIR, "Cinzel-Variable.ttf")
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


def draw_text(d, cx, y, s, f, fill=255, spacing=0):
    """中央揃え・字間つきで文字を描く (y は文字の上端)。"""
    x = cx - text_width(s, f, spacing) / 2
    for c in s:
        d.text((x, y), c, font=f, fill=fill)
        x += f.getlength(c) + spacing


def fit_size(s, path, weight, max_w, spacing_em, start):
    size = start
    while size > 8:
        f = font(path, size, weight)
        if text_width(s, f, size * spacing_em) <= max_w:
            return size
        size -= 2
    return size


def foil(canvas, mask, emboss=3):
    """mask (L) の形に金箔を押したように描く: 影 + ハイライト + 金のグラデーション。"""
    bbox = mask.getbbox()
    if not bbox:
        return
    w, h = canvas.size
    shadow = ImageChops.offset(mask, emboss, emboss).filter(ImageFilter.GaussianBlur(emboss * 0.8))
    canvas.paste((70, 48, 20), (0, 0), shadow.point(lambda a: a * 0.55))
    k = max(1, emboss // 2)
    hi = ImageChops.offset(mask, -k, -k)
    canvas.paste((255, 246, 214), (0, 0), hi.point(lambda a: a * 0.6))
    grad = Image.new("RGB", (1, h))
    y0, y1 = bbox[1], bbox[3]
    for y in range(h):
        t = min(1.0, max(0.0, (y - y0) / max(1, y1 - y0)))
        grad.putpixel((0, y), lerp_color(GOLD_STOPS, t))
    grad = grad.resize((w, h))
    # 金箔の細かいムラ
    noise = Image.effect_noise((w, h), 30).filter(ImageFilter.GaussianBlur(1.2))
    grad = Image.blend(grad, Image.merge("RGB", (noise, noise, noise)), 0.06)
    canvas.paste(grad, (0, 0), mask)


def new_mask(size):
    m = Image.new("L", size, 0)
    return m, ImageDraw.Draw(m)


def paper(size, base=IVORY):
    """細かい繊維感のある紙。"""
    w, h = size
    noise = Image.effect_noise((w, h), 40).filter(ImageFilter.GaussianBlur(0.8))
    grain = ImageChops.multiply(Image.merge("RGB", (noise,) * 3), Image.new("RGB", size, base))
    img = Image.blend(Image.new("RGB", size, base), grain, 0.12)
    img = Image.blend(img, Image.new("RGB", size, base), 0.3)
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(w * h // 9000):
        x, y = random.uniform(0, w), random.uniform(0, h)
        a = random.uniform(0, math.pi)
        ln = random.uniform(6, 22)
        d.line([(x, y), (x + ln * math.cos(a), y + ln * math.sin(a))], fill=(150, 130, 100, 22), width=1)
    return img


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
    """盾形の紋章 (バーガンディの地に金の P、周りに月桂樹)。"""
    w, h = canvas.size
    pts = [(cx - 0.5 * s, cy - 0.55 * s), (cx + 0.5 * s, cy - 0.55 * s), (cx + 0.5 * s, cy + 0.05 * s),
           (cx, cy + 0.62 * s), (cx - 0.5 * s, cy + 0.05 * s)]
    ImageDraw.Draw(canvas).polygon(pts, fill=BURGUNDY)
    m, md = new_mask((w, h))
    md.polygon(pts, outline=255, width=max(3, round(s * 0.06)))
    draw_text(md, cx, cy - 0.47 * s, "P", font(CINZEL, s * 0.62, 700))
    for side in (-1, 1):
        laurel(m, cx, cy + 0.02 * s, s * 0.78, side, leaves=6, leaf=(round(s * 0.085), round(s * 0.032)))
    foil(canvas, m, emboss=max(2, round(s * 0.02)))


def diamond_rule(md, cx, y, half, thick, gap=0):
    md.line([(cx - half, y), (cx - gap - thick * 4, y)], fill=255, width=thick)
    md.line([(cx + gap + thick * 4, y), (cx + half, y)], fill=255, width=thick)
    r = thick * 3
    md.polygon([(cx - r, y), (cx, y - r), (cx + r, y), (cx, y + r)], fill=255)


# ---------------------------------------------------------------- ラベル
def label_shape(W, H, main_bottom, inset=0):
    """長方形 + 下辺中央の出っ張り (丸い肩でつながる)。inset で内側にずらす。"""
    tab_l, tab_r = W * 0.30, W * 0.70
    curve = W * 0.06
    top, left, right = inset, inset, W - 1 - inset
    mb, bot = main_bottom - inset, H - 1 - inset
    pts = [(left, top), (right, top), (right, mb)]
    steps = 24
    for i in range(steps + 1):
        t = i / steps
        pts.append((tab_r - inset * 0.6 + curve * (1 - t), mb + (bot - mb) * (0.5 - 0.5 * math.cos(math.pi * t))))
    for i in range(steps + 1):
        t = i / steps
        pts.append((tab_l + inset * 0.6 - curve * t, bot - (bot - mb) * (0.5 - 0.5 * math.cos(math.pi * t))))
    pts.append((left, mb))
    return pts


def label_canvas():
    label_w = 2 * math.pi * RADIUS * LABEL_FRACTION   # 約 0.077m
    label_h = LABEL_Z[1] - LABEL_Z[0]                  # 約 0.068m
    W = 2600
    H = round(W * label_h / label_w)
    main_bottom = round(H * (LABEL_Z[1] - LABEL_MAIN_BOTTOM) / label_h)
    cx = W / 2

    shape, sd = new_mask((W, H))
    sd.polygon(label_shape(W, H, main_bottom), fill=255)
    canvas = paper((W, H))
    # ふちをわずかに暗く (紙の厚み感)
    edge = shape.filter(ImageFilter.GaussianBlur(26))
    canvas = ImageChops.multiply(canvas, Image.merge("RGB", [edge.point(lambda a: 205 + a * 50 // 255)] * 3))

    # 金の二重罫 (外形に沿う)
    m, md = new_mask((W, H))
    for inset, width in ((34, 9), (54, 3)):
        pts = label_shape(W, H, main_bottom, inset)
        md.line(pts + [pts[0]], fill=255, width=width, joint="curve")
    foil(canvas, m, emboss=3)

    d = ImageDraw.Draw(canvas)
    crest(canvas, cx, H * 0.150, H * 0.150)

    # 銘柄 (わずかに浮き出したような影つき)
    sp = 0.10
    size = fit_size("PEARCHAN", CINZEL, 700, W * 0.80, sp, 520)
    f = font(CINZEL, size, 700)
    y = H * 0.275
    draw_text(d, cx + 3, y + 4, "PEARCHAN", f, fill=(196, 184, 160), spacing=size * sp)
    draw_text(d, cx, y, "PEARCHAN", f, fill=INK, spacing=size * sp)

    m, md = new_mask((W, H))
    diamond_rule(md, cx, H * 0.475, W * 0.30, 5, gap=10)
    foil(canvas, m, emboss=2)

    draw_text(d, cx, H * 0.505, "OLOROSO", font(CORMORANT, H * 0.090, 600), fill=INK, spacing=H * 0.030)
    draw_text(d, cx, H * 0.618, "JEREZ · XÉRÈS · SHERRY", font(CORMORANT, H * 0.052, 600),
              fill=BURGUNDY, spacing=H * 0.010)

    # 年号 (金箔)
    m, md = new_mask((W, H))
    f = font(CINZEL, H * 0.120, 700)
    draw_text(md, cx, H * 0.680, YEAR, f, spacing=H * 0.018)
    yr_w = text_width(YEAR, f, H * 0.018)
    for sgn in (-1, 1):
        md.line([(cx + sgn * (yr_w / 2 + W * 0.03), H * 0.750), (cx + sgn * (yr_w / 2 + W * 0.20), H * 0.750)],
                fill=255, width=4)
    foil(canvas, m, emboss=3)

    draw_text(d, cx, H * 0.815, "SOLERA  GRAN  RESERVA", font(CORMORANT, H * 0.038, 700),
              fill=INK_SOFT, spacing=H * 0.010)
    draw_text(d, cx, H * 0.912, "BODEGAS PEARCHAN", font(CORMORANT, H * 0.030, 700),
              fill=INK_SOFT, spacing=H * 0.005)

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


# ---------------------------------------------------------------- ネックラベル
def draw_neck(atlas):
    x0, y0, x1, y1 = uv_box(UV_NECK)
    w, h = x1 - x0, y1 - y0
    W = 4000
    H = round(W * (NECK_Z[1] - NECK_Z[0]) / (2 * math.pi * NECK_RADIUS))
    noise = Image.effect_noise((W, H), 20).filter(ImageFilter.GaussianBlur(1))
    canvas = Image.blend(Image.new("RGB", (W, H), BLACK), Image.merge("RGB", (noise,) * 3), 0.03)
    for y, t in ((H * 0.10, 6), (H * 0.19, 2), (H * 0.81, 2), (H * 0.90, 6)):
        rule, rd = new_mask((W, H))
        rd.line([(0, y), (W, y)], fill=255, width=t)
        foil(canvas, rule, emboss=1)
    m, md = new_mask((W, H))
    # 正面 (u=0.5) に年号、左右に銘柄
    draw_text(md, W * 0.5, H * 0.255, YEAR, font(CINZEL, H * 0.40, 700), spacing=H * 0.05)
    for u in (0.17, 0.83):
        draw_text(md, W * u, H * 0.42, "PEARCHAN", font(CINZEL, H * 0.13, 600), spacing=H * 0.03)
    for u in (0.31, 0.69):
        r = H * 0.05
        md.polygon([(W * u - r, H * 0.5), (W * u, H * 0.5 - r), (W * u + r, H * 0.5), (W * u, H * 0.5 + r)], fill=255)
    foil(canvas, m, emboss=3)
    atlas.paste(canvas.resize((w, h), Image.LANCZOS), (x0, y0))


# ---------------------------------------------------------------- キャップ
def draw_capsule_side(atlas):
    x0, y0, x1, y1 = uv_box(UV_CAPSULE)
    w, h = x1 - x0, y1 - y0
    W = 3000
    H = round(W * (CAPSULE_Z[1] - CAPSULE_Z[0]) / (2 * math.pi * CAPSULE_RADIUS))
    # サテンの縦方向のヘアライン
    noise = Image.effect_noise((W, 8), 40).resize((W, H), Image.BICUBIC)
    canvas = Image.blend(Image.new("RGB", (W, H), BLACK), Image.merge("RGB", (noise,) * 3), 0.025)

    def row(z):  # v は高さに比例して割り当て (make_wine_bottle.py と同じ)
        return H * (CAPSULE_Z[1] - z) / (CAPSULE_Z[1] - CAPSULE_Z[0])

    # 2 本の溝の間を金の帯に (帯だけで金のグラデーションをかける)
    band, bd = new_mask((W, H))
    bd.rectangle([0, row(0.2866) + 4, W, row(0.2814) - 4], fill=255)
    foil(canvas, band, emboss=2)
    m, md = new_mask((W, H))
    md.line([(0, row(0.2780)), (W, row(0.2780))], fill=255, width=3)
    md.line([(0, row(0.2440)), (W, row(0.2440))], fill=255, width=5)
    # 正面の紋章 (金の P とリング、月桂樹)
    cy = row(0.2600)
    r = H * 0.16
    md.ellipse([W * 0.5 - r, cy - r, W * 0.5 + r, cy + r], outline=255, width=5)
    draw_text(md, W * 0.5, cy - r * 0.78, "P", font(CINZEL, r * 1.25, 700))
    for side in (-1, 1):
        laurel(m, W * 0.5, cy, r * 1.35, side, leaves=5, leaf=(round(r * 0.17), round(r * 0.065)))
    foil(canvas, m, emboss=3)
    # 溝そのもの (暗い線 + 明るい線)
    d = ImageDraw.Draw(canvas)
    for z in (0.2866, 0.2814):
        rr = row(z)
        d.line([(0, rr - 2), (W, rr - 2)], fill=(6, 6, 6), width=4)
        d.line([(0, rr + 3), (W, rr + 3)], fill=BLACK_HI, width=2)
    atlas.paste(canvas.resize((w, h), Image.LANCZOS), (x0, y0))


def draw_capsule_top(atlas):
    x0, y0, x1, y1 = uv_box(UV_CAP_TOP)
    pad = 8
    W = 1200
    canvas = Image.new("RGB", (W, W), BLACK)
    m, md = new_mask((W, W))
    c = W / 2
    for rr, t in ((0.86, 14), (0.78, 4)):
        md.ellipse([c - c * rr, c - c * rr, c + c * rr, c + c * rr], outline=255, width=t)
    # 天面の P は正面 (-Y = 画像の下) から読める向き
    draw_text(md, c, c - W * 0.25, "P", font(CINZEL, W * 0.42, 700))
    for side in (-1, 1):
        laurel(m, c, c + W * 0.02, W * 0.30, side, leaves=6, leaf=(round(W * 0.036), round(W * 0.014)))
    foil(canvas, m, emboss=4)
    atlas.paste(Image.new("RGB", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), BLACK), (x0 - pad, y0 - pad))
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
    draw_neck(atlas)
    draw_capsule_side(atlas)
    draw_glass(atlas)
    draw_capsule_top(atlas)
    atlas.save(OUT, optimize=True)
    print("saved:", OUT)


if __name__ == "__main__":
    main()
