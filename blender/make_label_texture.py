"""
ワインボトル (シェリー型 / PEARCHAN OLOROSO) 用テクスチャアトラス
WineBottle_Atlas.png を生成するスクリプト。

Blender ではなく通常の Python + Pillow で実行します:
    pip install pillow
    python make_label_texture.py

アトラスのレイアウト (UV は左下原点, 1024x1024):
    v 0.00-0.62 / u 0.00-1.00 : 正面ラベル (ボトル正面の円周 35% ぶん)
    v 0.64-0.84 / u 0.00-1.00 : キャップシール側面 (一周)
    v 0.86-1.00 / u 0.00-0.70 : ガラス (縦方向 = 高さのグラデーション)
    v 0.86-1.00 / u 0.74-0.88 : キャップシール天面
make_wine_bottle.py の UV 割り当てはこのレイアウトと下の寸法に合わせてあります。
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont

SIZE = 1024
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "WineBottle_Atlas.png")

# make_wine_bottle.py と同じ寸法 (高さ 0.30m / 直径 0.07m 基準)
LABEL_Z = (0.0750, 0.1430)      # ラベル帯の下端 (出っ張りの下) / 上端
LABEL_MAIN_BOTTOM = 0.0815      # 出っ張り以外のラベル下辺
LABEL_FRACTION = 0.35           # ラベルが覆う円周の割合
CAPSULE_Z = (0.2410, 0.3000)
RADIUS = 0.035

UV_LABEL = (0.0, 0.0, 1.0, 0.62)
UV_CAPSULE = (0.0, 0.64, 1.0, 0.84)
UV_GLASS = (0.0, 0.86, 0.70, 1.0)
UV_CAP_TOP = (0.74, 0.86, 0.88, 1.0)

# 色 (参考画像から)
PAPER = (240, 222, 216)
INK = (74, 64, 64)
INK_LIGHT = (120, 108, 106)
RED_INK = (184, 62, 52)
CAPSULE = (30, 28, 26)
CAPSULE_LINE = (64, 61, 58)
CAPSULE_DARK = (14, 13, 12)
# ガラスの色: 高さ (m) ごとの色。オロロソの赤褐色、底は厚みで暗く。
GLASS_STOPS = [
    (0.000, (44, 7, 4)),
    (0.030, (54, 10, 6)),
    (0.070, (68, 17, 11)),
    (0.145, (72, 20, 15)),
    (0.165, (90, 30, 26)),
    (0.185, (58, 15, 15)),
    (0.215, (76, 25, 26)),
    (0.241, (88, 31, 30)),
]

FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/liberation",
    "C:/Windows/Fonts",
    "/System/Library/Fonts/Supplemental",
    "/Library/Fonts",
]
SERIF = ["LiberationSerif-Regular.ttf", "DejaVuSerif.ttf", "times.ttf", "Times New Roman.ttf"]
SERIF_BOLD = ["LiberationSerif-Bold.ttf", "DejaVuSerif-Bold.ttf", "timesbd.ttf", "Times New Roman Bold.ttf"]
SANS = ["LiberationSans-Regular.ttf", "DejaVuSans.ttf", "arial.ttf", "Arial.ttf"]
SANS_BOLD = ["LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"]


def font(names, size):
    for d in FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def uv_box(rect):
    """UV 矩形 (左下原点) を PIL のピクセル矩形 (左上原点) に変換。"""
    u0, v0, u1, v1 = rect
    return (round(u0 * SIZE), round((1 - v1) * SIZE), round(u1 * SIZE), round((1 - v0) * SIZE))


def glass_color(z):
    for (z0, c0), (z1, c1) in zip(GLASS_STOPS, GLASS_STOPS[1:]):
        if z <= z1:
            t = max(0.0, (z - z0) / (z1 - z0))
            return tuple(round(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))
    return GLASS_STOPS[-1][1]


def spaced(d, xy, s, f, fill, spacing=0, anchor_center=False):
    widths = [d.textlength(c, font=f) for c in s]
    total = sum(widths) + spacing * (len(s) - 1)
    x, y = xy
    if anchor_center:
        x -= total / 2
    for c, w in zip(s, widths):
        d.text((x, y), c, font=f, fill=fill)
        x += w + spacing


# ---------------------------------------------------------------- ラベル
def label_canvas():
    """正方ピクセルでラベルを描いた画像 (透明 = ラベルの外) を返す。"""
    label_w = 2 * 3.14159265 * RADIUS * LABEL_FRACTION   # 約 0.077m
    label_h = LABEL_Z[1] - LABEL_Z[0]                     # 約 0.068m
    W = 1600
    H = round(W * label_h / label_w)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 外形: 長方形 + 下辺中央の出っ張り (丸い肩でつながる)
    main_bottom = round(H * (LABEL_Z[1] - LABEL_MAIN_BOTTOM) / label_h)
    tab_l, tab_r = W * 0.30, W * 0.70
    curve = W * 0.06
    pts = [(0, 0), (W, 0), (W, main_bottom)]
    steps = 16
    # 右の肩 (main_bottom → H-1 へ S 字)
    for i in range(steps + 1):
        t = i / steps
        x = tab_r + curve * (1 - t)
        y = main_bottom + (H - 1 - main_bottom) * (0.5 - 0.5 * math.cos(math.pi * t))
        pts.append((x, y))
    for i in range(steps + 1):
        t = i / steps
        x = tab_l - curve * t
        y = H - 1 - (H - 1 - main_bottom) * (0.5 - 0.5 * math.cos(math.pi * t))
        pts.append((x, y))
    pts.append((0, main_bottom))
    d.polygon(pts, fill=PAPER + (255,))

    # 文字 (参考画像どおり左寄せ)
    x0 = W * 0.075
    size = 260
    while size > 40 and d.textlength("PEARCHAN", font=font(SERIF_BOLD, size)) + 4 * 7 > W * 0.85:
        size -= 4
    spaced(d, (x0, H * 0.20 - size * 0.25), "PEARCHAN", font(SERIF_BOLD, size), INK, spacing=4)
    spaced(d, (x0 + 6, H * 0.43), "OLOROSO", font(SERIF, 104), INK_LIGHT, spacing=16)
    spaced(d, (x0 + 8, H * 0.60), "JEREZ \u2013 XÉRÈS \u2013 SHERRY", font(SANS, 62), RED_INK, spacing=6)
    d.line([(x0 + 8, H * 0.71), (W * 0.93, H * 0.71)], fill=INK_LIGHT, width=3)

    # 下の出っ張り部分: 年と蔵元名
    cx = W / 2
    spaced(d, (cx, H * 0.735), "VINO DE JEREZ", font(SANS, 40), INK_LIGHT, spacing=6, anchor_center=True)
    spaced(d, (cx, H * 0.79), "2007", font(SERIF_BOLD, 96), RED_INK, spacing=10, anchor_center=True)
    spaced(d, (cx, H * 0.915), "BODEGAS PEARCHAN", font(SANS_BOLD, 40), INK, spacing=5, anchor_center=True)
    return img, main_bottom


def draw_label(atlas):
    x0, y0, x1, y1 = uv_box(UV_LABEL)
    w, h = x1 - x0, y1 - y0
    # ラベルの外 (出っ張りの左右) はその高さのガラス色
    bg = Image.new("RGB", (w, h))
    bd = ImageDraw.Draw(bg)
    for y in range(h):
        z = LABEL_Z[1] - (LABEL_Z[1] - LABEL_Z[0]) * (y + 0.5) / h
        bd.line([(0, y), (w, y)], fill=glass_color(z))
    lab, _ = label_canvas()
    lab = lab.resize((w, h), Image.LANCZOS)
    bg.paste(lab, (0, 0), lab)
    atlas.paste(bg, (x0, y0))


# ---------------------------------------------------------------- キャップ
def draw_capsule_side(atlas):
    d = ImageDraw.Draw(atlas)
    x0, y0, x1, y1 = uv_box(UV_CAPSULE)
    d.rectangle([x0, y0, x1, y1], fill=CAPSULE)
    h = y1 - y0

    def row(z):  # 高さ z (m) → 行。v は断面の長さで割り当てるが、ほぼ高さに比例
        return y0 + round(h * (CAPSULE_Z[1] - z) / (CAPSULE_Z[1] - CAPSULE_Z[0]))

    # 上部の 2 本の溝 (参考画像の細いリング)
    for z in (0.2866, 0.2814):
        r = row(z)
        d.line([x0, r - 1, x1, r - 1], fill=CAPSULE_DARK, width=2)
        d.line([x0, r + 1, x1, r + 1], fill=CAPSULE_LINE, width=2)
    # 下端のふち
    d.line([x0, y1 - 3, x1, y1 - 3], fill=CAPSULE_LINE, width=2)


def draw_capsule_top(atlas):
    d = ImageDraw.Draw(atlas)
    x0, y0, x1, y1 = uv_box(UV_CAP_TOP)
    d.rectangle([x0 - 4, y0 - 4, x1 + 4, y1 + 4], fill=CAPSULE)
    cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2
    d.ellipse([cx - r * 0.72, cy - r * 0.72, cx + r * 0.72, cy + r * 0.72], outline=CAPSULE_LINE, width=2)


def draw_glass(atlas):
    d = ImageDraw.Draw(atlas)
    x0, y0, x1, y1 = uv_box(UV_GLASS)
    h = y1 - y0
    for y in range(y0 - 6, y1):
        t = min(1.0, max(0.0, (y1 - 1 - y) / (h - 1)))  # 下 = 底 (z=0), 上 = キャップ下端
        d.line([x0, y, x1, y], fill=glass_color(t * CAPSULE_Z[0]))


def main():
    atlas = Image.new("RGB", (SIZE, SIZE), glass_color(0.1))
    draw_label(atlas)
    draw_capsule_side(atlas)
    draw_glass(atlas)
    draw_capsule_top(atlas)
    atlas.save(OUT)
    print("saved:", OUT)


if __name__ == "__main__":
    main()
