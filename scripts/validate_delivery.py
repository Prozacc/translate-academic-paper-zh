#!/usr/bin/env python3
"""Validate translated academic HTML/PDF deliverables using lightweight checks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse


class InventoryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.counts = {
            "headings": 0,
            "figures": 0,
            "images": 0,
            "tables": 0,
            "math": 0,
            "bibliography_items": 0,
        }
        self.assets: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if re.fullmatch(r"h[1-6]", tag):
            self.counts["headings"] += 1
        elif tag == "figure":
            self.counts["figures"] += 1
        elif tag == "img":
            self.counts["images"] += 1
            if values.get("src"):
                self.assets.append(values["src"] or "")
        elif tag == "table":
            self.counts["tables"] += 1
        elif tag == "math":
            self.counts["math"] += 1
        elif tag == "li" and any(
            key in (values.get("class") or "").lower()
            for key in ("bib", "reference")
        ):
            self.counts["bibliography_items"] += 1

        if tag == "link" and values.get("href"):
            self.assets.append(values["href"] or "")

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text.append(data)


def local_asset_path(base: Path, reference: str) -> Path | None:
    parsed = urlparse(reference)
    if parsed.scheme in {"http", "https", "data"} or reference.startswith("#"):
        return None
    raw = unquote(parsed.path)
    if not raw:
        return None
    return (base / raw).resolve()


def pdf_info(path: Path) -> dict[str, object]:
    result: dict[str, object] = {"exists": path.is_file(), "bytes": 0}
    if not path.is_file():
        return result
    result["bytes"] = path.stat().st_size
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        result["pages"] = len(reader.pages)
        result["encrypted"] = reader.is_encrypted
    except Exception as exc:  # Optional dependency or malformed PDF.
        result["inspection_warning"] = str(exc)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--pdf", type=Path)
    args = parser.parse_args()

    html_path = args.html.resolve()
    report: dict[str, object] = {
        "html": str(html_path),
        "errors": [],
        "warnings": [],
    }
    errors: list[str] = report["errors"]  # type: ignore[assignment]
    warnings: list[str] = report["warnings"]  # type: ignore[assignment]

    if not html_path.is_file():
        errors.append("HTML file does not exist")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    raw = html_path.read_text(encoding="utf-8")
    inv = InventoryParser()
    inv.feed(raw)
    visible = " ".join(inv.text)
    han = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", visible))
    latin_words = len(re.findall(r"\b[A-Za-z]{3,}\b", visible))

    missing_assets: list[str] = []
    for reference in sorted(set(inv.assets)):
        target = local_asset_path(html_path.parent, reference)
        if target is not None and not target.is_file():
            missing_assets.append(reference)
    if missing_assets:
        errors.append(f"{len(missing_assets)} local assets are missing")
    if "\ufffd" in raw:
        errors.append("Unicode replacement characters found")
    if han == 0:
        errors.append("No Chinese characters found")
    if inv.counts["headings"] == 0:
        warnings.append("No heading elements found")
    if latin_words > han:
        warnings.append("Latin word count exceeds Han character count; review residual English")

    report["inventory"] = inv.counts
    report["text"] = {
        "han_characters": han,
        "latin_words": latin_words,
    }
    report["missing_assets"] = missing_assets
    if args.pdf:
        report["pdf"] = pdf_info(args.pdf.resolve())
        if not report["pdf"]["exists"]:  # type: ignore[index]
            errors.append("PDF file does not exist")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
