# Extraction and translation workflow

## Source hierarchy

Use the highest available level:

1. Original LaTeX/source archive: best for equations, tables, references, and section boundaries.
2. Structured HTML with MathML, such as an official HTML rendering: best practical fallback.
3. Tagged/digital PDF with reliable text extraction.
4. OCR for scanned pages, followed by manual equation/table reconstruction.

Do not rebuild a structured paper from raw PDF text if matching source LaTeX or structured HTML is available.

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
