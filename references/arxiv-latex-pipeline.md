# arXiv LaTeX pipeline

A reproducible path from an arXiv e-print to a layout-verified Chinese PDF.
Use it when the paper has an official LaTeX source: the source is a far more
faithful baseline than the typeset PDF, because it carries the exact
formulas, the exact numbering, and the exact bibliography.

## 0. Obtain the source

```bash
# The e-print tarball holds the original LaTeX.
curl -L -o src.tar.gz "https://arxiv.org/e-print/<ID>v<N>"
tar -xzf src.tar.gz -C src
```

The tarball often contains several `.tex` files plus `.bbl`, `.sty` and
figure files. Locate the main file (`\documentclass`) and read the
`\input`/`\include` graph before translating anything.

Keep the source PDF as the layout reference: the LaTeX gives the content,
the PDF gives the page geometry, the figures and the line structure.

## 1. Prepare the macro configuration

`latex2mathml` does not know the paper's custom macros. Declare them in a
small JSON file instead of patching the converter:

```json
{
  "wrappers": ["camerareadyrevisionlast", "camerareadyrevision"],
  "arg_wrappers": ["textcolor"],
  "macros": [
    ["\\\\masksub", "\\\\text{CP-MDA-Exact}"],
    ["\\\\mask", "\\\\text{CP-MDA-Nested}"],
    ["\\\\obs", "\\\\mathrm{obs}"]
  ]
}
```

- `wrappers` - macro names whose braced argument is kept verbatim.
- `arg_wrappers` - macro names that take one argument and then a braced body.
- `macros` - ordered `[regex, replacement]` pairs. **Order matters**: a
  longer macro must precede a shorter prefix of it (`\masksub` before
  `\mask`).

`scripts/macros.example.json` is a worked example. Copy it into the paper's
working directory and adjust it.

## 2. Write the translated parts

Split the translated document into `part1.html` ... `partN.html`:

- `part1.html` holds the document skeleton: `<head>`, an **empty**
  `<style></style>` block, the title block, the abstract, and the table of
  contents.
- later parts hold the translated body, appendices, and the `<!--REFS-->`
  placeholder where the bibliography goes.

Keep every formula as its original LaTeX inside `$...$` (inline) or
`$$...$$` (display). Do not hand-edit the MathML: the build step converts
it, so the LaTeX stays the single source of truth.

The stylesheet is injected by the build step, so `part1.html` must contain
exactly one empty `<style></style>` block.

## 3. Build, measure, rebuild

The first build shows how wide each inline formula is; the second build cuts
the wide ones so that Chrome can break them.

```bash
# 1. first build
python scripts/build_paper.py --parts work/parts --out outputs/Paper_zh.html \
    --css assets/paper-zh.css --macros work/macros.json --refs work/refs.json

# 2. find the inline formulas that are too wide
python scripts/measure_inline.py --html outputs/Paper_zh.html --out work/split_ids.json

# 3. rebuild with the cut list, then render
python scripts/build_paper.py --parts work/parts --out outputs/Paper_zh.html \
    --css assets/paper-zh.css --macros work/macros.json --refs work/refs.json \
    --split-ids work/split_ids.json --assets work/assets
python scripts/render_pdf.py --html outputs/Paper_zh.html --pdf outputs/Paper_zh.pdf
```

### Why the cut list exists

Chrome treats an inline `<math>` element as one atomic inline box and never
breaks it. A wide formula is therefore pushed to the next line as a whole,
and the short line left behind is stretched by `text-align: justify` - the
few Chinese characters in front of it can end up more than twice their
natural width. TeX breaks inline formulas after binary operators;
`latex_mathml.split_inline_math()` reproduces that by cutting the formula at
its top-level binary operators and separating the pieces with `<wbr>`.

`measure_inline.py` measures the formulas in the browser (the screen layout
is close enough for a width), and marks every formula wider than 30 % of the
text block.

## 4. Check the Chinese justification

```bash
python scripts/measure_cjk_stretch.py --pdf outputs/Paper_zh.pdf
```

The report gives, for every visual line, the average advance of the
neighbouring CJK glyphs divided by the font size. A ratio near 1.00 is
normal; above 1.55 the characters are visibly stretched and the line is a
defect.

**Fix the offending paragraph, not the document.** Set that one paragraph
ragged-right:

```html
<p class="nojust">请注意，此处我们假定 <math>…</math> 且 <math>…</math>。</p>
```

Changing the global justification mode makes every other paragraph worse:
`text-justify: inter-word` moves the slack into the few spaces around the
formula and leaves visible holes, and `text-justify: none` drops the
two-sided alignment of the whole document from ~28 % of the lines to ~2 %.

Do not use DOM geometry to detect this. The screen layout and the print
layout disagree, and a DOM-based detector returns zero defects on a document
that visibly has them. Measure the rendered PDF.

## 5. Validate, inspect, deliver

```bash
python scripts/validate_delivery.py --html outputs/Paper_zh.html --pdf outputs/Paper_zh.pdf --strict
python scripts/inspect_pdf.py --pdf outputs/Paper_zh.pdf --output-dir work/pdf-check
python scripts/audit_css.py --html outputs/Paper_zh.html --css assets/paper-zh.css
python scripts/package_html.py --html outputs/Paper_zh.html --output outputs/Paper_zh_editable.zip
```

`audit_css.py` lists the classes the document uses but the stylesheet does
not define. An unstyled class still renders, with the browser defaults,
which is easy to miss in a long document.

## 6. Escape the text before you mark it up

Reference entries carry italics for the venue or the book title. Escape the
text **first** and insert the markup afterwards:

```python
text = html.escape(text, quote=False)
text = re.sub(r"\[\[I\]\](.*?)\[\[/I\]\]", r"<em>\1</em>", text)
```

Escaping after the substitution turns the markup into visible text: the
reader sees `<em>Proceedings of the …</em>` instead of an italicised title.
`scripts/build_paper.py` already does it in the right order.

## Files produced

```
work/
  parts/part1.html … partN.html   translated fragments, formulas in LaTeX
  macros.json                     macro configuration
  refs.json                       bibliography records
  split_ids.json                  inline formulas that must be cut
  assets/*.png                    figures
outputs/
  Paper_zh.html                   the editable master
  Paper_zh.pdf                    the rendered deliverable
  Paper_zh_editable.zip           HTML + assets
```
