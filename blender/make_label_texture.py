"""
ワインボトル用テクスチャアトラス (WineBottle_Atlas.png) を生成するスクリプト。

Blender ではなく通常の Python + Pillow で実行します:
    pip install pillow
    python make_label_texture.py

アトラスのレイアウト (UV は左下原点, 1024x1024):
    v 0.00-0.50 / u 0.00-1.00 : 胴のラベル帯 (u=0.5 が正面, 継ぎ目は背面)
    v 0.52-0.72 / u 0.00-1.00 : キャップシール側面
    v 0.76-1.00 / u 0.00-0.70 : ガラス
    v 0.76-1.00 / u 0.74-0.98 : キャップシール天面
make_wine_bottle.py の UV 割り当てはこのレイアウトに合わせてあります。
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont

SIZE = 1024
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "WineBottle_Atlas.png")

GLASS = (40, 12, 18)
CAPSULE = (148, 20, 32)
CAPSULE_DARK = (110, 12, 22)
GOLD = (201, 162, 82)
GOLD_DARK = (150, 112, 48)
PAPER = (240, 233, 216)
INK = (52, 40, 34)
RED_INK = (150, 28, 36)

FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/liberation",
    "C:/Windows/Fonts",
    "/System/Library/Fonts/Supplemental",
    "/Library/Fonts",
]
SERIF = ["DejaVuSerif.ttf", "LiberationSerif-Regular.ttf", "times.ttf", "Times New Roman.ttf"]
SERIF_BOLD = ["DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf", "timesbd.ttf", "Times New Roman Bold.ttf"]
SERIF_ITALIC = ["LiberationSerif-Italic.ttf", "DejaVuSerif-Italic.ttf", "timesi.ttf", "Times New Roman Italic.ttf"]


def font(names, size):
    for d in FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def uv_box(u0, v0, u1, v1):
    """UV 矩形 (左下原点) を PIL のピクセル矩形 (左上原点) に変換。"""
    return (round(u0 * SIZE), round((1 - v1) * SIZE), round(u1 * SIZE), round((1 - v0) * SIZE))


def text_center(d, cx, y, s, f, fill, spacing=0):
    if spacing:
        widths = [d.textlength(c, font=f) for c in s]
        total = sum(widths) + spacing * (len(s) - 1)
        x = cx - total / 2
        for c, w in zip(s, widths):
            d.text((x, y), c, font=f, fill=fill)
            x += w + spacing
    else:
        w = d.textlength(s, font=f)
        d.text((cx - w / 2, y), s, font=f, fill=fill)


def draw_chateau(d, cx, base_y, w):
    """ラベル中央の城館 + ブドウ畑のスケッチ。"""
    s = w / 300.0

    def P(x, y):
        return (cx + x * s, base_y + y * s)

    line = max(1, round(1.6 * s))
    # ブドウ畑の畝 (手前に向かって広がる線)
    for i in range(-7, 8):
        d.line([P(i * 6, 0), P(i * 26, 62)], fill=INK, width=line)
    d.line([P(-150, 0), P(150, 0)], fill=INK, width=line)
    # 本館
    d.rectangle([P(-62, -46), P(62, 0)], outline=INK, width=line)
    d.polygon([P(-70, -46), P(-50, -70), P(50, -70), P(70, -46)], outline=INK, width=line)
    # 中央の破風
    d.polygon([P(-18, -46), P(0, -84), P(18, -46)], outline=INK, width=line)
    # 両脇の塔
    for sx in (-1, 1):
        x0, x1 = sx * 62, sx * 92
        d.rectangle([P(min(x0, x1), -56), P(max(x0, x1), 0)], outline=INK, width=line)
        d.polygon([P(min(x0, x1) - 3, -56), P((x0 + x1) / 2, -98), P(max(x0, x1) + 3, -56)], outline=INK, width=line)
        d.rectangle([P((x0 + x1) / 2 - 5, -40), P((x0 + x1) / 2 + 5, -24)], outline=INK, width=line)
    # 窓
    for row_y in (-38, -18):
        for i in range(-4, 5):
            if i == 0 and row_y == -18:
                d.rectangle([P(-6, -22), P(6, 0)], outline=INK, width=line)  # 扉
                continue
            d.rectangle([P(i * 13 - 4, row_y), P(i * 13 + 4, row_y + 12)], outline=INK, width=line)
    # 木
    for tx, th in ((-128, 50), (-110, 38), (118, 46), (136, 34)):
        d.ellipse([P(tx - 12, -th - 20), P(tx + 12, -th + 14)], outline=INK, width=line)
        d.line([P(tx, -th + 14), P(tx, 0)], fill=INK, width=line)


def draw_label(img):
    d = ImageDraw.Draw(img)
    # ラベル帯全体はガラス色で塗る (ラベル外の胴部分)
    d.rectangle(uv_box(0, 0, 1, 0.50), fill=GLASS)

    # 正面ラベル: 円周の約 45% (u 0.275-0.725)
    lx0, ly0, lx1, ly1 = uv_box(0.275, 0.0, 0.725, 0.50)
    ly0 += 4
    ly1 -= 4
    d.rectangle([lx0, ly0, lx1, ly1], fill=PAPER)
    w = lx1 - lx0
    cx = (lx0 + lx1) / 2
    # 枠
    d.rectangle([lx0 + 10, ly0 + 10, lx1 - 10, ly1 - 10], outline=GOLD_DARK, width=3)
    d.rectangle([lx0 + 16, ly0 + 16, lx1 - 16, ly1 - 16], outline=GOLD, width=1)

    y = ly0 + 34
    text_center(d, cx, y, "GRAND VIN DE BORDEAUX", font(SERIF, 15), INK, spacing=2)
    y += 34
    text_center(d, cx, y, "CHÂTEAU", font(SERIF, 28), INK, spacing=6)
    y += 38
    text_center(d, cx, y, "WAIN", font(SERIF_BOLD, 70), INK, spacing=8)
    y += 92
    draw_chateau(d, cx, y + 92, w * 0.62)
    y += 162
    text_center(d, cx, y, "BORDEAUX", font(SERIF_BOLD, 34), RED_INK, spacing=5)
    y += 42
    text_center(d, cx, y, "APPELLATION BORDEAUX CONTRÔLÉE", font(SERIF, 13), INK, spacing=1)

    # 下部の濃色帯 (写真のボトル 4・6 風)
    by0 = ly1 - 74
    d.rectangle([lx0 + 10, by0, lx1 - 10, ly1 - 10], fill=(28, 22, 22))
    text_center(d, cx, by0 + 8, "2024", font(SERIF_BOLD, 26), GOLD, spacing=4)
    text_center(d, cx, by0 + 40, "MIS EN BOUTEILLE AU CHÂTEAU", font(SERIF_ITALIC, 14), GOLD, spacing=1)

    # 右端のメダルシール
    mx, my, mr = lx1 - 6, ly0 + 170, 30
    d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=GOLD, outline=GOLD_DARK, width=3)
    d.ellipse([mx - mr + 7, my - mr + 7, mx + mr - 7, my + mr - 7], outline=GOLD_DARK, width=1)
    text_center(d, mx, my - 9, "OR", font(SERIF_BOLD, 15), GOLD_DARK)

    # 背面の小さな裏ラベル (u 0.88-1.0 と 0.0-0.12 にまたがる継ぎ目側)
    for u0, u1 in ((0.0, 0.10), (0.90, 1.0)):
        bx0, by0b, bx1, by1b = uv_box(u0, 0.10, u1, 0.36)
        d.rectangle([bx0, by0b, bx1, by1b], fill=PAPER)
        for k in range(8):
            yy = by0b + 22 + k * 14
            d.line([bx0 + (10 if u0 > 0 else 0), yy, bx1 - (0 if u0 > 0 else 10), yy], fill=(150, 140, 125), width=2)


def draw_capsule_side(img):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = uv_box(0, 0.52, 1, 0.72)
    # 上ほど暗くなる縦グラデーション
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0)
        c = tuple(round(CAPSULE_DARK[i] * (1 - t) + CAPSULE[i] * t) for i in range(3))
        d.line([x0, y, x1, y], fill=c)
    # 上端の金の帯 (口の膨らみ部分)
    d.rectangle([x0, y0, x1, y0 + 26], fill=GOLD)
    d.line([x0, y0 + 26, x1, y0 + 26], fill=GOLD_DARK, width=2)
    # 下端の金ライン
    d.rectangle([x0, y1 - 10, x1, y1], fill=GOLD)
    d.line([x0, y1 - 10, x1, y1 - 10], fill=GOLD_DARK, width=2)
    # 正面の紋章 (u=0.5 付近)
    cx = SIZE * 0.5
    cy = (y0 + y1) / 2 + 12
    pts = [(cx - 28, cy - 34), (cx + 28, cy - 34), (cx + 28, cy + 6), (cx, cy + 36), (cx - 28, cy + 6)]
    d.polygon(pts, fill=GOLD, outline=GOLD_DARK)
    text_center(d, cx, cy - 26, "W", font(SERIF_BOLD, 34), CAPSULE_DARK)
    # 紋章の左右の飾り線
    for sx in (-1, 1):
        d.line([cx + sx * 40, cy, cx + sx * 120, cy], fill=GOLD, width=3)


def draw_glass(img):
    d = ImageDraw.Draw(img)
    d.rectangle(uv_box(0, 0.76, 0.70, 1.0), fill=GLASS)


def draw_capsule_top(img):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = uv_box(0.74, 0.76, 0.98, 1.0)
    d.rectangle([x0 - 6, y0 - 6, x1 + 6, y1 + 6], fill=GOLD)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r = (x1 - x0) / 2
    d.ellipse([cx - r * 0.86, cy - r * 0.86, cx + r * 0.86, cy + r * 0.86], fill=CAPSULE)
    d.ellipse([cx - r * 0.80, cy - r * 0.80, cx + r * 0.80, cy + r * 0.80], outline=GOLD, width=3)
    # 天面の "W" は側面から見て正しい向き (正面 -Y 側が画像の下)
    text_center(d, cx, cy - 34, "W", font(SERIF_BOLD, 56), GOLD)


def main():
    img = Image.new("RGB", (SIZE, SIZE), GLASS)
    draw_label(img)
    draw_capsule_side(img)
    draw_glass(img)
    draw_capsule_top(img)
    img.save(OUT)
    print("saved:", OUT)


if __name__ == "__main__":
    main()
