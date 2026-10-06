# 刀 (VRChat 用 / 夢想の一太刀 風・ファンメイド)

原神の雷電将軍が元素爆発で使う刀をもとにした、アバターに持たせる刀のモデルです。
参考画像を見ながら独自に作ったファンメイドのモデルです。個人で楽しむ範囲で使ってください (販売・配布はしないでください)。

![preview](export/preview.png)

## 仕様

| 項目 | 内容 |
| --- | --- |
| 大きさ | 全長 約 1.07m (刃 80cm・柄 20cm・柄頭の飾り 約 7cm)。刃が柄の約 4 倍の細長いバランス |
| 刃 | 反りのある刀身。薄紫に白く光る地、中央に炎のような紫の模様、切っ先近くで炎のすじにほどける |
| 刃の付け根 | 白く光る三つ巴の紋、峰側に紫の炎のヒレ、金の鎺 |
| 鍔 | 細長い棒状 (両端は斜めにとがる)、白く光る |
| 柄 | 紫のマーブルに銀の柄巻き (斜めに交差)、峰側に金の爪飾り 5 本、白く光る玉 2 つ、金の縁と柄頭、先に黄色く光る炎 |
| 向き | Unity で刃が上 (Y)、刃先が前 (+Z)。原点は鍔の中心 |
| 目印 | `Grip` (握る位置、柄の中央) / `Tip` (切っ先)。どちらも Katana の子の空オブジェクト |
| ポリゴン | 2,340 三角形 |
| マテリアル | 2 個: `Katana_Blade` (光る部分: 刃・紋・ヒレ・鍔・玉・炎) / `Katana_Hilt` (柄巻き・金具) |
| テクスチャ | 1 枚 `Katana_Atlas.png` (2048×2048) を 2 つのマテリアルで共有 |
| 動作確認 | Blender 5.1.2 |

## ファイル

- `make_katana.py` … Blender で刀を作って FBX に書き出すスクリプト
- `make_katana_texture.py` … テクスチャ `Katana_Atlas.png` を作るスクリプト (Pillow を使用)
- `Katana_Atlas.png` … 生成済みのテクスチャ
- `export/Katana.fbx` … 書き出し済みの FBX (Blender 5.1.2 で作成)

## Blender での使い方

1. `make_katana.py` と `Katana_Atlas.png` を同じフォルダに置く
2. Blender の **Scripting** タブ → **テキスト → 開く** で `make_katana.py` を開く
3. **▶ (スクリプト実行)** (Alt+P)
4. シーンに `Katana` / `Grip` / `Tip` ができ、`Katana.fbx` と `Katana_Atlas.png` が書き出されます
   (.blend を保存していればそのフォルダ、未保存ならスクリプトのフォルダ)

大きさはスクリプト上部の `SCALE` (全体)、`BLADE_LEN` (刃の長さ)、`HANDLE_LEN` (柄の長さ)、
`SORI` (反り)、`BLADE_W` (刃の幅) で変えられます。

## Unity に入れるとき

- FBX は「回転 0・スケール 1・1unit = 1m」で読み込まれる設定で書き出しています。
- 2 つのマテリアルとも `Katana_Atlas.png` を使ってください。
- lilToon で光らせるとき: `Katana_Blade` の **Emission** をオンにして、Emission のテクスチャにも `Katana_Atlas.png` を設定します (柄の `Katana_Hilt` は光らせません)。
