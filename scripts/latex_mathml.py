# -*- coding: utf-8 -*-
"""LaTeX -> MathML, with paper-specific macros supplied by a JSON config.

The engine in this module is paper-agnostic.  Every macro that belongs to a
particular paper (blind-submission wrappers, notation shorthands such as
``\\obs``, custom operator names) is declared in a small JSON file and loaded
at run time, so the same engine serves every paper.

Config format::

    {
      "wrappers": ["camerareadyrevisionlast", "camerareadyrevision"],
      "arg_wrappers": ["textcolor"],
      "macros": [["\\\\obs", "\\\\mathrm{obs}"], ["\\\\ind", "\\\\perp\\\\!\\\\!\\\\!\\\\perp"]]
    }

``wrappers``        macro names whose single braced argument is kept verbatim
                    (``\\foo{X}`` -> ``X``)
``arg_wrappers``    macro names that take one argument and then a braced body
                    (``\\textcolor{red}{X}`` -> ``X``)
``macros``          ordered list of ``[regex, replacement]`` pairs applied to
                    the formula before conversion.  Order matters: a longer
                    macro must be listed before a shorter prefix of it.

See ``scripts/macros.example.json`` for a worked example.
"""
import json
import re
from xml.etree import ElementTree as ET

try:
    import latex2mathml.converter as _C
except ImportError:  # pragma: no cover - dependency check
    raise SystemExit(
        'latex2mathml is required: pip install latex2mathml')

_MATHML_NS = 'http://www.w3.org/1998/Math/MathML'
_N = '{%s}' % _MATHML_NS
ET.register_namespace('', _MATHML_NS)

# Transformations that hold for every paper and are therefore built in.
_GENERIC_MACROS = [
    (r'\\operatorname\{([a-zA-Z]+)\}', r'\\mathrm{\1}'),
    # \big / \Big are size commands; \bigcup, \bigcap ... are different macros.
    (r'\\Bigg(?![a-zA-Z])', ''),
    (r'\\bigg(?![a-zA-Z])', ''),
    (r'\\Big(?![a-zA-Z])', ''),
    (r'\\big(?![a-zA-Z])', ''),
    (r'\\displaystyle', ''),
]

DEFAULT_CONFIG = {'wrappers': [], 'arg_wrappers': [], 'macros': []}


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def load_config(path=None):
    """Read a macro configuration file; an absent file yields the defaults."""
    cfg = {'wrappers': [], 'arg_wrappers': [], 'macros': []}
    if not path:
        return cfg
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    cfg['wrappers'] = list(data.get('wrappers', []))
    cfg['arg_wrappers'] = list(data.get('arg_wrappers', []))
    cfg['macros'] = [tuple(pair) for pair in data.get('macros', [])]
    return cfg


def _strip_wrappers(s, plain=(), arg=()):
    """Drop wrapper macros but keep the content they enclose."""
    if not plain and not arg:
        return s
    plain_re = '|'.join(re.escape(name) for name in plain)
    arg_re = '|'.join(re.escape(name) for name in arg)
    head = r'\\(?:(?:%s)|(?:%s)\{[a-zA-Z]+\})' % (plain_re, arg_re) if (plain_re or arg_re) else r'(?!)'
    pattern = re.compile(head + r'\{')
    out = []
    i = 0
    while i < len(s):
        m = pattern.match(s, i)
        if m:
            depth = 1
            j = m.end()
            while j < len(s) and depth:
                if s[j] == '{':
                    depth += 1
                elif s[j] == '}':
                    depth -= 1
                j += 1
            out.append(s[m.end():j - 1])
            i = j
        else:
            out.append(s[i])
            i += 1
    return ''.join(out)


def _fix_resizebox(s):
    # \resizebox{\textwidth}{!}{$...$}  ->  ...
    s = re.sub(r'\\resizebox\{[^}]*\}\{[^}]*\}\{\$(.*?)\$\}', r'\1', s, flags=re.S)
    s = re.sub(r'\\resizebox\{[^}]*\}\{[^}]*\}\{(.*?)\}', r'\1', s, flags=re.S)
    return s


def prep(latex, config=None):
    """Normalise a LaTeX formula so that latex2mathml can convert it."""
    cfg = config or DEFAULT_CONFIG
    s = latex.strip()
    s = _strip_wrappers(s, cfg.get('wrappers', ()), cfg.get('arg_wrappers', ()))
    s = _fix_resizebox(s)
    # latex2mathml has no `aligned`; `align*` produces the same mtable.
    s = s.replace('\\begin{aligned}', '\\begin{align*}').replace('\\end{aligned}', '\\end{align*}')
    s = s.replace('\\begin{gathered}', '\\begin{align*}').replace('\\end{gathered}', '\\end{align*}')
    # `align` makes latex2mathml append a per-row "(1)", "(2)" ... column.
    # The paper's own numbering is carried by the .eqno spans instead.
    s = s.replace('\\begin{align}', '\\begin{align*}').replace('\\end{align}', '\\end{align*}')
    # LaTeX bookkeeping that latex2mathml does not know.
    s = re.sub(r'\\label\{[^}]*\}', '', s)
    s = re.sub(r'\\nonumber|\\notag|\\notag\*', '', s)
    # \limits only controls limit placement, which the mtable already handles.
    s = re.sub(r'\\limits(?![a-zA-Z])', '', s)
    # Inside a multi-row environment each cell must balance its own delimiters.
    if '\\begin{align*}' in s or '\\begin{align}' in s:
        s = re.sub(r'\\left\s*\.', '', s)
        s = re.sub(r'\\right\s*\.', '', s)
        s = re.sub(r'\\left\s*\{', r'\\{', s)
        s = re.sub(r'\\right\s*\}', r'\\}', s)
        s = re.sub(r'\\left\s*\[', '[', s)
        s = re.sub(r'\\right\s*\]', ']', s)
        s = re.sub(r'\\left\s*\(', '(', s)
        s = re.sub(r'\\right\s*\)', ')', s)
    for pat, rep in cfg.get('macros', []) + _GENERIC_MACROS:
        s = re.sub(pat, rep, s)
    # \text{...} inside math is fine; protect \NA
    s = s.replace('\\>', '>').replace('<\\', '<')
    return s


