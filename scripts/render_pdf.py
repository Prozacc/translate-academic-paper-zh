# -*- coding: utf-8 -*-
"""Render an HTML master to PDF with headless Chrome.

Usage::

    python scripts/render_pdf.py --html outputs/Paper_zh.html --pdf outputs/Paper_zh.pdf

The page size and the margins come from the ``@page`` rule of the HTML
stylesheet, so the CSS asset shipped with this skill governs the result.
"""
import argparse
import os
import shutil
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


def find_chrome(explicit=None):
    if explicit:
        return explicit
    for cand in CHROME_CANDIDATES:
        if os.path.exists(cand):
            return cand
    found = shutil.which('google-chrome') or shutil.which('chromium') \
        or shutil.which('chromium-browser') or shutil.which('msedge')
    if found:
        return found
    raise SystemExit('Chrome/Edge not found; pass --chrome <path>')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--html', required=True)
    ap.add_argument('--pdf', required=True)
    ap.add_argument('--chrome', help='path to the browser binary')
    ap.add_argument('--header-footer', action='store_true',
                    help='keep the default browser header and footer')
    args = ap.parse_args()

    html_path = Path(args.html).resolve()
    pdf_path = Path(args.pdf).resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    chrome = find_chrome(args.chrome)
    # Render to a sibling temporary file and move it into place.  Deleting the
    # previous PDF first is unreliable: a preview panel may still hold the file
    # open, and a recycle-bin based delete can be refused.
    tmp_path = pdf_path.with_name(pdf_path.stem + '.rendering.pdf')
    if tmp_path.exists():
        try:
            tmp_path.unlink()
        except OSError:
            tmp_path = pdf_path.with_name(pdf_path.stem + '.rendering2.pdf')

    cmd = [chrome, '--headless=new', '--disable-gpu', '--no-sandbox']
    if not args.header_footer:
        cmd.append('--no-pdf-header-footer')
    cmd.append('--print-to-pdf=' + str(tmp_path))
    cmd.append('file:///' + str(html_path).replace('\\', '/'))

    print('$', ' '.join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        sys.stderr.write(r.stderr or '')
    if not tmp_path.exists():
        raise SystemExit('render failed: no PDF produced')

    try:
        os.replace(str(tmp_path), str(pdf_path))
    except OSError:
        with open(pdf_path, 'wb') as fh:
            fh.write(tmp_path.read_bytes())
        try:
            tmp_path.unlink()
        except OSError:
            pass
    print('pdf:', pdf_path, pdf_path.stat().st_size)


if __name__ == '__main__':
    main()
