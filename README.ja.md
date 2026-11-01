# Markdown → Excel

[English](README.md) | **日本語**

Markdown文書を、読むためのシンプルなExcelブック（`.xlsx`）に変換するローカルCLIです。見出しはA列、本文・コード・画像はB列から始めます。画像はブック内に埋め込み、通常のリンクとURLはクリックできる状態で残します。

## 必要な環境

- Python 3.10以降
- 依存ライブラリは [requirements.txt](requirements.txt) に記載
- 外部URLの画像を含むMarkdownを変換する場合はネットワーク接続

## セットアップ

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## 変換する

```sh
.venv/bin/python md_to_excel.py 入力.md 出力.xlsx
```

入力はUTF-8のMarkdownファイル1件です。出力先のフォルダは自動で作成します。**既存の出力ファイルは上書きしません。** CLIのメッセージは現状日本語です。Excelの本文は日英どちらも扱えます。

英語Exampleを手元で再生成する場合：

```sh
.venv/bin/python md_to_excel.py examples/cohere-article.en.md cohere-example-local.xlsx
```

| Example | 入力Markdown | 生成済みExcel |
|---|---|---|
| 日本語原文 | [記事](examples/CohereとLangchainを使って、簡易AIデータアナリストエージェントを作ってみた.md) | [ブック](examples/cohere-converted.xlsx) |
| 英語翻訳 | [記事](examples/cohere-article.en.md) | [ブック](examples/cohere-article.en.xlsx) |

英語版は本人のQiita記事の翻訳で、記述と結果は2024年8月当時の内容です。各ExampleのExcelには画像3点を埋め込んでいます。英語版は元の構成図とグラフに加え、日本語の株価ランキング画像の内容を英語で再構成した表を使い、原画像へのリンクも記事に残しています。

## 配置ルール

- H1～H6はすべてA列の独立行。深い見出しほどセル内を字下げします。
- 本文、目次、リスト、コード、画像は文書を通じてB列から開始します。
- 長文は句読点や空白の近くで行に分け、段落間には空行を入れます。コードの改行と行頭の空白は保持します。
- 表はB列から右へ展開します。リンクが段落に複数ある場合は、本文の後にクリック可能なリンク行を追加します。
- 画像は縦横比を維持し、画像の前後に空行を確保します。文字は標準サイズの黒で、色・塗り・飾り罫線・ウィンドウ枠の固定は使いません。

## 画像と終了コード

HTTP(S)画像と、Markdownのあるフォルダ以下を指す相対パス画像に対応します。対応形式はPNG、JPEG、GIF、BMPで、1画像の上限は15MBです。取得できない画像は代替文として位置を残し、標準エラーに原因を表示します。

| 終了コード | 意味 |
|---:|---|
| 0 | 変換成功 |
| 1 | 入出力などで変換失敗 |
| 2 | Excelを作成したが画像の一部を埋め込めなかった |

## 現在の範囲

1回の実行でMarkdown1件から単一シートを作ります。既存Excelテンプレートへの流し込み、一括変換、Web画面には対応していません。Excelの表示はアプリとフォント環境に依存するため、共有前に開いて確認してください。実装の詳細は [仕様書](docs/service-design.md) に記載しています。
