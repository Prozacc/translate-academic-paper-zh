---
name: translate-academic-paper-zh
description: Translate English academic papers into Chinese while preserving scholarly structure, equations, tables, figures, captions, references, terminology, appendices, and practical page organization. Use for paper/PDF translation requests, especially when the user wants a downloadable Chinese PDF plus editable HTML or DOCX, asks to follow Paper-Translator-style workflows, or needs a layout-verified bilingual academic deliverable.
---

# Translate Academic Paper to Chinese

Produce a complete, terminology-consistent Chinese paper and verified deliverables. Optimize for fidelity and repeatability, not literal word substitution.

## Required companion skills

- Read and follow the available `pdf` skill before extracting, creating, rendering, or visually reviewing PDFs.
- Read and follow the available `doc`/`docx` skill only when the user requests Word output or when DOCX is clearly beneficial.
- Use the browser/web only to retrieve an official paper version or cited source when necessary.

## Safety and speed rules

- Never download a local translation model, model weights, or a dependency bundle larger than 100 MB unless the user explicitly requests offline translation and approves the download.
- Never send a confidential, unpublished, or private paper to a public translation service without explicit user approval.
- Prefer capabilities already available in the workspace. Cache translations so retries do not repeat completed work.
- Translate unique text segments in batches; do not make one network call per sentence.
- Preserve user files. Keep intermediate files under `work/` and user-facing files under `outputs/` unless the environment specifies other locations.

## Workflow

### 1. Identify the exact source

1. Locate the attached PDF in the current workspace or attachment path.
2. Record its filename, page count, title, authors, version/date, and checksum when possible.
3. If the attachment is inaccessible, do not silently substitute another file. Locate an official source only when title/authors match, and clearly disclose the substitution.
4. Prefer source LaTeX for arXiv papers; otherwise prefer structured HTML/MathML; use direct PDF extraction or OCR only as fallback.

Read [references/workflow.md](references/workflow.md) for the extraction decision tree and source hierarchy.

When the paper has an official LaTeX source, follow
[references/arxiv-latex-pipeline.md](references/arxiv-latex-pipeline.md): it
gives the reproducible path from the arXiv e-print to the deliverable, the
build model, and the macro configuration that `latex2mathml` needs.

### 2. Inventory before translating

Count and record:

- pages and section hierarchy;
- figures and captions;
- tables;
- display and inline equations;
- footnotes/endnotes;
- bibliography entries;
- appendices and supplementary sections.

Create a paper-specific glossary before bulk translation. Protect symbols, citations, URLs, dataset names, model names, code, units, and LaTeX/MathML tokens.

Check that the text layer actually contains the table numbers. A publisher PDF may draw a table as vector outlines, in which case extraction returns the caption and the axis labels but no data. Detect this by comparing the number of vector drawings on a page against the amount of text on it; a page with hundreds of drawings and almost no text has tables that must be read visually. Read such tables by rendering the table region at high resolution and transcribing cell by cell, then check the transcription against the numbers quoted in the surrounding prose before publishing it. Never guess a value from context.

### 3. Translate structurally

Translate titles, abstracts, headings, body paragraphs, list items, table headers/cells, figure captions, notes, and appendix prose. Preserve:

- equation markup and numbering;
- citation keys and citation order;
- table row/column relationships;
- figure/image references;
- cross-references and section numbering;
- author names, affiliations, dataset/model names, venues, and identifiers.

Use paragraph context. Apply the glossary consistently. Keep reference entries in their bibliographic language unless the user explicitly requests translated reference titles.

Use [references/terminology.md](references/terminology.md) as a starter glossary, then extend it for the paper.

Never type a vector arrow or a hat as a combining character in the body text. The characters U+20D7 and U+0302 have no glyph in most CJK font stacks, so the browser draws a replacement box instead of the mark. Express them as inline MathML instead:

```html
<math xmlns="http://www.w3.org/1998/Math/MathML"><mover accent="true"><mi>W</mi><mo>&#x2192;</mo></mover></math>
```

`scripts/validate_delivery.py` reports these characters before rendering, and `scripts/inspect_pdf.py` confirms after rendering that no replacement box was drawn.

### 4. Build the editable master

