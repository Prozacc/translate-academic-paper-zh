# -*- coding: utf-8 -*-
"""Measure CJK character stretching and right-margin overflow in a rendered PDF.

Chinese text is normally set with `text-align: justify`.  Chrome implements
that for CJK by *stretching the characters themselves* (the `inter-ideograph`
justification mode).  When a line ends with a wide inline formula, only a few
Chinese characters are left on that line and the whole slack is poured into
them - they can end up 2.5x their natural width, which reads as a defect.

The browser's DOM geometry does not match the print layout, so the only
trustworthy witness is the PDF itself.  This script

  * groups every text span into visual lines by its baseline,
  * computes the advance between two neighbouring CJK glyphs and compares it
    with the font size of the line (a ratio near 1 means normal spacing, a
    ratio far above 1 means the line was stretched by justification),
  * lists every line whose ratio exceeds a threshold,
  * reports every line that crosses the right text margin.

Usage::

    python scripts/measure_cjk_stretch.py --pdf outputs/Paper_zh.pdf

A ratio above ~1.55 is a visible defect; fix the offending paragraph by
setting it ragged-right (``text-align: left``) rather than by changing the
global justification mode, which would make every other paragraph worse.
"""
import argparse
import json
import sys

try:
    import pymupdf as fitz  # type: ignore
except ImportError:  # pragma: no cover - dependency check
    try:
        import fitz  # type: ignore
    except ImportError:
        raise SystemExit('pymupdf is required: pip install pymupdf')

# A CJK advance larger than this multiple of the font size counts as stretched.
STRETCH_RATIO = 1.55

# Default @page margins of assets/paper-zh.css.
PAGE_WIDTH_MM = 210
RIGHT_MARGIN_MM = 17
LEFT_MARGIN_MM = 17

MM_TO_PT = 72.0 / 25.4


def is_cjk(ch):
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF or 0x3000 <= o <= 0x303F
            or 0xFF00 <= o <= 0xFFEF or 0x3400 <= o <= 0x4DBF)


def lines_of(page):
    """Group the page text into visual lines, keyed by baseline.

    `rawdict` gives the bounding box of every single character, so the
    advance between two neighbours is measured, not estimated.
    """
    raw = []
    for blk in page.get_text('rawdict')['blocks']:
        if blk.get('type') != 0:
            continue
        for line in blk['lines']:
            for sp in line['spans']:
                if not sp.get('chars'):
                    continue
                size = sp['size']
                for ch in sp['chars']:
                    c = ch['c']
                    if not c.strip():
                        continue
                    x0, y0, x1, y1 = ch['bbox']
                    raw.append((y0, y1, x0, x1, size, c))
    raw.sort(key=lambda r: (round(r[0], 1), r[2]))

    lines = []
    for item in raw:
        top, bot, x0, x1, size, text = item
        placed = False
        for ln in lines:
            if abs(ln['top'] - top) <= 2.0 and abs(ln['bot'] - bot) <= 2.0:
                ln['items'].append(item)
                ln['top'] = min(ln['top'], top)
                ln['bot'] = max(ln['bot'], bot)
                placed = True
                break
        if not placed:
            lines.append({'top': top, 'bot': bot, 'items': [item]})
    for ln in lines:
        ln['items'].sort(key=lambda r: r[2])
    return lines


def line_ratio(items):
    """Average advance/font-size of the neighbouring CJK glyphs on a line."""
    size = max(i[4] for i in items)
    if size <= 0:
        return 0.0, 0
    gaps = []
    for k in range(len(items) - 1):
        c0, ch0, sz0 = items[k][2], items[k][5], items[k][4]
        c1, ch1 = items[k + 1][2], items[k + 1][5]
        if not (is_cjk(ch0) and is_cjk(ch1)):
            continue
        g = c1 - c0
        if 0.2 < g < sz0 * 3:
            gaps.append(g / sz0)
    if len(gaps) < 4:
        return 0.0, len(gaps)
    return sum(gaps) / len(gaps), len(gaps)


def analyse(path, right_margin_mm=RIGHT_MARGIN_MM, page_width_mm=PAGE_WIDTH_MM):
    doc = fitz.open(path)
    page_count = doc.page_count
    rows = []
    overflow = []
    for pno in range(doc.page_count):
        page = doc[pno]
        right_edge = page.rect.width - right_margin_mm * MM_TO_PT
        for ln in lines_of(page):
            items = ln['items']
            if not items:
                continue
            ratio, n = line_ratio(items)
            text = ''.join(i[5] for i in items)
            if n >= 4:
                rows.append({'page': pno + 1, 'ratio': round(ratio, 2),
                             'n': n, 'text': text[:80]})
            xmax = max(i[3] for i in items)
            if xmax > right_edge + 1.0:
                overflow.append({'page': pno + 1, 'x': round(xmax, 1),
                                 'text': text[:60]})
    doc.close()

    per_page = {}
    for r in rows:
        cur = per_page.get(r['page'], 0.0)
        if r['ratio'] > cur:
            per_page[r['page']] = r['ratio']
    return page_count, per_page, rows, overflow


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pdf', required=True)
    ap.add_argument('--threshold', type=float, default=STRETCH_RATIO,
                    help='ratio above which a line counts as stretched')
    ap.add_argument('--list-threshold', type=float, default=1.15,
                    help='ratio above which a line is listed individually')
    ap.add_argument('--right-margin-mm', type=float, default=RIGHT_MARGIN_MM)
    ap.add_argument('--page-width-mm', type=float, default=PAGE_WIDTH_MM)
    ap.add_argument('--json', help='write the full result as JSON')
    args = ap.parse_args()

    page_count, per_page, lines, overflow = analyse(args.pdf, args.right_margin_mm,
                                                    args.page_width_mm)
    ratios = sorted(per_page.values(), reverse=True)
    stretched = [r for r in lines if r['ratio'] > args.threshold]
    listed = sorted((r for r in lines if r['ratio'] > args.list_threshold),
                    key=lambda r: -r['ratio'])

    print('pdf: %s' % args.pdf)
    print('pages: %d | measured lines: %d | max ratio: %.2f | top6: %s'
          % (page_count, len(lines), ratios[0] if ratios else 0.0,
             [round(r, 2) for r in ratios[:6]]))
    print('stretched lines (> %.2f): %d' % (args.threshold, len(stretched)))
    for r in stretched:
        print('   p%-3d %.2f  %s' % (r['page'], r['ratio'], r['text']))
    print('lines above %.2f: %d' % (args.list_threshold, len(listed)))
    for r in listed:
        print('   p%-3d %.2f n=%-3d %s' % (r['page'], r['ratio'], r['n'], r['text']))
    print('right-margin overflow: %d' % len(overflow))
    for o in overflow:
        print('   p%-3d x=%.1f  %s' % (o['page'], o['x'], o['text']))

    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump({'pdf': args.pdf, 'pages': page_count, 'per_page': per_page,
                       'lines': lines, 'overflow': overflow}, fh,
                      ensure_ascii=False, indent=1)
        print('json:', args.json)


if __name__ == '__main__':
    main()
