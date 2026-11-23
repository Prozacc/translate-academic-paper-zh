# Extraction and translation workflow

## Source hierarchy

Use the highest available level:

1. Original LaTeX/source archive: best for equations, tables, references, and section boundaries.
2. Structured HTML with MathML, such as an official HTML rendering: best practical fallback.
3. Tagged/digital PDF with reliable text extraction.
4. OCR for scanned pages, followed by manual equation/table reconstruction.

Do not rebuild a structured paper from raw PDF text if matching source LaTeX or structured HTML is available.

A digital PDF can still need the treatment reserved for scans. Some publishers draw tables as vector outlines: the text layer returns the caption and the axis labels but none of the cell values. This is not a scanned page and OCR is not the right answer either.

Detect it per page by comparing the number of vector drawings against the amount of text. A page carrying hundreds of drawings and almost no text has tables whose values are only available as pixels. For each such table:

1. Locate its bounding box from the horizontal and vertical rules.
2. Render the region at high resolution in two halves so that each cell stays legible.
3. Transcribe cell by cell, then cross-check against the numbers the surrounding prose quotes.
4. Record the method in the delivery note.

Never infer a value from the shape of the surrounding sentence, and never carry over a plausible-looking number that no rendering actually shows.

## Source identity

Record the title, authors, publication venue or preprint identifier, version/date, page count, and SHA-256 hash of the actual input. If replacing an inaccessible attachment with an official copy, compare title and authors and disclose the replacement in the final note.

## Content inventory

Before translation, record counts for headings, paragraphs, figures, tables, equations, references, footnotes, and appendices. Repeat the same counts after translation. Differences must be explained.

## Protected content

Replace the following with stable placeholders before translation and restore them afterward:

- LaTeX and MathML;
- inline symbols and variables;
- citations and bibliography keys;
- URLs, DOIs, e-mail addresses, and code;
- model/dataset names;
- units and numeric values;
- figure/table/section reference anchors.

Validate that every placeholder is restored exactly once.

## Translation strategy

1. Extract visible prose nodes without flattening the document tree.
2. Deduplicate identical segments.
3. Build a paper-specific glossary from the title, abstract, keywords, headings, model architecture, datasets, metrics, and repeated noun phrases.
4. Translate in batches that preserve nearby context and content type.
5. Cache source-to-target pairs in a local JSON file.
6. Apply deterministic terminology replacements after translation.
7. Review high-impact sections manually: title, abstract, introduction, method overview, contributions, conclusions, limitations, captions, and table headers.

Avoid translating isolated fragments when their meaning depends on the sentence or table context.

## Bibliography policy

Preserve author names, paper titles, venues, years, page ranges, identifiers, and ordering. Translate only surrounding labels such as “References” unless the user explicitly asks to translate bibliographic titles.

## Page organization

Preserve reading order, section hierarchy, numbering, figure/table placement near first mention, and appendix order. Page count may change because Chinese and English have different line lengths. Report this instead of forcing artificial page-for-page correspondence.

## Paper-Translator compatibility

Follow the practical principles of the Prozacc/Paper-Translator workflow: read the whole paper, create a terminology guide, build a semantic academic HTML document, preserve equations/tables, render to PDF, and report statistics and limitations. Treat any repository scripts as optional; use equivalent verified tooling when a referenced script is absent or unreliable.

## Reproducible LaTeX pipeline

When the paper has an official LaTeX source, follow
[arxiv-latex-pipeline.md](arxiv-latex-pipeline.md). It describes the build
model (translated fragments in `work/parts/`, formulas kept as LaTeX, one
shared stylesheet), the macro configuration for `latex2mathml`, the
measurement pass that decides which inline formulas must be cut so that
Chrome can break them like TeX, and the Chinese-justification check that
catches characters stretched by `text-align: justify`.

The pipeline scripts are `scripts/latex_mathml.py`, `scripts/build_paper.py`,
`scripts/measure_inline.py`, `scripts/measure_cjk_stretch.py`,
`scripts/render_pdf.py` and `scripts/audit_css.py`.
