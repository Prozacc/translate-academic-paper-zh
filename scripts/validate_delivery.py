#!/usr/bin/env python3
"""Validate translated academic HTML/PDF deliverables using lightweight checks.

The checks are intentionally conservative: they flag conditions that are almost
always defects in a translated paper, and stay silent on patterns that are
legitimate (kept English references, model names, retained figure labels).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

# Blocks whose text is prose and therefore must be translated.
PROSE_TAGS = {"p", "li", "td", "th", "figcaption", "caption", "h1", "h2", "h3", "h4", "h5", "h6"}

# Combining marks that commonly have no glyph in CJK font stacks and render as
# tofu boxes (U+25AF) in Chrome/PDF output.
RISKY_COMBINING = {
    "⃐": "U+20D0",
    "⃑": "U+20D1",
    "⃒": "U+20D2",
    "⃗": "U+20D7",
    "̂": "U+0302",
    "̃": "U+0303",
    "̄": "U+0304",
    "̅": "U+0305",
    "̆": "U+0306",
    "̇": "U+0307",
    "̈": "U+0308",
    "̋": "U+030B",
    "̌": "U+030C",
    "̐": "U+0310",
    "̑": "U+0311",
    "⃗": "U+20D7",
}

# Words that legitimately stay in English inside an otherwise Chinese document.
ALLOWED_ENGLISH_TOKENS = {
    "IEEE", "ACM", "arXiv", "DOI", "URL", "ISBN", "ISSN", "PDF", "HTML", "XML",
    "API", "GPU", "CPU", "HTTP", "HTTPS", "JSON", "CSV", "SQL", "GPU",
    "Transformer", "BERT", "LSTM", "GRU", "RNN", "CNN", "SVM", "KNN",
    "MSE", "MAE", "MRE", "RMSE", "R2", "R^2", "MAPE", "SNR", "PSD", "FFT",
    "SOTA", "MoE", "ML", "DL", "AI", "AGI", "LLM", "NLP", "CV", "RL", "RLHF",
    "IEEE", "Springer", "Elsevier", "Wiley", "ACM", "Nature", "Science",
    "Google", "Microsoft", "Amazon", "Meta", "OpenAI", "Anthropic", "NVIDIA",
    "PyTorch", "TensorFlow", "NumPy", "SciPy", "MATLAB", "R", "Python",
    "Java", "C++", "Linux", "Windows", "GitHub", "GitLab", "SQL", "NoSQL",
}

# English sentence fragments that are expected in a bilingual paper.
ALLOWED_ENGLISH_PHRASES = {
    "et al", "i.e", "e.g", "etc", "vs", "fig", "figs", "eq", "eqs",
    "table", "tab", "section", "sec", "appendix", "vol", "no", "pp",
}

# Structural elements that legitimately keep the source language: the paper
# title (often a model name plus the original English title), the running head
# and the venue line.
SOURCE_LANGUAGE_TAGS = {"h1"}

# Class names used to mark a span whose English text is deliberately kept
# (bilingual captions, original English subtitle, bibliography entries).
SOURCE_LANGUAGE_CLASSES = {
    "cap-en",
    "caption-en",
    "subtitle-en",
    "title-en",
    "original",
    "en",
}


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
            "table_cells": 0,
            "empty_table_cells": 0,
            "empty_tables": 0,
        }
        self.assets: list[str] = []
        self.text: list[str] = []
        # Per-paragraph residual-English candidates.
        self.english_paragraphs: list[str] = []
        # Risky combining marks found in the source text.
        self.risky_marks: dict[str, int] = {}
        # Table cell emptiness tracking.
        self._table_stack: list[dict[str, object]] = []
        self._cell_stack: list[dict[str, object]] = []
        # Block-level text accumulation: each entry tracks its tag and whether it
        # belongs to a bibliography list (references are intentionally kept in
        # the original language and must never be reported as residual English).
        self._blocks: list[dict[str, object]] = []
        self._in_bibliography = False
        # Open elements whose text is deliberately kept in the source language.
        self._keep_source_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = {c for c in (values.get("class") or "").split() if c}
        keep_source = bool(classes & SOURCE_LANGUAGE_CLASSES)
        if keep_source:
            # Text inside a deliberately kept-English span must not count as
            # untranslated prose in the enclosing block (bilingual captions).
            self._keep_source_stack.append(tag)
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
            self._table_stack.append({"cells": 0, "empty": 0})
        elif tag == "math":
            self.counts["math"] += 1
        elif tag in {"td", "th"}:
            self.counts["table_cells"] += 1
            if self._table_stack:
                self._table_stack[-1]["cells"] = int(self._table_stack[-1]["cells"]) + 1
            self._cell_stack.append({"tag": tag, "text": "", "in_bib": False})
        elif tag == "li":
            classes = (values.get("class") or "").lower()
            self._in_bibliography = any(
                key in classes for key in ("bib", "reference", "bibliography")
            )
            if self._in_bibliography:
                self.counts["bibliography_items"] += 1

        if tag in PROSE_TAGS or tag == "li":
            self._blocks.append(
                {
                    "tag": tag,
                    "text": "",
                    "in_bib": self._in_bibliography if tag == "li" else False,
                    "keep_source": keep_source,
                }
            )

        if tag == "link" and values.get("href"):
            self.assets.append(values["href"] or "")

    def handle_endtag(self, tag: str) -> None:
        if self._keep_source_stack and self._keep_source_stack[-1] == tag:
            self._keep_source_stack.pop()
        if tag in {"td", "th"} and self._cell_stack:
            cell = self._cell_stack.pop()
            body = str(cell["text"]).strip()
            if not body:
                self.counts["empty_table_cells"] += 1
                if self._table_stack:
                    self._table_stack[-1]["empty"] = int(self._table_stack[-1]["empty"]) + 1
        elif tag == "table" and self._table_stack:
            table = self._table_stack.pop()
            if int(table["cells"]) > 0 and int(table["empty"]) == int(table["cells"]):
                self.counts["empty_tables"] += 1
        elif tag == "li":
            self._in_bibliography = False

        if tag in PROSE_TAGS or tag == "li":
            # Close the innermost matching block (tags may nest inside <li>).
            for index in range(len(self._blocks) - 1, -1, -1):
                if self._blocks[index]["tag"] == tag:
                    block = self._blocks.pop(index)
                    self._record_block(
                        str(block["tag"]),
                        str(block["text"]),
                        bool(block["in_bib"]),
                        bool(block["keep_source"]),
                    )
                    break

    def handle_data(self, data: str) -> None:
        if not data.strip():
            return
        self.text.append(data)
        if self._cell_stack:
            self._cell_stack[-1]["text"] = str(self._cell_stack[-1]["text"]) + " " + data
        if self._keep_source_stack:
            # Deliberately kept-English text: excluded from block prose, and
            # excluded from the enclosing block as well (bilingual captions and
            # the original English subtitle sit inside a Chinese block).
            return
        if self._blocks:
            self._blocks[-1]["text"] = str(self._blocks[-1]["text"]) + " " + data

    def _record_block(
        self, tag: str, block: str, in_bibliography: bool, keep_source: bool
    ) -> None:
        body = block.strip()
        if not body:
            return
        for mark, name in RISKY_COMBINING.items():
            count = body.count(mark)
            if count:
                self.risky_marks[name] = self.risky_marks.get(name, 0) + count
        if in_bibliography or keep_source:
            return
        if tag in SOURCE_LANGUAGE_TAGS:
            return
        if not residual_english(body):
            return
        self.english_paragraphs.append(collapse(body)[:160])


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# Function words that appear in running English prose but not in a name or an
# identifier. A run of English containing several of these is a sentence.
ENGLISH_FUNCTION_WORDS = {
    "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "that", "this", "these", "those", "it", "its", "we", "our", "they",
    "their", "which", "where", "when", "while", "if", "then", "than", "so",
    "not", "no", "can", "will", "would", "should", "could", "may", "might",
    "each", "such", "has", "have", "had", "there", "here", "also", "into",
    "between", "within", "over", "under", "about", "after", "before",
}


def residual_english(block: str) -> bool:
    """Return True when a prose block looks like untranslated English prose.

    The signal is a run of consecutive English words that also contains several
    function words. An untranslated paragraph reads as a sentence and therefore
    carries function words; a translated paragraph that merely keeps an English
    name (model name, venue, paper title in parentheses) does not, even when
    that name is long. Runs of single-letter tokens are ignored so that inline
    mathematics such as "x j t i" is never reported.
    """
    tokens = re.findall(r"[A-Za-z][A-Za-z'\-]*", block)
    if len(tokens) < 3:
        return False
    meaningful = [
        token
        for token in tokens
        if token not in ALLOWED_ENGLISH_TOKENS and token.lower() not in ALLOWED_ENGLISH_PHRASES
    ]
    if len(meaningful) < 3:
        return False
    # Split on Chinese characters and digits: they end an English run.
    segments = re.split(r"[\u3400-\u4dbf\u4e00-\u9fff0-9]+", block)
    for segment in segments:
        # Further split before every capitalised token: a proper name such as
        # "IET Journal of Measurement and Control" must not accumulate function
        # words across neighbouring names.
        for name in re.split(r"(?=\b[A-Z])", segment):
            words = [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", name) if len(w) >= 2]
            if len(words) < 6:
                continue
            function_words = sum(
                1 for word in words if word.lower() in ENGLISH_FUNCTION_WORDS and word.islower()
            )
            # A sentence needs several function words; a proper name has none.
            if function_words >= 3:
                return True
    return False

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
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat residual English paragraphs and risky combining marks as errors.",
    )
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

    missing_assets = []
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

    # A table whose every cell is empty is always a defect.
    if inv.counts["empty_tables"]:
        errors.append(
            f"{inv.counts['empty_tables']} table(s) have no populated cells; "
            "the table content was likely dropped"
        )
    elif inv.counts["empty_table_cells"]:
        warnings.append(
            f"{inv.counts['empty_table_cells']} empty table cell(s) detected; "
            "verify that blanks are intentional"
        )

    # Combining marks without glyphs in CJK font stacks render as tofu boxes.
    if inv.risky_marks:
        detail = ", ".join(f"{name} x{count}" for name, count in sorted(inv.risky_marks.items()))
        message = (
            "Combining marks without a reliable glyph in CJK font stacks: "
            f"{detail}. Replace them with inline MathML (<mover>) before rendering."
        )
        (errors if args.strict else warnings).append(message)

    # Prose blocks that still read as English.
    if inv.english_paragraphs:
        message = (
            f"{len(inv.english_paragraphs)} block(s) still read as untranslated English "
            "prose"
        )
        (errors if args.strict else warnings).append(message)

    report["inventory"] = inv.counts
    report["text"] = {
        "han_characters": han,
        "latin_words": latin_words,
    }
    report["missing_assets"] = missing_assets
    report["residual_english"] = inv.english_paragraphs[:20]
    report["risky_combining_marks"] = inv.risky_marks
    if args.pdf:
        report["pdf"] = pdf_info(args.pdf.resolve())
        if not report["pdf"]["exists"]:  # type: ignore[index]
            errors.append("PDF file does not exist")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
