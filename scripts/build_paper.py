# -*- coding: utf-8 -*-
"""Assemble the translated parts of a paper into one Chinese HTML master.

The parts are plain HTML fragments (``part1.html`` ... ``partN.html``) that
carry the translated prose, the LaTeX of every formula, and the document
skeleton.  This script

  * converts every ``$...$`` / ``$$...$$`` formula to MathML,
  * numbers the inline formulas (``m1``, ``m2``, ...) so that later passes
    can refer to them,
  * cuts the inline formulas listed in the split-id file at their top-level
    binary operators so that Chrome can break them like TeX does,
  * injects the shared stylesheet (assets/paper-zh.css) into the document,
  * injects the bibliography at the ``<!--REFS-->`` placeholder,
  * copies the image assets next to the output.

Usage::

    python scripts/build_paper.py \\
        --parts work/parts \\
        --out outputs/Paper_zh.html \\
        --css scripts/../assets/paper-zh.css \\
        --macros work/macros.json \\
        --refs work/refs.json \\
        --split-ids work/split_ids.json \\
        --assets work/assets
"""
import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latex_mathml as _mm


MATH_RE = re.compile(r"\$\$(.+?)\$\$|\$([^$\n]+?)\$", re.S)


def ref_text(item):
    """Turn one bibliography record into a plain reference line.

    The text is escaped *before* the italic markers are turned into markup,
    otherwise the `<em>` tags are escaped as well and the browser prints them
    as literal text.
    """
    text = item["text"]
    text = re.sub(r"\\url\{([^}]*)\}", r"\1", text)
    text = text.replace("\\&", "&").replace("\\%", "%").replace("\\$", "$")
    text = text.replace("{", "").replace("}", "")
    text = text.replace("--", "–")
    text = re.sub(r"\s+", " ", text).strip()
    text = html.escape(text, quote=False)
    # The [[I]] markers come from the LaTeX \em scope (italic venue / title).
    text = re.sub(r"\[\[I\]\](.*?)\[\[/I\]\]", r"<em>\1</em>", text)
    return text


def build_refs(refs):
    items = []
    for r in refs:
        items.append(
            '<li class="bib"><span class="refnum">[%d]</span> %s.</li>'
            % (r["n"], ref_text(r))
        )
    return "\n".join(items)


def replace_math(text, counter, split_ids, config):
    """Replace every LaTeX formula with its MathML rendering."""
    def repl(m):
        if m.group(1) is not None:
            return _mm.to_mathml(m.group(1), display=True, config=config)
        counter[0] += 1
        mid = "m%d" % counter[0]
        xml = _mm.to_mathml(m.group(2), display=False, inline_id=mid, config=config)
        if mid in split_ids:
            xml = _mm.split_inline_math(xml)
        return xml

    return MATH_RE.sub(repl, text)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--parts', required=True,
                    help='directory holding part*.html fragments')
    ap.add_argument('--out', required=True, help='output HTML file')
    ap.add_argument('--css', help='stylesheet injected into the <style> block')
    ap.add_argument('--macros', help='JSON macro configuration')
    ap.add_argument('--refs', help='JSON bibliography')
    ap.add_argument('--split-ids', help='JSON list of inline formula ids to cut')
    ap.add_argument('--assets', help='directory of images to copy to <out>/assets')
    args = ap.parse_args()

    parts_dir = Path(args.parts)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    config = _mm.load_config(args.macros)
    split_ids = set()
    if args.split_ids and Path(args.split_ids).exists():
        split_ids = set(json.loads(Path(args.split_ids).read_text(encoding='utf-8')))

    counter = [0]
    chunks = []
    for path in sorted(parts_dir.glob('part*.html')):
        raw = path.read_text(encoding='utf-8')
        raw = replace_math(raw, counter, split_ids, config)
        chunks.append(raw)
        print('part:', path.name)

    doc = "\n".join(chunks)

    if args.css:
        css = Path(args.css).read_text(encoding='utf-8')
        if '<style' in doc:
            doc = re.sub(r'<style[^>]*>.*?</style>',
                         lambda _m: '<style>\n%s\n</style>' % css,
                         doc, count=1, flags=re.S)
        else:
            doc = re.sub(r'(</head>)', r'\1\n<style>\n%s\n</style>' % css,
                         doc, count=1)
        print('css:', args.css, len(css), 'bytes')

    if '<!--REFS-->' in doc:
        refs = json.loads(Path(args.refs).read_text(encoding='utf-8')) if args.refs else []
        doc = doc.replace('<!--REFS-->', build_refs(refs))

    leftover = re.findall(r'\$\$?[^$]{0,40}\$', doc)
    if leftover:
        print('WARN leftover math delimiters:', leftover[:5])

    out.write_text(doc, encoding='utf-8')
    print('html:', out, out.stat().st_size)
    print('inline formulas:', counter[0], '| split:', len(split_ids))

    if args.assets:
        dest = out.parent / 'assets'
        dest.mkdir(parents=True, exist_ok=True)
        for item in sorted(Path(args.assets).glob('*.png')):
            shutil.copy2(item, dest / item.name)
        print('assets:', len(list(dest.glob('*.png'))))


if __name__ == '__main__':
    main()
