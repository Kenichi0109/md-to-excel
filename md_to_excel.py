#!/usr/bin/env python3
"""Convert a Markdown document into a readable, single-sheet Excel workbook."""
import argparse
import io
import math
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse, unquote
from urllib.request import Request, urlopen

from markdown_it import MarkdownIt
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from PIL import Image as PILImage

MAX_IMAGE_BYTES = 15 * 1024 * 1024
URL_RE = re.compile(r'https?://[^\s<>]+')


def inline_parts(token):
    parts = []
    children = token.children or []
    link = None
    for child in children:
        if child.type == 'link_open':
            link = child.attrGet('href')
        elif child.type == 'link_close':
            link = None
        elif child.type == 'image':
            parts.append(('image', child.attrGet('src'), child.content))
        elif child.type in ('text', 'code_inline', 'html_inline'):
            parts.append(('text', child.content, link))
        elif child.type in ('softbreak', 'hardbreak'):
            parts.append(('text', '\n', link))
    return parts


def read_image(src, base):
    parsed = urlparse(src)
    if parsed.scheme in ('http', 'https'):
        req = Request(src, headers={'User-Agent': 'markdown-to-excel/0.1'})
        with urlopen(req, timeout=15) as response:
            if response.status != 200:
                raise ValueError(f'HTTP {response.status}')
            data = response.read(MAX_IMAGE_BYTES + 1)
    elif parsed.scheme:
        raise ValueError('非対応の画像URL形式')
    else:
        path = (base / unquote(src.split('#', 1)[0])).resolve()
        if not path.is_relative_to(base.resolve()):
            raise ValueError('入力フォルダ外の画像参照')
        if path.stat().st_size > MAX_IMAGE_BYTES:
            raise ValueError('画像サイズ上限超過')
        data = path.read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError('画像サイズ上限超過')
    image = PILImage.open(io.BytesIO(data))
    image.verify()
    image = PILImage.open(io.BytesIO(data))
    if image.format not in ('PNG', 'JPEG', 'GIF', 'BMP'):
        raise ValueError('非対応の画像形式')
    if image.format not in ('PNG', 'JPEG'):
        out = io.BytesIO()
        image.convert('RGB').save(out, format='PNG')
        data = out.getvalue()
    return data


