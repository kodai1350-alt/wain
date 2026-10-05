# ワインボトル (VRChat 用)

参考画像のシェリー型ボトル「PEARCHAN OLOROSO」をもとにした、アバターに持たせるワインボトルです。

![preview](../export/preview.png)

## 仕様

| 項目 | 内容 |
| --- | --- |
| 形 | シェリー型。細長い胴、丸く高い肩、長くゆるやかに細くなる首、上部を覆う黒いキャップシール (溝 2 本) |
| ラベル | 淡いピンク。PEARCHAN / OLOROSO / JEREZ – XÉRÈS – SHERRY、下辺中央の出っ張りに年号 **2007** |
| ガラス | オロロソの赤褐色 (底ほど暗い) |
| 向き | 立てた状態。Unity で Y が上、注ぎ口が真上 |
| 大きさ | 高さ 30cm / 太さ (直径) 7cm。原点は底面の中心 |
| 注ぎ口 | 口の真上の中心に空のオブジェクト `Spout` (WineBottle の子) |
| 中のワイン | なし (外側の瓶だけ) |
| ポリゴン | 2,080 三角形 |
| マテリアル | 1 個 (`WineBottle_Mat`、テクスチャ 1 枚 `WineBottle_Atlas.png` 1024×1024) |
| 構成 | 瓶・キャップシール・ラベルが 1 つのメッシュ `WineBottle` |
| ラベルの正面 | オブジェクトの前方 (Unity の +Z 方向) |
| 動作確認 | Blender 5.1.2 |

## ファイル

- `make_wine_bottle.py` … Blender でボトルを作って FBX に書き出すスクリプト
- `make_label_texture.py` … ラベルなどのテクスチャ `WineBottle_Atlas.png` を作るスクリプト (Pillow を使用)
- `WineBottle_Atlas.png` … 生成済みのテクスチャ
- `../export/WineBottle.fbx` … このスクリプトで書き出し済みの FBX (Blender 5.1.2 で作成)

## Blender での使い方

1. `make_wine_bottle.py` と `WineBottle_Atlas.png` を同じフォルダに置く
2. Blender の **Scripting** タブ → テキストエディタの「開く」で `make_wine_bottle.py` を開く
3. 「スクリプト実行」(▶ または Alt+P)
4. シーンに `WineBottle` と `Spout` ができ、FBX が書き出されます
   - 書き出し先: .blend を保存していればそのフォルダ、未保存ならスクリプトのフォルダ
   - 書き出し先を決めたいときはスクリプト上部の `OUTPUT_DIR` にフォルダを書く
   - 出力: `WineBottle.fbx` と `WineBottle_Atlas.png`

もう一度実行すると、前の `WineBottle` / `Spout` を消してから作り直します。それ以外のオブジェクトは消しません。書き出すのは `WineBottle` と `Spout` だけです。

コマンドラインでも実行できます:

```
blender -b -P make_wine_bottle.py -- --out <出力フォルダ>
```

大きさや丸さを変えたいときは、スクリプト上部の `HEIGHT` / `DIAMETER` / `SEGMENTS` を変更してください。
ラベルの文字や年号を変えたいときは `make_label_texture.py` を編集して実行し直してください。

## Unity に入れるとき

- FBX は「回転 0・スケール 1・1unit = 1m」で読み込まれる設定で書き出しています。
- テクスチャは FBX に埋め込み済みです。マテリアルを自分で作る場合は `WineBottle_Atlas.png` を使ってください。
- lilToon で使う場合: ガラス部分の光沢は、Smoothness などをお好みで調整してください。
