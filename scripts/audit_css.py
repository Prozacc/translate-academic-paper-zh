# -*- coding: utf-8 -*-
"""Report the CSS classes an HTML document uses but the stylesheet does not define.

A class that is missing from the stylesheet is silently unstyled: the block
still renders, but with the browser defaults, which is easy to miss in a
long document.  Run this after adding a new block type to a paper.

Usage::

    python scripts/audit_css.py --html outputs/Paper_zh.html \\
        --css assets/paper-zh.css
"""
import argparse
import re
from pathlib import Path

CLASS_ATTR = re.compile(r'class="([^"]+)"')
SELECTOR_CLASS = re.compile(r'\.([A-Za-z_][\w-]*)')
COMMENT = re.compile(r'/\*.*?\*/', re.S)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--html', required=True)
    ap.add_argument('--css', required=True)
    args = ap.parse_args()

    html = Path(args.html).read_text(encoding='utf-8')
    css = Path(args.css).read_text(encoding='utf-8')

    used = set()
    for m in CLASS_ATTR.finditer(html):
        used.update(m.group(1).split())

    defined = set(SELECTOR_CLASS.findall(COMMENT.sub('', css)))

    missing = sorted(used - defined)
    print('classes used     :', len(used))
    print('classes defined  :', len(defined))
    print('used but unstyled:', len(missing))
    for c in missing:
        print('   .%s' % c)


if __name__ == '__main__':
    main()
