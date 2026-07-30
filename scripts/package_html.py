#!/usr/bin/env python3
"""Package an editable HTML paper and its local assets into a ZIP file."""

from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        key = "src" if tag in {"img", "script", "source"} else "href"
        if tag in {"img", "script", "source", "link"} and values.get(key):
            self.references.add(values[key] or "")


def local_relative(reference: str) -> Path | None:
    parsed = urlparse(reference)
    if parsed.scheme in {"http", "https", "data"} or reference.startswith("#"):
        return None
    raw = unquote(parsed.path)
    if not raw:
        return None
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe asset reference: {reference}")
    return relative


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    html_path = args.html.resolve()
    output_path = args.output.resolve()
    if not html_path.is_file():
        raise FileNotFoundError(html_path)
    if output_path.suffix.lower() != ".zip":
        raise ValueError("--output must end with .zip")

    inventory = AssetParser()
    inventory.feed(html_path.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="paper-translation-") as temp:
        package_root = Path(temp) / html_path.stem
        package_root.mkdir()
        shutil.copy2(html_path, package_root / html_path.name)

        missing: list[str] = []
        for reference in sorted(inventory.references):
            relative = local_relative(reference)
            if relative is None:
                continue
            source = (html_path.parent / relative).resolve()
            if not source.is_file():
                missing.append(reference)
                continue
            destination = package_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

        if missing:
            raise FileNotFoundError("Missing local assets: " + ", ".join(missing))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for item in sorted(package_root.rglob("*")):
                if item.is_file():
                    archive.write(item, item.relative_to(package_root.parent))

    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