def to_mathml(latex, display=False, inline_id=None, config=None):
    """Convert one LaTeX formula to a MathML string."""
    s = prep(latex, config)
    try:
        xml = _C.convert(s)
    except Exception:
        return '<span class="matherr">[%s]</span>' % (latex[:60],)
    if display:
        xml = xml.replace('display="inline"', 'display="block"')
    elif inline_id:
        xml = xml.replace('<math ', '<math id="%s" ' % inline_id, 1)
    return xml


# --------------------------------------------------------------------------
# Inline line breaking
# --------------------------------------------------------------------------
# Chrome does not break inline MathML: a formula is one atomic inline box, so
# a long inline formula is pushed to the next line as a whole and the short
# line left behind gets stretched by `text-align: justify`.  TeX breaks inline
# formulas after binary operators; we reproduce that by cutting the formula at
# its top-level binary operators and marking every cut with a zero-width
# break opportunity.

_BREAK_OPS = {
    '=', '≤', '≥', '<', '>', '≈', '≲', '≳', '±', '+', '−', '–', '-', '∗', '×',
}

# Operators that must not be separated from the operand on their left.
_NO_BREAK_BEFORE = {',', ';', '.', ')', ']', '}', '|', ':'}


def _top_row(root):
    """Return (mrow element, list of its children) for a <math> root."""
    kids = list(root)
    if len(kids) == 1 and kids[0].tag == _N + 'mrow':
        return kids[0], list(kids[0])
    return root, kids


def _cut_points(children):
    """Indices at which the formula may be broken (after the given child)."""
    cuts = []
    for i, node in enumerate(children):
        if node.tag != _N + 'mo':
            continue
        text = ''.join(node.itertext()).strip()
        if text not in _BREAK_OPS:
            continue
        # Do not break right before a closing delimiter or a comma.
        if i + 1 < len(children):
            nxt = children[i + 1]
            if nxt.tag == _N + 'mo':
                nxt_text = ''.join(nxt.itertext()).strip()
                if nxt_text in _NO_BREAK_BEFORE:
                    continue
        if 0 < i < len(children) - 1:
            cuts.append(i + 1)
    return cuts


def split_inline_math(mathml, piece_ids=None):
    """Split an inline MathML formula at its top-level binary operators.

    Chrome only honours break opportunities *between* inline boxes, and a
    <math> element is one atomic box, so a break point inside the formula is
    ignored.  The formula is therefore turned into several sibling <math>
    elements separated by <wbr>, which is exactly how TeX breaks an inline
    formula: at a binary operator.

    The operator stays with the piece on its left, so the spacing around it
    is unchanged - verified glyph by glyph against the unsplit formula.
    """
    if '<math' not in mathml:
        return mathml
    try:
        root = ET.fromstring(mathml)
    except ET.ParseError:
        return mathml

    row, children = _top_row(root)
    cuts = _cut_points(children)
    if not cuts:
        return mathml

    pieces = []
    prev = 0
    for c in cuts:
        pieces.append(children[prev:c])
        prev = c
    pieces.append(children[prev:])
    pieces = [p for p in pieces if p]

    if len(pieces) < 2:
        return mathml

    out = []
    for i, piece in enumerate(pieces):
        for child in list(row):
            row.remove(child)
        for child in piece:
            row.append(child)
        frag = ET.tostring(root, encoding='unicode')
        if piece_ids is not None and i < len(piece_ids):
            # Give every piece its own id.
            frag = re.sub(r'\sid="[^"]*"', '', frag, count=1)
            frag = frag.replace('<math ', '<math id="%s" ' % piece_ids[i], 1)
        out.append(frag)
        if i < len(pieces) - 1:
            out.append('<wbr>')
    return ''.join(out)


if __name__ == '__main__':
    import sys
    cfg = load_config(sys.argv[1] if len(sys.argv) > 1 else None)
    tests = [
        r'\mathds{P}\left( Y \in \widehat{C}_\alpha (X) \right) \geq 1 - \alpha.',
        r'\overset{(d)}{=}',
        r'\hat{q}_{\frac{\alpha}{2}}(\cdot) \leftarrow \mathcal{QR}\left(\left\{\left( x_{\text{imp}}^{(k)}, y^{(k)} \right), k \in \rm{Tr}\right\}, \alpha/2 \right)',
        r'\rho_\beta(u) = \beta|u|\mathds{1}_{\{u \geq 0\}} + (1-\beta)|u|\mathds{1}_{\{u \leq 0\}}',
        r'\operatorname{median}',
        r'\blacklozenge',
        r'\perp\!\!\!\!\perp',
    ]
    for t in tests:
        print('>>>', t[:70])
        print(to_mathml(t, config=cfg))
        print()
