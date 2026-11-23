# -*- coding: utf-8 -*-
"""Find the inline formulas that are too wide to fit on a single line.

Chrome treats an inline <math> element as one atomic inline box and never
breaks it, so a wide formula is pushed to the next line as a whole and the
short line left behind gets stretched by `text-align: justify`.  TeX breaks
inline formulas at binary operators instead.  This script measures every
inline formula in the rendered page and writes the ids of the ones that need
a break opportunity, so that `build_paper.py` can cut them.

Usage::

    python scripts/measure_inline.py --html outputs/Paper_zh.html --out work/split_ids.json

Run it once after the first build, then rebuild with ``--split-ids``.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
CHROME_CANDIDATES = [
    DEFAULT_CHROME,
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
]

# The text block of the printed page: A4 width minus the @page margins.
TEXT_WIDTH_MM = 210 - 2 * 17
# A formula is worth cutting once it occupies more than this share of the
# text block; below that it always fits on a line of its own.
CUT_RATIO = 0.30

INJECT = r"""
<script>
window.addEventListener('load', function () {
  var out = [];
  var all = document.querySelectorAll('math[id]');
  for (var i = 0; i < all.length; i++) {
    var m = all[i];
    if (m.getAttribute('display') === 'block') continue;
    var r = document.createRange();
    r.selectNodeContents(m);
    var b = r.getBoundingClientRect();
    if (b.width > 0) {
      out.push({id: m.id, w: Math.round(b.width * 100) / 100,
                left: Math.round(b.left * 100) / 100,
                top: Math.round(b.top * 100) / 100});
    }
  }
  var pre = document.createElement('pre');
  pre.id = 'RESULT';
  pre.textContent = JSON.stringify({
    width: document.documentElement.clientWidth,
    maths: out
  });
  document.body.appendChild(pre);
});
</script>
"""


def find_chrome(explicit=None):
    if explicit:
        return explicit
    for cand in CHROME_CANDIDATES:
        if os.path.exists(cand):
            return cand
    raise SystemExit('Chrome/Edge not found; pass --chrome <path>')


def measure(html_path, chrome):
    probe = str(html_path) + '.probe.html'
    src = Path(html_path).read_text(encoding='utf-8').replace('</body>', INJECT + '</body>')
    Path(probe).write_text(src, encoding='utf-8')
    r = subprocess.run(
        [chrome, '--headless=new', '--disable-gpu', '--no-sandbox',
         '--window-size=1400,1200', '--virtual-time-budget=40000', '--dump-dom',
         'file:///' + os.path.abspath(probe).replace('\\', '/')],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
    d = r.stdout
    i = d.find('<pre id="RESULT">')
    if i < 0:
        print('NO RESULT', (r.stderr or '')[-500:])
        raise SystemExit(1)
    j = d.find('</pre>', i)
    return json.loads(d[d.find('>', i) + 1:j])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--html', required=True)
    ap.add_argument('--out', required=True, help='JSON file receiving the ids to cut')
    ap.add_argument('--chrome')
    ap.add_argument('--cut-ratio', type=float, default=CUT_RATIO)
    ap.add_argument('--text-width-mm', type=float, default=TEXT_WIDTH_MM)
    args = ap.parse_args()

    chrome = find_chrome(args.chrome)
    data = measure(args.html, chrome)

    text_width_px = args.text_width_mm / 25.4 * 96
    limit = text_width_px * args.cut_ratio
    wide = [m for m in data['maths'] if m['w'] > limit]
    ids = sorted(m['id'] for m in wide)

    Path(args.out).write_text(json.dumps(ids, indent=1), encoding='utf-8')
    print('viewport width:', data['width'])
    print('inline formulas measured:', len(data['maths']))
    print('cut threshold: %.0f px (%.0f%% of the text block)' % (limit, args.cut_ratio * 100))
    print('formulas to cut:', len(ids))
    for m in sorted(wide, key=lambda x: -x['w'])[:20]:
        print('   %-8s %7.1f px' % (m['id'], m['w']))
    print('written:', args.out)


if __name__ == '__main__':
    main()