Use semantic HTML as the default editable master because it preserves MathML, tables, figures, and references better than DOCX.

1. Retain the document tree and IDs when starting from structured HTML.
2. Apply [assets/paper-zh.css](assets/paper-zh.css) or merge its rules into the document.
3. Use Chinese serif fonts for body text and sans-serif fonts for headings.
4. Use three-line academic tables where practical.
5. Keep equations centered and horizontally scrollable in HTML; scale them only when printing.
6. Use hanging indentation for references.
7. Keep image files as separate assets referenced by relative paths.

When the formulas come from LaTeX, build the master with
`scripts/build_paper.py` rather than by hand: it converts every `$...$` to
MathML, numbers the inline formulas so that later passes can refer to
them, cuts the inline formulas that are too wide (Chrome never breaks an
inline `<math>`, so a wide formula is pushed to the next line as a whole and
the short line left behind is stretched by justification), and injects the
shared stylesheet. See
[references/arxiv-latex-pipeline.md](references/arxiv-latex-pipeline.md).

Create DOCX only when requested or when the document has modest equation/table complexity. If conversion reduces fidelity, deliver HTML and state why DOCX was omitted.

### 5. Render the PDF

Render the editable master to A4 PDF with backgrounds enabled. Prefer the rendering mechanism supplied by the `pdf` skill.

- Test Paged.js only if already available and the document has no giant tables.
- If Paged.js truncates content or drops tables, use browser-native A4 printing and verify every page.
- Do not claim page-for-page equivalence when translation expansion changes pagination.

`scripts/render_pdf.py` drives headless Chrome with the browser-native A4
printer. It renders to a temporary file and moves it into place, so it never
has to delete a PDF that a preview window still holds open.

### 6. Validate

Run the source check:

```powershell
python scripts/validate_delivery.py --html <translated.html> --pdf <translated.pdf>
```

Then inspect the rendered PDF:

```powershell
python scripts/inspect_pdf.py --pdf <translated.pdf> --output-dir work/pdf-check
```

Then check the Chinese justification and the stylesheet coverage:

```powershell
python scripts/measure_cjk_stretch.py --pdf <translated.pdf>
python scripts/audit_css.py --html <translated.html> --css assets/paper-zh.css
```

`validate_delivery.py` checks the HTML source: missing assets, structure counts, empty table cells, untranslated English prose, and combining marks that have no glyph in CJK font stacks. `inspect_pdf.py` checks the rendered result: blank pages, characters drawn with a missing-glyph box, images that failed to load, and replacement characters in the text layer. It also writes every page as a PNG plus 2x2 contact sheets for visual review.

`measure_cjk_stretch.py` catches a defect that no other check sees: Chrome
justifies Chinese by stretching the characters themselves, so a line that
ends with a wide inline formula can leave its few Chinese characters more
than twice their natural width. The script measures the advance of the
neighbouring CJK glyphs in the rendered PDF. When it reports a ratio above
1.55, set that one paragraph ragged-right (`class="nojust"`) - do not change
the global justification mode, which would make every other paragraph worse.

`audit_css.py` lists the classes the document uses but the stylesheet does
not define; an unstyled class still renders, with the browser defaults.

Then render every PDF page to images, assemble contact sheets, and inspect all pages. Spot-check the title, abstract, first paragraph of each major section, all captions, table headers, appendices, and the final reference.

Use [references/quality-checklist.md](references/quality-checklist.md) as the release gate. Fix missing text, broken assets, clipping, blank pages, mojibake, inconsistent terms, and untranslated prose before delivery.

Automation does not replace reading the pages. The scripts catch structural defects; only visual review catches a formula that reads wrong, a caption attached to the wrong figure, or a table whose numbers were transcribed from the wrong column.

### 7. Package and report

Create an editable HTML ZIP:

```powershell
python scripts/package_html.py --html <translated.html> --output <editable-html.zip>
```

Deliver:

1. translated PDF;
2. editable HTML ZIP;
3. DOCX only if requested and reliable;
4. a concise limitations/provenance note.

Report source identity/version, output page count, structure counts, what was visually checked, untranslated content, substitutions, and layout deviations. Never describe machine-assisted translation as an official author translation.
