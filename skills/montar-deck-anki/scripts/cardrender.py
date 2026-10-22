#!/usr/bin/env python3
"""cardrender — Markdown de card → HTML pronto para campo do Anki.

Suporta:
  * Markdown (CommonMark + tabelas), HTML cru, ==marca-texto==, <kbd>
  * Cloze {{c1::...}} em texto e DENTRO de blocos de código (marcadores ficam
    só em fronteiras de <span>; { } : viram entidades para não quebrar o cloze)
  * Matemática MathJax: \\( ... \\) e \\[ ... \\] (preservada intacta)
  * Blocos cercados (```):
      <linguagem> {hl=2,4-5 err=3 ok=6 dim=7-9 title="x.py" lines=no wrap}
      out | output | console | text     saída de programa (sem realce)
      dot | graphviz {hl=A,B caption="..."}   → SVG inline temático
      tree {caption=...}                árvore binária: 8(3(1,6*),10(,14?))
      schema                            esquema relacional (PK sublinhada)
      mermaid {caption=...}             → SVG claro + escuro (precisa mmdc+Chromium)
      svg                               SVG escrito à mão (sanitizado)
  * Cores semânticas em dot/svg/mermaid: @ink @accent @muted @mark @alert @ok
    @panel @accent-soft (viram variáveis CSS → funcionam no tema claro e escuro)
  * Imagens locais ![alt](arquivo.png) → copiadas para a mídia com nome por hash

Uso como biblioteca (build_deck.py) ou CLI de teste:
  python3 cardrender.py arquivo.md > saida.html
"""
from __future__ import annotations

import glob
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from markdown_it import MarkdownIt
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.token import STANDARD_TYPES
from pygments.util import ClassNotFound
from lxml import etree

SVG_NS = "http://www.w3.org/2000/svg"

# ---------------------------------------------------------------------------
# Paleta semântica: nomes → cor-placeholder (Graphviz não aceita var()) → CSS
# ---------------------------------------------------------------------------
PALETTE = {
    "ink": ("#010101", "currentColor"),
    "accent": ("#020202", "var(--accent)"),
    "muted": ("#030303", "var(--muted)"),
    "mark": ("#040404", "var(--mark)"),
    "paper": ("#050505", "var(--paper)"),
    "alert": ("#060606", "var(--alert)"),
    "ok": ("#070707", "var(--ok)"),
    "panel": ("#080808", "var(--panel)"),
    "accent-soft": ("#090909", "var(--accent-soft)"),
    "alert-soft": ("#0a0a0a", "var(--alert-soft)"),
    "ok-soft": ("#0b0b0b", "var(--ok-soft)"),
}
PLACEHOLDER_TO_CSS = {ph.lower(): css for ph, css in PALETTE.values()}
_COLOR_NAME_RE = re.compile(r"@(accent-soft|alert-soft|ok-soft|ink|accent|muted|mark|paper|alert|ok|panel)\b")

CODE_PLAIN = {"out", "output", "console", "text", "plain", "txt", "stdout"}
DIAGRAM_LANGS = {"dot", "graphviz", "tree", "heap", "schema", "mermaid", "svg"}

PUA_CLZ_O, PUA_CLZ_C = "", ""
PUA_MATH_O, PUA_MATH_C = "", ""


class RenderError(Exception):
    pass


# ---------------------------------------------------------------------------
# utilidades
# ---------------------------------------------------------------------------
def _sha(s: str | bytes, n: int = 10) -> str:
    if isinstance(s, str):
        s = s.encode()
    return hashlib.sha256(s).hexdigest()[:n]


def esc_cloze_safe(text: str) -> str:
    """Escapa HTML e neutraliza { } : (o parser de cloze do Anki age antes do HTML)."""
    return (html.escape(text, quote=False)
            .replace("{", "&#123;").replace("}", "&#125;").replace(":", "&#58;"))


def _encode_text_outside_tags(fragment: str) -> str:
    """Aplica &#123; &#125; &#58; só no texto (não dentro de <tags>)."""
    parts = re.split(r"(<[^>]+>)", fragment)
    for i, p in enumerate(parts):
        if p and not p.startswith("<"):
            parts[i] = p.replace("{", "&#123;").replace("}", "&#125;").replace(":", "&#58;")
    return "".join(parts)