class Builder:
    """Place short lines in ordinary Excel cells, leaving nearby cells empty."""
    def __init__(self, source):
        self.source = source
        self.book = Workbook()
        self.sheet = self.book.active
        self.sheet.title = 'Document'
        self.sheet.sheet_format.defaultRowHeight = 15.75
        self.row = 1
        self.warnings = []
        self.images = 0
        self.body_col = 2

    def configure(self, tokens):
        # Every document uses the same left edge for headings and body.
        self.body_col = 2

    def line(self, value, col=None, link=None, indent=0):
        col = col or self.body_col
        cell = self.sheet.cell(self.row, col, value)
        cell.data_type = 's'  # Markdown text is never an Excel formula.
        cell.alignment = Alignment(vertical='center', wrap_text=False, indent=indent)
        cell.font = Font(name='Aptos', size=11, color='000000')
        if link:
            cell.hyperlink = link
            cell.font = Font(name='Aptos', size=11, color='000000')
        self.row += 1

    def blank(self):
        self.row += 1

    @staticmethod
    def units(text):
        return sum(2 if unicodedata.east_asian_width(c) in ('F', 'W') else 1 for c in text)

    def split_prose(self, text, limit=140):
        # Break at punctuation or whitespace when possible; preserve every character.
        for paragraph_line in text.split('\n'):
            rest = paragraph_line
            if not rest:
                yield ''
                continue
            while self.units(rest) > limit + 15:
                count = 0
                cut = 0
                for i, char in enumerate(rest):
                    count += self.units(char)
                    if count > limit:
                        break
                    cut = i + 1
                candidates = [m.end() for m in re.finditer(r'[。！？、，．,.!?;；:：]|\s+', rest[:cut]) if m.end() >= cut // 2]
                if candidates:
                    cut = candidates[-1]
                yield rest[:cut]
                rest = rest[cut:]
            if rest:
                yield rest

    def prose(self, text, col=None, links=()):
        standalone_urls = set()
        for segment in self.split_prose(text):
            url = segment.strip() if re.fullmatch(r'https?://[^\s<>]+', segment.strip()) else None
            if url:
                standalone_urls.add(url)
            self.line(segment, col, url)
        for label, url in links:
            if label.strip() and url not in standalone_urls:
                self.line('↗ ' + label, col, url)
        self.blank()

    def inline(self, token, col=None, prefix=''):
        col = col or self.body_col
        buf = prefix
        links = []
        for typ, value, extra in inline_parts(token):
            if typ == 'image':
                if buf.strip():
                    self.prose(buf, col, links)
                    buf, links = '', []
                self.image(value, extra)
            else:
                buf += value
                if extra and value.strip():
                    links.append((value, extra))
        if buf.strip():
            bare = [(m.group(), m.group().rstrip('.,;')) for m in URL_RE.finditer(buf)]
            links += [x for x in bare if x[1] not in [url for _, url in links]]
            if len(links) == 1 and buf.strip() == links[0][0].strip():
                self.line(buf, col, links[0][1])
                self.blank()
            else:
                self.prose(buf, col, links)

    def image(self, src, alt):
        try:
            data = read_image(src, self.source.parent)
            img = ExcelImage(io.BytesIO(data))
            scale = min(1, 940 / img.width)
            img.width = round(img.width * scale)
            img.height = round(img.height * scale)
            # Leave one empty row above the image and at least two below it.
            self.row += 1
            img.anchor = f'{get_column_letter(self.body_col)}{self.row}'
            self.sheet.add_image(img)
            self.images += 1
            row_px = self.sheet.sheet_format.defaultRowHeight * 96 / 72
            safe_row_px = row_px - 1  # allow for Excel display rounding
            image_rows = max(1, math.ceil(img.height / safe_row_px))
            self.row += image_rows + 2
        except Exception as exc:
            self.warnings.append(f'行 {self.row}: 画像「{alt or src}」を取得できません: {exc}')
            self.prose(f'[画像を埋め込めませんでした: {alt or src}] {src}')

    def build(self, markdown):
        tokens = MarkdownIt('commonmark').enable('table').parse(markdown)
        self.configure(tokens)
        i = 0
        lists = []
        while i < len(tokens):
            t = tokens[i]
            if t.type in ('bullet_list_open', 'ordered_list_open'):
                lists.append([t.type == 'ordered_list_open', int(t.attrGet('start') or 1)])
            elif t.type in ('bullet_list_close', 'ordered_list_close'):
                lists.pop()
            elif t.type == 'heading_open':
                level = int(t.tag[1:])
                self.line(tokens[i+1].content, 1, indent=min(level - 1, 5))
                self.blank()
                i += 2
            elif t.type == 'paragraph_open' and i+1 < len(tokens) and tokens[i+1].type == 'inline':
                prefix = ''
                if lists:
                    ordered, number = lists[-1]
                    prefix = ('  ' * (len(lists) - 1)) + (f'{number}. ' if ordered else '• ')
                    if ordered:
                        lists[-1][1] += 1
                self.inline(tokens[i+1], prefix=prefix)
                i += 2
            elif t.type in ('fence', 'code_block'):
                # Keep the original line breaks and leading spaces of the code.
                for code_line in t.content.rstrip('\n').split('\n'):
                    self.line(code_line)
                self.blank()
            elif t.type == 'hr':
                self.blank()
            elif t.type == 'table_open':
                j = i + 1
                current = []
                while j < len(tokens) and tokens[j].type != 'table_close':
                    x = tokens[j]
                    if x.type == 'tr_open':
                        current = []
                    if x.type == 'inline':
                        current.append(x.content)
                    if x.type == 'tr_close':
                        for n, value in enumerate(current):
                            cell = self.sheet.cell(self.row, self.body_col+n, value)
                            cell.data_type = 's'
                            cell.font = Font(name='Aptos', size=11, color='000000')
                        self.row += 1
                    j += 1
                self.blank()
                i = j
            i += 1
        self.sheet.freeze_panes = None
        return self.book


def main():
    parser = argparse.ArgumentParser(description='Markdownを読みやすいExcelブックに変換します')
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error('入力Markdownが見つかりません')
    if args.output.exists():
        parser.error('出力先が既に存在します。別名を指定してください')
    builder = Builder(args.input.resolve())
    try:
        builder.build(args.input.read_text(encoding='utf-8'))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        builder.book.save(args.output)
    except Exception as exc:
        print(f'変換失敗: {exc}', file=sys.stderr)
        return 1
    print(f'作成: {args.output} / 埋め込み画像: {builder.images}点')
    for warning in builder.warnings:
        print('警告: ' + warning, file=sys.stderr)
    return 2 if builder.warnings else 0


if __name__ == '__main__':
    raise SystemExit(main())
