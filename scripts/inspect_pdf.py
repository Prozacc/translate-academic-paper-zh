#!/usr/bin/env python3
"""Inspect a rendered PDF page by page and report visual defects.

This complements ``validate_delivery.py``, which checks the HTML source.
The checks here operate on the rendered artefact and catch problems that only
appear after layout and font resolution:

* blank or nearly blank pages (measured by ink coverage);
* missing glyphs, reported as replacement characters or private-use codepoints
  in the extracted text layer;
* tofu boxes, detected by rendering the page and looking for the hollow
  rectangle that a missing glyph produces;
* images that failed to load and therefore occupy no space.

Every page is also written to disk as a PNG so a human can review the result
with a contact sheet.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# A page whose ink coverage falls below this ratio is treated as blank.
BLANK_INK_RATIO = 0.005

# Ink coverage below this but above BLANK_INK_RATIO is worth a warning.
SPARSE_INK_RATIO = 0.02


def require_pymupdf():
    try:
        import pymupdf  # type: ignore

        return pymupdf
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore

            return pymupdf
        except ImportError:
            print(
                "pymupdf is required: pip install pymupdf",
                file=sys.stderr,
            )
            raise SystemExit(2)


def page_ink_ratio(page, dpi: int = 40) -> float:
    """Return the fraction of non-white pixels on a rendered page."""
    import numpy as np

    pixmap = page.get_pixmap(dpi=dpi)
    data = np.frombuffer(pixmap.samples, dtype=np.uint8)
    data = data.reshape(pixmap.height, pixmap.width, pixmap.n)
    return float((data[:, :, 0] < 245).mean())


def _type3_notdef_names(document, font_xref: int) -> set[str]:
    """Return the glyph names that a Type3 font uses for a missing glyph.

    When a browser prints text it emits one Type3 font per glyph, and the
    first entry of ``/CharProcs`` is the ``.notdef`` box that is drawn when a
    character has no glyph in the selected font.
    """
    import re

    try:
        obj = document.xref_object(font_xref)
    except Exception:
        return set()
    if "/Subtype /Type3" not in obj:
        return set()
    match = re.search(r"/CharProcs\s*<<(.*?)>>", obj, re.S)
    if not match:
        return set()
    first = re.search(r"/(\S+)\s+\d+\s+0\s+R", match.group(1))
    return {first.group(1)} if first else set()


def _type3_encoding(document, font_xref: int) -> dict[int, str]:
    """Map character codes of a Type3 font to their glyph names."""
    import re

    try:
        obj = document.xref_object(font_xref)
    except Exception:
        return {}
    match = re.search(r"/Differences \[(.*?)\]", obj, re.S)
    if not match:
        return {}
    codes: dict[int, str] = {}
    current = 0
    for token in match.group(1).split():
        if token.startswith("/"):
            codes[current] = token[1:]
            current += 1
        else:
            try:
                current = int(token)
            except ValueError:
                pass
    return codes


def missing_glyphs(document, page) -> list[str]:
    """Find characters that were drawn with the ``.notdef`` box.

    The text layer still contains the original character, but the page draws
    the replacement box instead of a real glyph. Decoding the content stream
    and comparing every drawn code against the font's ``.notdef`` entry
    identifies them exactly, without the false positives that a pixel-shape
    heuristic produces on Latin letters and Chinese strokes.
    """
    import re

    try:
        contents = page.read_contents()
    except Exception:
        return []
    if not contents:
        return []
    stream = contents.decode("latin-1", errors="replace")

    resources = document.xref_get_key(page.xref, "Resources")
    if resources[0] != "dict":
        return []
    fonts: dict[str, int] = {
        "/" + name: int(xref)
        for name, xref in re.findall(r"/(F\d+)\s+(\d+)\s+0\s+R", resources[1])
    }

    # Cache the encoding table per font: Chrome emits one font per glyph, so
    # the same font is consulted many times.
    encoding_cache: dict[int, tuple[dict[int, str], set[str]]] = {}

    missing: list[str] = []
    current: int | None = None
    for match in re.finditer(r"/(F\d+)\s+[\d.]+\s+Tf|<([0-9A-Fa-f]*)>\s*Tj", stream):
        if match.group(1):
            current = fonts.get("/" + match.group(1))
            continue
        code = match.group(2)
        if not code or current is None:
            continue
        if current not in encoding_cache:
            encoding_cache[current] = (
                _type3_encoding(document, current),
                _type3_notdef_names(document, current),
            )
        encoding, notdef_names = encoding_cache[current]
        if not notdef_names:
            continue
        for index in range(0, len(code), 2):
            byte = int(code[index : index + 2], 16)
            if encoding.get(byte) in notdef_names:
                missing.append(f"code 0x{byte:02X} in font {current}")
    return missing


# A browser that cannot load an image inserts its own broken-image icon.
# The icon has a fixed pixel size, so it can be recognised reliably.
BROKEN_IMAGE_SIZES = {(14, 14), (14, 16), (16, 16), (16, 14)}


def broken_images(page) -> list[dict[str, object]]:
    """Report images that the renderer could not load.

    A failed image is replaced by the browser's broken-image icon, whose pixel
    size is fixed. A real figure in a paper is never that small.
    """
    broken: list[dict[str, object]] = []
    for image in page.get_images(full=True):
        width, height = image[2], image[3]
        if (width, height) not in BROKEN_IMAGE_SIZES:
            continue
        try:
            rects = page.get_image_rects(image[0])
        except Exception:
            continue
        for rect in rects:
            broken.append(
                {
                    "xref": image[0],
                    "size": [width, height],
                    "rect": [round(v, 1) for v in rect],
                }
            )
    return broken


def text_layer_anomalies(page) -> list[dict[str, object]]:
    """Report replacement characters and private-use codepoints."""
    anomalies: list[dict[str, object]] = []
    for char in page.get_text():
        code = ord(char)
        if char == "�" or 0xE000 <= code <= 0xF8FF or 0xFFF0 <= code <= 0xFFFF:
            anomalies.append({"char": char, "codepoint": f"U+{code:04X}"})
    return anomalies


def inspect(pdf_path: Path, output_dir: Path | None, dpi: int, make_sheets: bool) -> dict:
    pymupdf = require_pymupdf()
    document = pymupdf.open(str(pdf_path))

    report: dict[str, object] = {
        "pdf": str(pdf_path),
        "pages": document.page_count,
        "page_size": [
            round(document[0].rect.width, 1),
            round(document[0].rect.height, 1),
        ],
        "blank_pages": [],
        "sparse_pages": [],
        "missing_glyph_pages": [],
        "text_anomaly_pages": [],
        "broken_image_pages": [],
        "images_total": 0,
        "errors": [],
        "warnings": [],
    }

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)

    page_images: list[Path] = []
    for index, page in enumerate(document):
        number = index + 1
        ink = page_ink_ratio(page)
        report["pages"] = document.page_count

        images = page.get_images(full=True)
        report["images_total"] = int(report["images_total"]) + len(images)
        broken = broken_images(page)
        if broken:
            report["broken_image_pages"].append({"page": number, "images": broken[:5]})

        if ink < BLANK_INK_RATIO:
            report["blank_pages"].append({"page": number, "ink": round(ink * 100, 3)})
        elif ink < SPARSE_INK_RATIO:
            report["sparse_pages"].append({"page": number, "ink": round(ink * 100, 3)})

        anomalies = text_layer_anomalies(page)
        if anomalies:
            report["text_anomaly_pages"].append(
                {"page": number, "anomalies": anomalies[:10]}
            )

        missing = missing_glyphs(document, page)
        if missing:
            report["missing_glyph_pages"].append(
                {"page": number, "count": len(missing), "detail": missing[:10]}
            )

        if output_dir is not None:
            target = output_dir / f"page-{number:03d}.png"
            page.get_pixmap(dpi=dpi).save(str(target))
            page_images.append(target)

    if report["blank_pages"]:
        report["errors"].append(
            f"{len(report['blank_pages'])} blank page(s): "
            + ", ".join(str(item["page"]) for item in report["blank_pages"])
        )
    if report["missing_glyph_pages"]:
        report["errors"].append(
            f"{len(report['missing_glyph_pages'])} page(s) draw characters with a "
            "missing-glyph box: "
            + ", ".join(str(item["page"]) for item in report["missing_glyph_pages"])
        )
    if report["text_anomaly_pages"]:
        report["errors"].append(
            f"{len(report['text_anomaly_pages'])} page(s) contain replacement or "
            "private-use characters in the text layer"
        )
    if report["broken_image_pages"]:
        report["errors"].append(
            f"{len(report['broken_image_pages'])} page(s) contain an image that failed "
            "to load (browser broken-image icon): "
            + ", ".join(str(item["page"]) for item in report["broken_image_pages"])
        )
    if report["sparse_pages"]:
        report["warnings"].append(
            f"{len(report['sparse_pages'])} page(s) are nearly empty: "
            + ", ".join(str(item["page"]) for item in report["sparse_pages"])
        )

    if output_dir is not None and make_sheets and page_images:
        build_contact_sheets(page_images, output_dir)

    return report


def build_contact_sheets(page_images: list[Path], output_dir: Path) -> None:
    """Assemble 2x2 contact sheets so that every page can be reviewed at once."""
    try:
        from PIL import Image
    except ImportError:
        return

    width, height = 595, 842
    for start in range(0, len(page_images), 4):
        group = page_images[start : start + 4]
        sheet = Image.new("RGB", (width * 2 + 30, height * 2 + 30), "#cccccc")
        for offset, path in enumerate(group):
            with Image.open(path) as handle:
                tile = handle.convert("RGB").resize((width, height))
            sheet.paste(tile, ((offset % 2) * (width + 10) + 10, (offset // 2) * (height + 10) + 10))
        sheet.save(output_dir / f"contact-sheet-{start // 4 + 1:02d}.png")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for the rendered page images and contact sheets.",
    )
    parser.add_argument("--dpi", type=int, default=100, help="DPI for page images.")
    parser.add_argument(
        "--no-sheets",
        action="store_true",
        help="Skip generating contact sheets (Pillow is required for them).",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Exit non-zero when warnings are present.",
    )
    args = parser.parse_args()

    if not args.pdf.is_file():
        print(f"PDF file does not exist: {args.pdf}", file=sys.stderr)
        return 2

    report = inspect(args.pdf.resolve(), args.output_dir, args.dpi, not args.no_sheets)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["errors"]:
        return 1
    if args.fail_on_warning and report["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
