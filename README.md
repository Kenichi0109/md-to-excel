# Markdown → Excel

**English** | [日本語](README.ja.md)

A local command-line tool that converts one Markdown document into a simple, readable Excel workbook (`.xlsx`). Headings start in column A; body text, code, and images start in column B. Images are embedded in the workbook, and ordinary links and URLs remain clickable.

## Requirements

- Python 3.10 or newer
- The packages in [requirements.txt](requirements.txt)
- Network access when the Markdown references remote images

## Install

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Convert a document

```sh
.venv/bin/python md_to_excel.py input.md output.xlsx
```

The input is one UTF-8 Markdown file. The output directory is created when needed. **An existing output file is never overwritten.** The CLI's messages are currently in Japanese; the workbook accepts either language.

To regenerate the English example:

```sh
.venv/bin/python md_to_excel.py examples/cohere-article.en.md cohere-example-local.xlsx
```

| Example | Markdown input | Generated Excel output |
|---|---|---|
| Japanese original | [Article](examples/CohereとLangchainを使って、簡易AIデータアナリストエージェントを作ってみた.md) | [Workbook](examples/cohere-converted.xlsx) |
| English translation | [Article](examples/cohere-article.en.md) | [Workbook](examples/cohere-article.en.xlsx) |

The English article translates the author's Japanese Qiita article; statements and results retain their August 2024 context. Each workbook embeds three images. The English example uses the original diagram and chart plus a locally recreated English table for the Japanese market-ranking screenshot; the article links to the original screenshot.

## Workbook layout

- H1–H6 each occupy their own row in column A. Deeper headings use more indentation within the cell.
- Body text, tables of contents, lists, code, and images start in column B throughout the document.
- Long prose is split near punctuation or whitespace, with blank rows between paragraphs. Code keeps its original line breaks and leading spaces.
- Tables extend to the right from column B. When a paragraph contains multiple links, separate clickable link rows follow the text.
- Images keep their aspect ratio and have empty rows around them. Cells use standard-size black text without fills, decorative borders, or frozen panes.

## Images and exit codes

HTTP(S) images and relative image paths within the Markdown file's directory are supported. Accepted formats are PNG, JPEG, GIF, and BMP, up to 15 MB per image. If an image cannot be retrieved, the workbook contains replacement text at that position and the cause is written to standard error.

| Code | Meaning |
|---:|---|
| 0 | Conversion succeeded |
| 1 | Conversion failed, for example because of an input or output error |
| 2 | Workbook created, but one or more images could not be embedded |

## Current scope

Each run creates one worksheet from one Markdown file. Existing Excel templates, batch conversion, and a web interface are not supported. Display can vary by spreadsheet app and fonts, so open the workbook before sharing it. See the [technical specification](docs/service-design.md) for implementation details.