def parse_ranges(spec: str | None) -> set[int]:
    out: set[int] = set()
    if not spec:
        return out
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def parse_info(info: str) -> tuple[str, dict]:
    """'python {hl=2-3 title="a b.py" wrap}' → ('python', {...})"""
    info = (info or "").strip()
    m = re.match(r"^([^\s{]*)\s*(?:\{(.*)\})?\s*$", info, re.S)
    if not m:
        return info, {}
    lang = m.group(1).lower()
    opts: dict = {}
    for km in re.finditer(r'([\w-]+)(?:=("([^"]*)"|\'([^\']*)\'|[^\s]+))?', m.group(2) or ""):
        k = km.group(1)
        if km.group(2) is None:
            opts[k] = True
        else:
            opts[k] = km.group(3) if km.group(3) is not None else (km.group(4) if km.group(4) is not None else km.group(2))
    return lang, opts


def _truthy(v) -> bool:
    return str(v).lower() not in {"no", "false", "0", "off", "nao", "não"}


# ---------------------------------------------------------------------------
# cloze: extração balanceada
# ---------------------------------------------------------------------------
_CLOZE_OPEN = re.compile(r"\{\{c(\d+)::")


def extract_clozes(text: str) -> tuple[str, list[tuple[int, str]]]:
    """Troca cada {{cN::conteúdo}} por um marcador privado. Conteúdo pode conter
    chaves balanceadas ({"a": {1}}). Retorna (texto, [(N, conteúdo), ...])."""
    out, found, i = [], [], 0
    while True:
        m = _CLOZE_OPEN.search(text, i)
        if not m:
            out.append(text[i:])
            break
        out.append(text[i:m.start()])
        j, depth = m.end(), 0
        while j < len(text):
            if text.startswith("}}", j) and depth == 0:
                break
            ch = text[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            j += 1
        else:
            raise RenderError(f"cloze sem fechamento: {text[m.start():m.start()+40]!r}")
        content = text[m.end():j]
        found.append((int(m.group(1)), content))
        out.append(f"{PUA_CLZ_O}{len(found)-1}{PUA_CLZ_C}")
        i = j + 2
    return "".join(out), found


_MATH_RE = re.compile(r"\\\((.+?)\\\)|\\\[(.+?)\\\]", re.S)


def protect_math(text: str, store: list[str]) -> str:
    def sub(m):
        store.append(m.group(0))
        return f"{PUA_MATH_O}{len(store)-1}{PUA_MATH_C}"
    return _MATH_RE.sub(sub, text)


def restore_math(text: str, store: list[str], escape: bool = False) -> str:
    f = (lambda x: html.escape(x, quote=False)) if escape else (lambda x: x)
    return re.sub(f"{PUA_MATH_O}(\\d+){PUA_MATH_C}", lambda m: f(store[int(m.group(1))]), text)


# ---------------------------------------------------------------------------
# ferramentas externas
# ---------------------------------------------------------------------------
def find_chromium() -> str | None:
    env = os.environ.get("CHROMIUM_PATH")
    if env and os.path.exists(env):
        return env
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        p = shutil.which(name)
        if p:
            return p
    pats = ["/opt/pw-browsers/chromium-*/chrome-linux*/chrome",
            os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")]
    for pat in pats:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def find_mmdc() -> str | None:
    env = os.environ.get("MMDC")
    if env and os.path.exists(env):
        return env
    p = shutil.which("mmdc")
    if p:
        return p
    for cand in ("/opt/npm-tools/node_modules/.bin/mmdc", os.path.expanduser("~/.npm-global/bin/mmdc")):
        if os.path.exists(cand):
            return cand
    return None


# ---------------------------------------------------------------------------
# SVG: limpeza e tema
# ---------------------------------------------------------------------------
def _svg_parse(svg_text: str) -> etree._Element:
    svg_text = re.sub(r"<\?xml[^>]*\?>", "", svg_text)
    svg_text = re.sub(r"<!DOCTYPE[^>]*>", "", svg_text, flags=re.S)
    parser = etree.XMLParser(remove_comments=True, remove_blank_text=False, resolve_entities=False, no_network=True)
    try:
        root = etree.fromstring(svg_text.strip().encode(), parser)
    except etree.XMLSyntaxError as e:
        raise RenderError(f"SVG inválido: {e}") from e
    if etree.QName(root).localname != "svg":
        raise RenderError("o bloco svg precisa ter <svg> como raiz")
    return root


def _svg_sanitize(root: etree._Element) -> None:
    for el in list(root.iter()):
        if not isinstance(el.tag, str):
            continue
        name = etree.QName(el).localname
        if name in {"script", "foreignObject", "iframe"}:
            el.getparent().remove(el)
            continue
        for attr in list(el.attrib):
            a = attr.lower()
            if a.startswith("on") or (a.endswith("href") and el.attrib[attr].strip().lower().startswith("javascript:")):
                del el.attrib[attr]


def _svg_theme(root: etree._Element) -> None:
    """Placeholders → currentColor/var(--x). Atributos com var() vão para style."""
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        style_add = []
        for attr in list(el.attrib):
            val = el.attrib[attr]
            low = val.lower()
            if low in PLACEHOLDER_TO_CSS and attr in {"fill", "stroke", "stop-color", "color"}:
                css = PLACEHOLDER_TO_CSS[low]
                if css.startswith("var("):
                    style_add.append(f"{attr}:{css}")
                    del el.attrib[attr]
                else:
                    el.attrib[attr] = css
            elif attr == "style":
                el.attrib["style"] = re.sub(r"#0[0-9a-b]0[0-9a-b]0[0-9a-b]",
                                            lambda m: PLACEHOLDER_TO_CSS.get(m.group(0).lower(), m.group(0)), val, flags=re.I)
            elif attr in {"fill", "stroke"} and low in {"black", "#000000", "#000"}:
                el.attrib[attr] = "currentColor"
            elif attr == "fill" and low in {"white", "#ffffff", "#fff"} and etree.QName(el).localname in {"polygon", "rect", "ellipse", "path", "circle"}:
                style_add.append("fill:var(--paper)")
                del el.attrib[attr]
        if style_add:
            prev = el.attrib.get("style", "")
            el.attrib["style"] = (prev + ";" if prev else "") + ";".join(style_add)


def _svg_finish(root: etree._Element, id_prefix: str, max_width: str | None = None) -> str:
    # dimensões responsivas
    w, h = root.attrib.get("width"), root.attrib.get("height")
    if "viewBox" not in root.attrib and w and h:
        num = lambda s: float(re.sub(r"[^\d.]", "", s) or 0)
        root.attrib["viewBox"] = f"0 0 {num(w):g} {num(h):g}"
    natural_w = None
    if w:
        try:
            val = float(re.sub(r"[^\d.]", "", w))
            natural_w = val * (4 / 3 if w.endswith("pt") else 1)
        except ValueError:
            pass
    for a in ("width", "height"):
        root.attrib.pop(a, None)
    style = ["max-width:100%", "height:auto"]
    if max_width:
        style.append(f"width:{max_width}")
    elif natural_w:
        style.append(f"width:{natural_w:.0f}px")
    root.attrib["style"] = ";".join(style)
    root.attrib["role"] = "img"
    # ids únicos (vários SVGs no mesmo card)
    ids = {}
    for el in root.iter():
        if isinstance(el.tag, str) and "id" in el.attrib:
            new = f"{id_prefix}-{el.attrib['id']}"
            ids[el.attrib["id"]] = new
            el.attrib["id"] = new
    out = etree.tostring(root, encoding="unicode")
    for old, new in ids.items():
        out = out.replace(f"url(#{old})", f"url(#{new})").replace(f'href="#{old}"', f'href="#{new}"')
    out = re.sub(r'\sxmlns:xlink="[^"]*"', "", out) if "xlink:" not in out.replace('xmlns:xlink', '') else out
    return out


def _svg_highlight_nodes(root: etree._Element, names: set[str]) -> None:
    if not names:
        return
    for g in root.iter(f"{{{SVG_NS}}}g"):
        cls = g.attrib.get("class", "")
        if "node" not in cls.split() and "edge" not in cls.split() and "data-occ" not in g.attrib:
            continue
        if _group_name(g) & names:
            g.attrib["class"] = (cls + " hl").strip()


def _group_name(g) -> set[str]:
    names = set()
    t = g.find(f"{{{SVG_NS}}}title")
    if t is not None and t.text:
        names.add(t.text.strip())
    if "data-occ" in g.attrib:
        names.add(g.attrib["data-occ"].strip())
    texts = [x.strip() for x in g.itertext() if x.strip() and (t is None or x != t.text)]
    if texts:
        names.add(" ".join(texts))
        names.update(texts)
    return names


def _svg_occlude(root: etree._Element, target: str, mode: str) -> None:
    hit = None
    for g in root.iter(f"{{{SVG_NS}}}g"):
        cls = g.attrib.get("class", "").split()
        if ("node" in cls or "data-occ" in g.attrib) and target in _group_name(g):
            hit = g
            break
    if hit is None:
        raise RenderError(f"alvo de oclusão não encontrado no diagrama: {target!r}")
    hit.attrib["class"] = (hit.attrib.get("class", "") + (" occ-hide" if mode == "front" else " occ-show")).strip()
    if mode == "front":
        texts = list(hit.iter(f"{{{SVG_NS}}}text"))
        for i, t in enumerate(texts):
            if i == 0:
                for ch in list(t):
                    t.remove(ch)
                t.text = "?"
            else:
                t.getparent().remove(t)
        tt = hit.find(f"{{{SVG_NS}}}title")
        if tt is not None:
            tt.text = "?"


# ---------------------------------------------------------------------------
# renderizador
# ---------------------------------------------------------------------------
@dataclass
class Renderer:
    base_dir: Path = field(default_factory=Path.cwd)     # p/ resolver imagens relativas
    media_out: Path | None = None                         # onde copiar imagens
    cache_dir: Path = field(default_factory=lambda: Path(tempfile.gettempdir()) / "cardrender-cache")
    media_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    _seq: int = 0

    def __post_init__(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.md = MarkdownIt("commonmark", {"html": True, "breaks": False}).enable("table").enable("strikethrough")
        self.md.renderer.rules["fence"] = self._render_fence
        self.md.renderer.rules["code_block"] = self._render_code_block
        self.md.renderer.rules["table_open"] = lambda *a: '<div class="tbl"><table>\n'
        self.md.renderer.rules["table_close"] = lambda *a: "</table></div>\n"
        self.md.renderer.rules["image"] = self._render_image
        self._clozes: list[tuple[int, str]] = []
        self._math: list[str] = []
        self._occl: tuple[str, str] | None = None   # (alvo, modo) durante oclusão
        self._dg_extra_class = ""

    # ---- API ------------------------------------------------------------
    def render(self, text: str | None, *, cloze_ok: bool = False) -> str:
        if not text:
            return ""
        text = str(text).replace("\r\n", "\n")
        body, clozes = extract_clozes(text)
        if clozes and not cloze_ok:
            raise RenderError("sintaxe {{cN::...}} só é permitida em notas cloze (campo text)")
        self._clozes = clozes
        math: list[str] = []
        self._math = math
        body = protect_math(body, math)
        body = apply_marks(body)
        out = self.md.render(body)
        out = self._restore_clozes(out, math)
        out = restore_math(out, math, escape=True)
        self._clozes = []
        self._math = []
        return out.strip()

    def render_inline(self, text: str | None) -> str:
        if not text:
            return ""
        math: list[str] = []
        t = apply_marks(protect_math(str(text), math))
        return restore_math(self.md.renderInline(t), math, escape=True)

    def render_occlusion(self, diagram_md: str, target: str, mode: str, extra_class: str = "") -> str:
        self._occl = (target, mode)
        self._dg_extra_class = extra_class
        try:
            return self.render(diagram_md)
        finally:
            self._occl = None
            self._dg_extra_class = ""

    # ---- clozes ---------------------------------------------------------
    def _restore_clozes(self, out: str, math: list[str]) -> str:
        def repl(m):
            idx = int(m.group(1))
            n, content = self._clozes[idx]
            before = out[:m.start()]
            in_code = before.count("<code") > before.count("</code>")
            if in_code:
                inner = esc_cloze_safe(content)
            else:
                inner = _encode_text_outside_tags(self.render_inline(content))
            return f"{{{{c{n}::{inner}}}}}"
        return re.sub(f"{PUA_CLZ_O}(\\d+){PUA_CLZ_C}", repl, out)

    # ---- imagens --------------------------------------------------------
    def _render_image(self, tokens, idx, options, env):
        tok = tokens[idx]
        src = tok.attrGet("src") or ""
        alt = html.escape("".join(c.content for c in (tok.children or [])), quote=True)
        if re.match(r"^(https?:|data:)", src):
            self.warnings.append(f"imagem remota não funciona offline no AnkiDroid: {src[:60]}")
            return f'<img src="{html.escape(src, quote=True)}" alt="{alt}">'
        p = (self.base_dir / src).resolve()
        if not p.exists():
            raise RenderError(f"imagem não encontrada: {src}")
        data = p.read_bytes()
        name = f"cc1-img-{_sha(data, 12)}{p.suffix.lower()}"
        if self.media_out:
            self.media_out.mkdir(parents=True, exist_ok=True)
            dst = self.media_out / name
            if not dst.exists():
                dst.write_bytes(data)
            if str(dst) not in self.media_files:
                self.media_files.append(str(dst))
        return f'<img src="{name}" alt="{alt}">'

    # ---- blocos ---------------------------------------------------------
    def _render_code_block(self, tokens, idx, options, env):
        return self._code_html(restore_math(tokens[idx].content.rstrip("\n"), self._math), "text", {})

    def _render_fence(self, tokens, idx, options, env):
        tok = tokens[idx]
        lang, opts = parse_info(tok.info)
        content = tok.content.rstrip("\n")
        if lang in DIAGRAM_LANGS:
            if PUA_CLZ_O in content:
                raise RenderError(f"cloze dentro de bloco '{lang}' não é suportado; use oclusão")
            content = restore_math(content, self._math)
            return self._diagram_html(lang, content, opts)
        content = restore_math(content, self._math)
        return self._code_html(content, lang or "text", opts)

    # código com realce, linhas e clozes
    def _code_html(self, content: str, lang: str, opts: dict) -> str:
        plain, spans = self._unpack_clozes_in_code(content)
        plain_lang = lang in CODE_PLAIN
        try:
            lexer = TextLexer(ensurenl=False, stripnl=False) if plain_lang else get_lexer_by_name(lang, ensurenl=False, stripnl=False)
        except ClassNotFound:
            self.warnings.append(f"linguagem desconhecida no Pygments: {lang!r} (sem realce)")
            lexer = TextLexer(ensurenl=False, stripnl=False)
        lines_total = plain.count("\n") + 1
        show_ln = _truthy(opts.get("lines", "yes")) if "lines" in opts else (lines_total > 3 and not plain_lang)
        marks = {k: parse_ranges(opts.get(k)) for k in ("hl", "err", "ok", "dim")}
        if opts.get("focus"):
            focus = parse_ranges(opts["focus"])
            marks["dim"] |= set(range(1, lines_total + 1)) - focus

        opens = {s: n for s, e, n in spans}
        closes = {e for s, e, n in spans}
        cuts = sorted(set(opens) | closes)
        for s, e, n in spans:
            if "\n" in plain[s:e]:
                raise RenderError("um cloze dentro de código não pode atravessar linhas")

        lines: list[list[str]] = [[]]
        pos = 0
        for ttype, val in lexer.get_tokens(plain):
            t = ttype
            while t not in STANDARD_TYPES and t.parent is not None:
                t = t.parent
            cls = STANDARD_TYPES.get(t, "")
            start, end = pos, pos + len(val)
            pts = [start] + [c for c in cuts if start < c < end] + [end]
            for a, b in zip(pts, pts[1:]):
                if a in closes:
                    lines[-1].append("}}")
                    closes = closes - {a}
                if a in opens:
                    lines[-1].append(f"{{{{c{opens.pop(a)}::")
                piece = val[a - start:b - start]
                segs = piece.split("\n")
                for k, seg in enumerate(segs):
                    if k > 0:
                        lines.append([])
                    if seg:
                        e = esc_cloze_safe(seg)
                        lines[-1].append(f'<span class="{cls}">{e}</span>' if cls else e)
            pos = end
        if pos in closes:
            lines[-1].append("}}")
        while len(lines) > 1 and not lines[-1]:
            lines.pop()

        html_lines = []
        for i, parts in enumerate(lines, start=1):
            cl = ["line"] + [k for k in ("hl", "err", "ok", "dim") if i in marks[k]]
            ln = f'<span class="ln">{i}</span>' if show_ln else ""
            html_lines.append(f'<span class="{" ".join(cl)}">{ln}{"".join(parts)}</span>')
        classes = ["code"] + (["out"] if plain_lang else []) + (["wrap"] if opts.get("wrap") else [])
        cap = f'<figcaption>{html.escape(str(opts["title"]))}</figcaption>' if opts.get("title") else ""
        lang_attr = html.escape(lang, quote=True)
        return (f'<figure class="{" ".join(classes)}" data-lang="{lang_attr}">{cap}'
                f'<pre><code>{chr(10).join(html_lines)}</code></pre></figure>\n')

    def _unpack_clozes_in_code(self, content: str) -> tuple[str, list[tuple[int, int, int]]]:
        """Substitui marcadores privados pelo conteúdo e devolve offsets."""
        out, spans, i = [], [], 0
        pattern = re.compile(f"{PUA_CLZ_O}(\\d+){PUA_CLZ_C}")
        length = 0
        for m in pattern.finditer(content):
            seg = content[i:m.start()]
            out.append(seg)
            length += len(seg)
            n, c = self._clozes[int(m.group(1))]
            spans.append((length, length + len(c), n))
            out.append(c)
            length += len(c)
            i = m.end()
        out.append(content[i:])
        return "".join(out), spans

    # diagramas
    def _diagram_html(self, lang: str, content: str, opts: dict) -> str:
        self._seq += 1
        uid = f"dg{_sha(content + lang + str(self._occl), 6)}{self._seq}"
        cap = opts.get("caption")
        width = opts.get("width")
        if lang in {"dot", "graphviz"}:
            inner = self._dot(content, opts, uid, width)
        elif lang == "tree":
            inner = self._dot(tree_to_dot(content), opts, uid, width)
        elif lang == "heap":
            inner = self._dot(heap_to_dot(content, opts), {}, uid, width)
        elif lang == "schema":
            return render_schema(content)
        elif lang == "svg":
            src = _COLOR_NAME_RE.sub(lambda m: PALETTE[m.group(1)][0], content)
            root = _svg_parse(src)
            _svg_sanitize(root)
            _svg_theme(root)
            _svg_highlight_nodes(root, set(filter(None, str(opts.get("hl", "")).split(","))))
            if self._occl:
                _svg_occlude(root, *self._occl)
            inner = _svg_finish(root, uid, width)
        elif lang == "mermaid":
            inner = self._mermaid(content, uid, width)
        else:
            raise RenderError(lang)
        cls = "dg" + (f" {self._dg_extra_class}" if self._dg_extra_class else "")
        capt = f"<figcaption>{html.escape(str(cap))}</figcaption>" if cap else ""
        return f'<figure class="{cls}">{inner}{capt}</figure>\n'

    def _dot(self, src: str, opts: dict, uid: str, width: str | None) -> str:
        if not shutil.which("dot"):
            raise RenderError("Graphviz (dot) não está instalado. Instale: apt install graphviz")
        src = _COLOR_NAME_RE.sub(lambda m: PALETTE[m.group(1)][0], src)
        ink = PALETTE["ink"][0]
        args = ["dot", "-Tsvg", "-Gbgcolor=transparent", "-Gfontname=DejaVu Sans", "-Nfontname=DejaVu Sans",
                "-Efontname=DejaVu Sans", "-Nfontsize=14", "-Efontsize=13", "-Gfontsize=14",
                f"-Ncolor={ink}", f"-Nfontcolor={ink}", f"-Ecolor={ink}", f"-Efontcolor={ink}",
                f"-Gfontcolor={ink}", f"-Gcolor={ink}", "-Gpad=0.1"]
        key = _sha(json.dumps([args, src]), 16)
        cached = self.cache_dir / f"dot-{key}.svg"
        if cached.exists():
            svg = cached.read_text()
        else:
            r = subprocess.run(args, input=src, capture_output=True, text=True)
            if r.returncode != 0:
                raise RenderError(f"Graphviz falhou: {r.stderr.strip()[:400]}")
            svg = r.stdout
            cached.write_text(svg)
        root = _svg_parse(svg)
        _svg_sanitize(root)
        _svg_theme(root)
        _svg_highlight_nodes(root, set(x.strip() for x in str(opts.get("hl", "")).split(",") if x.strip()))
        if self._occl:
            _svg_occlude(root, *self._occl)
        return _svg_finish(root, uid, width)

    def _mermaid(self, src: str, uid: str, width: str | None) -> str:
        mmdc, chrome = find_mmdc(), find_chromium()
        if not mmdc or not chrome:
            raise RenderError("Mermaid precisa de mmdc + Chromium (não encontrados). Use ```dot ou ```svg, "
                              "ou instale: PUPPETEER_SKIP_DOWNLOAD=1 npm i -g @mermaid-js/mermaid-cli e um Chromium")
        if self._occl:
            raise RenderError("oclusão não é suportada em Mermaid; use dot/tree/svg")
        src = _COLOR_NAME_RE.sub(lambda m: PALETTE[m.group(1)][0], src)
        outs = []
        for theme in ("light", "dark"):
            key = _sha(src + theme, 16)
            cached = self.cache_dir / f"mmd-{key}.svg"
            if not cached.exists():
                with tempfile.TemporaryDirectory() as td:
                    tdp = Path(td)
                    (tdp / "in.mmd").write_text(src)
                    (tdp / "pp.json").write_text(json.dumps({"executablePath": chrome, "args": ["--no-sandbox"]}))
                    cfg = {"htmlLabels": False, "flowchart": {"htmlLabels": False},
                           "theme": "neutral" if theme == "light" else "dark",
                           "themeVariables": {"fontFamily": "DejaVu Sans"}}
                    (tdp / "cfg.json").write_text(json.dumps(cfg))
                    r = subprocess.run([mmdc, "-p", str(tdp / "pp.json"), "-c", str(tdp / "cfg.json"),
                                        "-i", str(tdp / "in.mmd"), "-o", str(tdp / "out.svg"),
                                        "-b", "transparent", "-I", f"m{key[:8]}{theme[0]}"],
                                       capture_output=True, text=True, timeout=180)
                    if r.returncode != 0 or not (tdp / "out.svg").exists():
                        raise RenderError(f"Mermaid falhou: {(r.stderr or r.stdout).strip()[:400]}")
                    shutil.copy(tdp / "out.svg", cached)
            root = _svg_parse(cached.read_text())
            _svg_sanitize(root)
            _svg_theme(root)
            outs.append(f'<div class="mm-{theme}">{_svg_finish(root, f"{uid}{theme[0]}", width)}</div>')
        return "".join(outs)


# ---------------------------------------------------------------------------
# marca-texto ==x==  (pode conter `código` e **negrito**; ignora blocos de código)
# ---------------------------------------------------------------------------
_MARK_RE = re.compile(r"==(?=\S)(.+?)(?<=\S)==")
_FENCE_RE = re.compile(r"^(```|~~~)[^\n]*\n.*?^\1[ \t]*$", re.S | re.M)
_ICODE_RE = re.compile(r"(`+)(?!`).+?(?<!`)\1", re.S)


def apply_marks(text: str) -> str:
    store: list[str] = []

    def keep(m):
        store.append(m.group(0))
        return f"\ue010{len(store)-1}\ue011"
    t = _FENCE_RE.sub(keep, text)
    t = _ICODE_RE.sub(keep, t)
    t = _MARK_RE.sub(lambda m: f"<mark>{m.group(1)}</mark>", t)
    while "\ue010" in t:
        t = re.sub("\ue010(\\d+)\ue011", lambda m: store[int(m.group(1))], t)
    return t


# ---------------------------------------------------------------------------
# árvore binária → dot
# ---------------------------------------------------------------------------
def tree_to_dot(src: str) -> str:
    """'8(3(1,6*),10(,14?))'  *=destaque  ?=oculto  vazio=sem filho."""
    s = re.sub(r"\s+", "", src.strip())
    pos = 0
    nodes, edges = [], []
    counter = [0]

    def new_id():
        counter[0] += 1
        return f"n{counter[0]}"

    def parse():
        nonlocal pos
        m = re.match(r"[^(),]+", s[pos:])
        if not m:
            return None
        label = m.group(0)
        pos += len(label)
        flags = ""
        while label and label[-1] in "*?":
            flags += label[-1]
            label = label[:-1]
        nid = new_id()
        nodes.append((nid, label, flags))
        if pos < len(s) and s[pos] == "(":
            pos += 1
            left = parse()
            right = None
            if pos < len(s) and s[pos] == ",":
                pos += 1
                right = parse()
            if pos >= len(s) or s[pos] != ")":
                raise RenderError(f"árvore mal formada perto de: {s[pos:pos+10]!r}")
            pos += 1
            # nó invisível no meio força esquerda/direita simétricas (truque clássico do dot)
            for k, child in enumerate((left, None, right)):
                if k == 1 or child is None:
                    inv = new_id()
                    nodes.append((inv, "", "inv"))
                    edges.append((nid, inv, True))
                else:
                    edges.append((nid, child, False))
        return nid

    parse()
    if pos != len(s):
        raise RenderError(f"sobrou texto na árvore: {s[pos:]!r}")
    lines = ["graph T {", "  graph [ordering=out, nodesep=0.35, ranksep=0.35];",
             "  node [shape=circle, width=0.5, height=0.5, fixedsize=true];"]
    for nid, label, flags in nodes:
        if flags == "inv":
            lines.append(f'  {nid} [label="", style=invis, width=0.2];')
            continue
        lab = label.replace('"', '\\"')
        attrs = [f'id="{nid}"']
        classes = ["tnode"]
        if "*" in flags:
            classes.append("hl")
        if "?" in flags:
            classes.append("occ-hide")
            lab = "?"
        attrs.append(f'label="{lab}"')
        attrs.append(f'class="{" ".join(classes)}"')
        lines.append(f'  {nid} [{", ".join(attrs)}];')
    for a, b, inv in edges:
        lines.append(f"  {a} -- {b}" + (" [style=invis];" if inv else ";"))
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# heap / árvore completa a partir de um vetor (base 0)
# ---------------------------------------------------------------------------
def heap_to_dot(src: str, opts: dict) -> str:
    """Vetor → árvore binária completa com posições fixas (simétrica e estreita).
    ```heap {show=vk hl=1,3 path=0-1-3 alert=1-4 hide=4 dashed=3-5}
    [1, 3, 5, 7, 9, 6]
    ```
    show: v (valor, padrão) | k (índice) | vk (valor com [índice] embaixo)
    hl: índices destacados · hide: índices com rótulo "?" · dashed: índices tracejados (ex.: folhas)
    path: caminho de índices com arestas destacadas · alert: aresta pai-filho em vermelho (a-b)"""
    raw = src.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    vals = [v.strip().strip("'\"") for v in raw.split(",") if v.strip()]
    if not vals:
        raise RenderError("bloco heap vazio")
    n = len(vals)
    show = str(opts.get("show", "v"))
    hl, hide, dashed = parse_ranges(opts.get("hl")), parse_ranges(opts.get("hide")), parse_ranges(opts.get("dashed"))
    path_e, alert_e = set(), set()
    if opts.get("path"):
        pts = [int(x) for x in re.split(r"[-,\s]+", str(opts["path"])) if x]
        path_e = {tuple(sorted(e)) for e in zip(pts, pts[1:])}
    for pair in str(opts.get("alert", "")).split(","):
        if "-" in pair:
            a, b = pair.split("-", 1)
            alert_e.add(tuple(sorted((int(a), int(b)))))
    big = show == "vk"
    lv = lambda k: (k + 1).bit_length() - 1
    cnt = {}
    for k in range(n):
        cnt[lv(k)] = cnt.get(lv(k), 0) + 1
    widest = max([l for l, c in cnt.items() if c >= 2] or [0])
    if widest >= 3:   # 8+ folhas: compacta para caber em ~360 px sem fonte < 12 px
        w, sp, dy = (0.5, 0.53, 0.72) if big else (0.4, 0.44, 0.56)
    else:
        w, sp, dy = (0.62, 0.7, 0.78) if big else (0.48, 0.56, 0.64)
    if widest >= 4:
        raise RenderError("heap com 5+ níveis não cabe legível no celular: mostre só a subárvore relevante")
    W = (2 ** widest) * sp
    L = ["graph H {", "  layout=neato;", f"  node [shape=circle, width={w}, height={w}, fixedsize=true];"]
    for k, v in enumerate(vals):
        l = lv(k)
        x = (k - (2 ** l - 1) + 0.5) * W / 2 ** l
        y = -l * dy
        ve = html.escape(v)
        if k in hide:
            lab = '"?"'
        elif show == "k":
            lab = f'"{k}"'
        elif big:
            lab = f'<{ve}<BR/><FONT POINT-SIZE="12" COLOR="{PALETTE["muted"][0]}">[{k}]</FONT>>'
        else:
            lab = f'"{ve}"'
        attrs = [f'pos="{x:.2f},{y:.2f}!"', f"label={lab}", f'id="h{k}"']
        cls = ["hnode"]
        if k in hl:
            cls.append("hl")
        if k in hide:
            cls.append("occ-hide")
        if k in dashed:
            attrs.append(f'style=dashed, color="{PALETTE["muted"][0]}", fontcolor="{PALETTE["muted"][0]}"')
        attrs.append(f'class="{" ".join(cls)}"')
        L.append(f"  h{k} [{', '.join(attrs)}];")
    for k in range(n):
        for c in (2 * k + 1, 2 * k + 2):
            if c < n:
                e = tuple(sorted((k, c)))
                ea = ""
                if e in alert_e:
                    ea = f' [color="{PALETTE["alert"][0]}", penwidth=2.2]'
                elif e in path_e:
                    ea = f' [color="{PALETTE["accent"][0]}", penwidth=2.2]'
                L.append(f"  h{k} -- h{c}{ea};")
    L.append("}")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# esquema relacional
# ---------------------------------------------------------------------------
def render_schema(src: str) -> str:
    """Linhas: tabela(*pk, coluna, fk_col -> outra.col, !destaque)
    *=PK (sublinhado, notação de livro), ->=FK, !=marca-texto."""
    rels, refs = [], []
    for raw in src.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([\w.$]+)\s*\((.*)\)\s*$", line)
        if not m:
            raise RenderError(f"linha de schema inválida: {line!r} (formato: tabela(*id, col, fk -> outra.id))")
        name, cols = m.group(1), [c.strip() for c in m.group(2).split(",") if c.strip()]
        parts = []
        for c in cols:
            hl = c.startswith("!") or c.endswith("!")
            c = c.strip("!").strip()
            pk = c.startswith("*")
            c = c.lstrip("*").strip()
            fk = None
            if "->" in c:
                c, fk = [x.strip() for x in c.split("->", 1)]
            cls = []
            if pk:
                cls.append("pk")
            if fk:
                cls.append("fk")
                refs.append((name, c, fk))
            if hl:
                cls.append("hl")
            e = html.escape(c)
            parts.append(f'<span class="{" ".join(cls)}">{e}</span>' if cls else e)
        rels.append(f'<div class="rel"><span class="rn">{html.escape(name)}</span> ({", ".join(parts)})</div>')
        for (t, col, target) in [r for r in refs if r[0] == name]:
            tgt = html.escape(target)
            rels.append(f'<div class="fkref">{html.escape(col)} referencia {tgt}</div>')
    return f'<div class="schema">{"".join(rels)}</div>\n'


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    r = Renderer(base_dir=Path(sys.argv[1]).parent if len(sys.argv) > 1 else Path.cwd())
    text = Path(sys.argv[1]).read_text() if len(sys.argv) > 1 else sys.stdin.read()
    print(r.render(text, cloze_ok=True))
    for w in r.warnings:
        print("AVISO:", w, file=sys.stderr)
