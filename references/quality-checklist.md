# Release checklist

Do not deliver until all applicable checks pass.

## Completeness

- Title, authors, affiliations, abstract, keywords, all numbered sections, conclusion, acknowledgments, references, appendices, footnotes, and supplementary prose are present.
- Figure, table, equation, section, and citation numbering matches the source.
- Source and translated structure counts agree or every difference is explained.
- The final reference and final appendix paragraph are present.

## Translation

- Title and abstract are fluent Chinese, not word-by-word output.
- Terminology is consistent across prose, captions, and tables.
- No general phrase is mistranslated as an acronym expansion.
- Negations, comparative claims, percentages, and units match the source.
- Model names, dataset names, variables, and citations remain unchanged.
- Residual English prose is intentional and documented.

## Equations and tables

- Math markup is preserved; subscripts, superscripts, Greek letters, operators, and equation numbers are correct.
- Every table has the expected rows and columns.
- Table values were read from a reliable source. If the PDF drew the table as vector outlines, every cell was transcribed from a high-resolution rendering and checked against the numbers quoted in the prose.
- Headers and notes are translated.
- Multi-level table headers use a `rowspan` that matches the number of header levels, so metric columns stay aligned under their group.
- Wide tables are legible; if reduced or split across pages, the limitation is disclosed.

## Figures

- Every image loads and has nonzero dimensions.
- Captions are translated and linked to the correct figure.
- Embedded labels inside source images are either translated by careful redrawing or explicitly identified as retained English.

## Layout and PDF

- PDF opens without a password and has the expected number of pages.
- Every page has been rendered and visually inspected.
- No blank page, clipped text, overlapping blocks, missing glyphs, broken image, or mojibake remains.
- No character is drawn with a missing-glyph box. Vector arrows and hats are inline MathML, not raw combining characters.
- No line has its Chinese characters stretched by justification. `scripts/measure_cjk_stretch.py` reports no line above a ratio of 1.55; such a paragraph is set ragged-right with `class="nojust"` instead of changing the global justification mode.
- Headings do not appear alone at a page bottom when avoidable.
- References use hanging indentation and URLs/DOIs remain usable.
- No markup leaks into the rendered text: a reference entry must not display a literal `<em>` tag, and no page shows raw HTML entities.

## Automated checks

- `scripts/validate_delivery.py --html <file> --pdf <file>` reports no errors.
- `scripts/inspect_pdf.py --pdf <file> --output-dir <dir>` reports no errors and no blank pages.
- `scripts/measure_cjk_stretch.py --pdf <file>` reports no stretched line.
- `scripts/audit_css.py --html <file> --css assets/paper-zh.css` reports no class that the stylesheet leaves unstyled.
- The page images and contact sheets produced by `inspect_pdf.py` have been reviewed.

## Delivery note

- State the exact source/version and whether an official substitute was used.
- State PDF page count and editable-source format.
- State machine assistance and manual-review scope.
- List any unmodified figure-internal English, OCR uncertainty, or layout deviation.
