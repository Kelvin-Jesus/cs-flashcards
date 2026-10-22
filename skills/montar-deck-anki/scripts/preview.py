#!/usr/bin/env python3
"""preview — renderiza os cards como o Anki/AnkiDroid e confere o layout.

Entradas: o .apkg gerado e o cards.json (de build_deck.py --cards-json).
Saídas na pasta -o:
  galeria.html        página única para revisar todos os cards (frente/verso,
                      claro/escuro, largura de celular/tablet). Pode virar artifact.
  layout.json         problemas de layout por card (rolagem horizontal da página,
                      elemento vazando, fonte não carregada, card longo demais,
                      sintaxe de cloze/type sobrando, contraste)
  folhas/*.png        folhas de contato (frente/verso × claro/escuro, 390 px)
                      dos cards amostrados + todos os que tiveram problema

Renderização: usa o pacote oficial `anki` (pip install anki) quando disponível
(fiel ao Anki 2x: cloze, type, condicionais). Sem ele, usa um renderizador
próprio equivalente para os dois note types do plugin.
Screenshots: Playwright + Chromium (opcional; sem eles só a galeria é gerada).

Uso:
  python3 preview.py deck.apkg --cards cards.json -o prev/ [--lint lint.json] [--sample 8] [--all-shots]
"""
from __future__ import annotations

import argparse
import base64
import glob
import html
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
sys.path.insert(0, str(HERE))

WIDTHS = [390, 800, 1280]


# ---------------------------------------------------------------------------
# renderização das faces
# ---------------------------------------------------------------------------
def render_with_anki(apkg: Path) -> list[dict] | None:
    try:
        from anki.collection import Collection, ImportAnkiPackageRequest, ImportAnkiPackageOptions
    except Exception:
        return None
    td = Path(tempfile.mkdtemp(prefix="ccprev-"))
    col = Collection(str(td / "collection.anki2"))
    try:
        col.import_anki_package(ImportAnkiPackageRequest(
            package_path=str(apkg), options=ImportAnkiPackageOptions(with_scheduling=False, merge_notetypes=True)))
        out = []
        for cid in col.find_cards("deck:*"):
            c = col.get_card(cid)
            n = c.note()
            q = c.question()
            a = c.answer()
            out.append({"id": n["Id"] if "Id" in n else str(n.id), "ord": c.ord, "due": c.due,
                        "q": _strip_style(q), "a": _strip_style(a), "model": n.note_type()["name"],
                        "tags": list(n.tags)})
        out.sort(key=lambda x: (x["due"], x["ord"]))
        return out
    finally:
        col.close()
        shutil.rmtree(td, ignore_errors=True)


def _strip_style(h: str) -> str:
    return re.sub(r"<style>.*?</style>", "", h, flags=re.S)


def render_fallback(cards_json: dict) -> list[dict]:
    """Renderizador mínimo dos templates CC (sem pacote anki)."""
    from build_deck import BASIC_TEMPLATES, CLOZE_TEMPLATES
    out = []
    for c in cards_json["cards"]:
        f = c["fields"]
        if c["model"] == "cloze":
            nums = sorted({int(x) for x in re.findall(r"\{\{c(\d+)::", f["Texto"])})
            for k in nums:
                q = _mustache(CLOZE_TEMPLATES[0]["qfmt"], f, cloze=(k, "q"))
                a = _mustache(CLOZE_TEMPLATES[0]["afmt"], f, cloze=(k, "a"))
                out.append({"id": c["id"], "ord": k - 1, "due": c["due"], "q": q, "a": a, "model": "CC Cloze", "tags": c["tags"]})
        else:
            q = _mustache(BASIC_TEMPLATES[0]["qfmt"], f)
            a = _mustache(BASIC_TEMPLATES[0]["afmt"], f)
            out.append({"id": c["id"], "ord": 0, "due": c["due"], "q": q, "a": a, "model": "CC Básico", "tags": c["tags"]})
    return out


def _mustache(tpl: str, f: dict, cloze=None) -> str:
    def nonempty(name):
        return bool(re.sub(r"<[^>]+>|\s", "", f.get(name, "")) or "<svg" in f.get(name, "") or "<img" in f.get(name, ""))
    tpl = re.sub(r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}", lambda m: m.group(2) if nonempty(m.group(1)) else "", tpl, flags=re.S)
    tpl = re.sub(r"\{\{\^(\w+)\}\}(.*?)\{\{/\1\}\}", lambda m: "" if nonempty(m.group(1)) else m.group(2), tpl, flags=re.S)

    def cloze_filter(text):
        k, side = cloze

        def rep(m):
            n, content = int(m.group(1)), m.group(2)
            if n == k:
                return ('<span class="cloze" data-ordinal="%d">[...]</span>' % n) if side == "q" else \
                       f'<span class="cloze" data-ordinal="{n}">{content}</span>'
            return f'<span class="cloze-inactive" data-ordinal="{n}">{content}</span>'
        return _cloze_sub(text, rep)

    tpl = re.sub(r"\{\{cloze:(\w+)\}\}", lambda m: cloze_filter(f.get(m.group(1), "")), tpl)
    tpl = re.sub(r"\{\{type:(\w+)\}\}", lambda m: f"[[type:{m.group(1)}]]", tpl)
    return re.sub(r"\{\{(\w+)\}\}", lambda m: f.get(m.group(1), ""), tpl)


def _cloze_sub(text: str, rep) -> str:
    out, i = [], 0
    pat = re.compile(r"\{\{c(\d+)::")
    while True:
        m = pat.search(text, i)
        if not m:
            out.append(text[i:])
            return "".join(out)
        out.append(text[i:m.start()])
        j = text.find("}}", m.end())
        content = text[m.end():j]
        if "::" in content:
            content = content.split("::")[0]
        out.append(rep(type("M", (), {"group": lambda self, g, n=m.group(1), c=content: n if g == 1 else c})()))
        i = j + 2


def fix_type_placeholders(face: str, side: str, fields_by_id: dict, cid: str) -> str:
    """O reviewer do Anki troca [[type:X]] por um input; aqui simulamos."""
    def rep(m):
        if side == "q":
            return '<input type="text" id="typeans" placeholder="digite a resposta">'
        ans = html.unescape(re.sub(r"<[^>]+>", "", fields_by_id.get(cid, {}).get("Digitar", "")))
        return f'<code id="typeans"><span class="typeGood">{html.escape(ans)}</span></code>'
    return re.sub(r"\[\[type:[^\]]+\]\]", rep, face)


# ---------------------------------------------------------------------------
# páginas e galeria
# ---------------------------------------------------------------------------
def font_face_data_uri(css: str) -> str:
    def rep(m):
        name = m.group(1)
        p = ASSETS / "fonts" / name
        if not p.exists():
            return m.group(0)
        b64 = base64.b64encode(p.read_bytes()).decode()
        return f'url("data:font/woff2;base64,{b64}")'
    return re.sub(r'url\("(_cc1-[\w-]+\.woff2)"\)', rep, css)


def find_mathjax() -> str | None:
    """MathJax local para os screenshots (no Anki/AnkiDroid ele já vem embutido)."""
    env = os.environ.get("MATHJAX_JS")
    if env and os.path.exists(env):
        return env
    cands = [os.path.expanduser("~/.npm-global/lib/node_modules/mathjax/es5/tex-chtml.js"),
             "/usr/lib/node_modules/mathjax/es5/tex-chtml.js", "/usr/local/lib/node_modules/mathjax/es5/tex-chtml.js",
             "/usr/share/javascript/mathjax/es5/tex-chtml.js"]
    try:
        import subprocess
        root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=10).stdout.strip()
        if root:
            cands.insert(0, os.path.join(root, "mathjax/es5/tex-chtml.js"))
    except Exception:
        pass
    return next((c for c in cands if os.path.exists(c)), None)


MATHJAX = None


def page_html(css: str, face: str, night: bool, mobile: bool, card_ord: int) -> str:
    hcls = "mobile android linux js" if mobile else "linux chrome js"
    bcls = f"card card{card_ord + 1}" + (" nightMode night_mode" if night else "")
    mj = ""
    if MATHJAX and ("\\(" in face or "\\[" in face):
        mj = ('<script>window.MathJax={tex:{inlineMath:[["\\\\(","\\\\)"]],displayMath:[["\\\\[","\\\\]"]]},'
              'startup:{pageReady:()=>MathJax.startup.defaultPageReady().then(()=>{window.__mjDone=true})}};</script>'
              f'<script src="{Path(MATHJAX).as_uri()}"></script>')
    return (f'<!doctype html><html class="{hcls}"><head><meta charset="utf-8">'
            f"<style>{css}</style>{mj}</head><body class=\"{bcls}\">{face}</body></html>")


GALLERY_CSS = """
:root{--g-bg:#E9EEEC;--g-ink:#16202A;--g-muted:#56636E;--g-line:#C9D3D1;--g-acc:#0D6B61;--g-warn:#8A4B00;--g-err:#B3261E}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--g-bg:#0C0F11;--g-ink:#E5E9EC;--g-muted:#98A3AC;--g-line:#2E363D;--g-acc:#5CC4B4;--g-warn:#F2B866;--g-err:#FF8C82}}
:root[data-theme=dark]{--g-bg:#0C0F11;--g-ink:#E5E9EC;--g-muted:#98A3AC;--g-line:#2E363D;--g-acc:#5CC4B4;--g-warn:#F2B866;--g-err:#FF8C82}
html,body{margin:0;background:var(--g-bg);color:var(--g-ink);font-family:"CC Sans",system-ui,sans-serif}
body{background:var(--g-bg)}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:10;background:var(--g-bg)}
.g-top{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--g-bg);border-bottom:1px solid var(--g-line);padding-block:10px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
.g-top h1{font-size:17px;margin:0 8px 0 0}
.g-top .stat{color:var(--g-muted);font-size:14px}
.g-top button{font:inherit;font-size:14px;padding:5px 12px;border-radius:999px;border:1px solid var(--g-line);background:transparent;color:var(--g-ink);cursor:pointer}
.g-top button[aria-pressed=true]{background:var(--g-acc);border-color:var(--g-acc);color:#fff}
.g-list{padding-block:16px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:flex;flex-direction:column;gap:28px;max-width:1700px;margin:0 auto}
.g-item header{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:baseline;margin-bottom:8px}
.g-item header b{font-family:"CC Mono",monospace;font-size:14px}
.g-item header span{font-size:13px;color:var(--g-muted)}
.g-flag{font-size:13px;padding:2px 8px;border-radius:999px;border:1px solid currentColor}
.g-flag.warn{color:var(--g-warn)} .g-flag.error{color:var(--g-err)} .g-flag.info{color:var(--g-muted)}
.g-faces{display:flex;flex-wrap:wrap;gap:12px}
.g-item{min-width:0}
button:focus-visible{outline:2px solid var(--g-acc);outline-offset:2px}
.g-face{width:var(--fw,390px);max-width:100%;border:1px solid var(--g-line);border-radius:10px;overflow:hidden;display:flex;flex-direction:column}
.g-face > .lbl{font-size:12px;color:var(--g-muted);padding:4px 10px;border-bottom:1px solid var(--g-line);background:var(--g-bg)}
.g-face > .card{min-height:120px;flex:1}
.g-notes{font-size:13px;color:var(--g-muted);margin:6px 0 0;padding-left:18px}
"""

GALLERY_JS = """
const root=document.documentElement;
function setTheme(t){document.querySelectorAll('.g-face .card').forEach(c=>{const dark=t==='dark'||(t==='both'&&c.dataset.side%2==1);c.classList.toggle('nightMode',dark);c.classList.toggle('night_mode',dark)});
 document.querySelectorAll('[data-theme-btn]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.themeBtn===t));}
function setWidth(w){root.style.setProperty('--fw',w+'px');document.querySelectorAll('[data-w]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.w==w));}
function onlyFlagged(on){document.querySelectorAll('.g-item').forEach(i=>{i.hidden=on&&!i.dataset.flags});document.getElementById('flt').setAttribute('aria-pressed',on);}
let flt=false;
document.addEventListener('click',e=>{const t=e.target.closest('button');if(!t)return;
 if(t.dataset.themeBtn)setTheme(t.dataset.themeBtn); if(t.dataset.w)setWidth(t.dataset.w); if(t.id==='flt'){flt=!flt;onlyFlagged(flt)}});
setTheme('light');setWidth(390);
"""


def build_gallery(title: str, css: str, faces: list[dict], findings: dict, layout: dict) -> str:
    css_data = font_face_data_uri(css)
    items = []
    n_flag = 0
    for f in faces:
        key = f"{f['id']}#{f['ord']}"
        flags = list(findings.get(f["id"], [])) + [{"sev": "warn", "msg": m} for m in layout.get(key, {}).get("issues", [])]
        if flags:
            n_flag += 1
        badges = "".join(f'<span class="g-flag {html.escape(x.get("sev","info"))}">{html.escape(x.get("code", x.get("sev","")))}</span>' for x in flags[:6])
        notes = "".join(f"<li>{html.escape(x.get('msg',''))}</li>" for x in flags[:8])
        faces_html = "".join(
            f'<div class="g-face"><div class="lbl">{lbl}</div><div class="card card{f["ord"]+1}" data-side="{i}">{face}</div></div>'
            for i, (lbl, face) in enumerate([("frente", f["q"]), ("verso", f["a"])]))
        items.append(
            f'<section class="g-item" data-flags="{"1" if flags else ""}"><header><b>{html.escape(f["id"])}</b>'
            f'<span>{html.escape(f["model"])}{" · cloze " + str(f["ord"]+1) if "loze" in f["model"] else ""}</span>{badges}</header>'
            f'<div class="g-faces">{faces_html}</div>{"<ul class=g-notes>"+notes+"</ul>" if notes else ""}</section>')
    # fragmento no formato de artifact (o host envolve com doctype/head/body)
    head = (f'<title>{html.escape(title)}</title><meta name="claude:viewport-fit-sides" content="cover">'
            f'<style>{css_data}</style><style>{GALLERY_CSS}</style>'
            '<script>window.MathJax={tex:{inlineMath:[["\\\\(","\\\\)"]],displayMath:[["\\\\[","\\\\]"]]}};</script>'
            '<script async src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-chtml.min.js"></script>')
    top = (f'<div class="g-top"><h1>{html.escape(title)}</h1><span class="stat">{len(faces)} cards · {n_flag} com aviso</span>'
           '<button data-theme-btn="light">Claro</button><button data-theme-btn="dark">Escuro</button><button data-theme-btn="both">Frente clara, verso escuro</button>'
           '<button data-w="390">Celular</button><button data-w="800">Tablet</button><button data-w="1280">Desktop</button>'
           '<button id="flt">Só com aviso</button></div>')
    return head + top + '<main class="g-list">' + "".join(items) + f"</main><script>{GALLERY_JS}</script>"


# ---------------------------------------------------------------------------
# checagem de layout + screenshots
# ---------------------------------------------------------------------------
CHECK_JS = r"""
() => {
  const W = document.documentElement.clientWidth, H = window.innerHeight;
  const issues = [];
  const sw = document.documentElement.scrollWidth;
  if (sw > W + 1) issues.push(`página rola na horizontal (${sw}px > ${W}px)`);
  const scrollers = 'pre, .tbl, .schema, .typein';
  for (const el of document.querySelectorAll('.cc *')) {
    if (el.closest(scrollers) && !el.matches(scrollers)) continue;
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.right > W + 1) { issues.push(`elemento vaza a tela: <${el.tagName.toLowerCase()} class="${el.className.baseVal ?? el.className}">`); break; }
  }
  const txt = document.body.innerText;
  if (/\{\{c\d+::/.test(txt)) issues.push('sintaxe de cloze apareceu como texto');
  if (/\[\[type:/.test(txt)) issues.push('marcador [[type:]] apareceu como texto');
  if (!window.__ccFonts) issues.push('fontes do card não carregaram');
  const lum = c => { const m = c.match(/\d+(\.\d+)?/g).map(Number); const f = v => { v/=255; return v<=.03928? v/12.92 : ((v+.055)/1.055)**2.4 }; return .2126*f(m[0])+.7152*f(m[1])+.0722*f(m[2]); };
  const q = document.querySelector('.q');
  if (q) { const a = lum(getComputedStyle(q).color), b = lum(getComputedStyle(document.body).backgroundColor);
    const ratio = (Math.max(a,b)+.05)/(Math.min(a,b)+.05); if (ratio < 7) issues.push(`contraste baixo da pergunta (${ratio.toFixed(1)}:1)`); }
  let small = 0;
  for (const svg of document.querySelectorAll('.dg svg')) {
    const vb = svg.viewBox && svg.viewBox.baseVal; const w = svg.getBoundingClientRect().width;
    if (!vb || !vb.width || !w) continue;
    const scale = w / vb.width;
    for (const t of svg.querySelectorAll('text')) {
      const fs = parseFloat(t.getAttribute('font-size') || getComputedStyle(t).fontSize) || 14;
      if (fs * scale < 11.5) small++;
    }
  }
  if (small) issues.push(`texto de diagrama pequeno demais (${small} rótulos com menos de 12px) — use rankdir=TB, menos nós ou divida`);
  const inner = [...document.querySelectorAll(scrollers)].filter(e => e.scrollWidth > e.clientWidth + 1).length;
  return {issues, height: document.documentElement.scrollHeight, inner, H};
}
"""


def check_and_shoot(faces: list[dict], css: str, out: Path, sample: set[str], all_shots: bool) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("aviso: Playwright ausente — sem screenshots nem checagem de layout", file=sys.stderr)
        return {}
    sys.path.insert(0, str(HERE))
    from cardrender import find_chromium
    exe = find_chromium()
    pages_dir = out / "_pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for fn in (ASSETS / "fonts").glob("_cc1-*.woff2"):
        shutil.copy(fn, pages_dir / fn.name)
    shots_dir = out / "shots"
    shots_dir.mkdir(exist_ok=True)
    layout: dict = {}
    with sync_playwright() as p:
        kw = {"args": ["--no-sandbox"]}
        if exe:
            kw["executable_path"] = exe
        browser = p.chromium.launch(**kw)
        for w in WIDTHS:
            mobile = w <= 800
            ctx = browser.new_context(viewport={"width": w, "height": 844 if w == 390 else 1000}, device_scale_factor=1)
            page = ctx.new_page()
            for f in faces:
                key = f"{f['id']}#{f['ord']}"
                for side in ("q", "a"):
                    for night in (False, True):
                        fp = pages_dir / f"{re.sub(r'[^a-z0-9-]', '_', f['id'])}-{f['ord']}-{side}-{'d' if night else 'l'}-{w}.html"
                        fp.write_text(page_html(css, f[side], night, mobile, f["ord"]))
                        page.goto(fp.resolve().as_uri())
                        if "MathJax" in fp.read_text()[:4000]:
                            try:
                                page.wait_for_function("window.__mjDone === true", timeout=8000)
                            except Exception:
                                pass
                        page.evaluate("""async () => { const r = await Promise.all([document.fonts.load('16px "CC Sans"'), document.fonts.load('16px "CC Mono"')]); window.__ccFonts = r.every(x => x.length > 0); await document.fonts.ready; }""")
                        res = page.evaluate(CHECK_JS)
                        issues = [f"[{w}px {'escuro' if night else 'claro'} {'frente' if side=='q' else 'verso'}] {i}" for i in res["issues"]]
                        if w == 390 and not night and res["inner"]:
                            issues.append(f"[390px {'frente' if side=='q' else 'verso'}] {res['inner']} bloco(s) rolam na horizontal no celular — quebre linhas de código com mais de ~42 caracteres")
                        if w == 390 and not night and res["height"] > 2.2 * res["H"]:
                            issues.append(f"[390px {'frente' if side=='q' else 'verso'}] card muito longo ({res['height']}px ≈ {res['height']/res['H']:.1f} telas) — considere dividir")
                        ent = layout.setdefault(key, {"issues": [], "inner_scroll": 0})
                        ent["issues"] += issues
                        ent["inner_scroll"] = max(ent["inner_scroll"], res["inner"] if w == 390 else 0)
                        if w == 390 and (all_shots or key in sample or issues):
                            page.screenshot(path=str(shots_dir / f"{fp.stem}.png"), full_page=True)
            ctx.close()
        browser.close()
    return layout


def contact_sheets(faces: list[dict], out: Path, keys: list[str]) -> list[str]:
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return []
    shots = out / "shots"
    sheets_dir = out / "folhas"
    sheets_dir.mkdir(exist_ok=True)
    rows = []
    for f in faces:
        key = f"{f['id']}#{f['ord']}"
        if key not in keys:
            continue
        stem = f"{re.sub(r'[^a-z0-9-]', '_', f['id'])}-{f['ord']}"
        imgs = []
        for side, th in (("q", "l"), ("a", "l"), ("q", "d"), ("a", "d")):
            p = shots / f"{stem}-{side}-{th}-390.png"
            if p.exists():
                imgs.append(Image.open(p).convert("RGB"))
        if imgs:
            rows.append((key, imgs))
    paths = []
    per = 3
    for s in range(0, len(rows), per):
        chunk = rows[s:s + per]
        scale = 0.6
        col_w = int(390 * scale)
        row_hs = [int(min(max(i.height for i in imgs) * scale, 1100)) + 22 for _, imgs in chunk]
        sheet = Image.new("RGB", (col_w * 4 + 50, sum(row_hs) + 10), (200, 206, 204))
        d = ImageDraw.Draw(sheet)
        y = 5
        for (key, imgs), rh in zip(chunk, row_hs):
            d.text((10, y + 3), key, fill=(20, 30, 40))
            for k, im in enumerate(imgs):
                im2 = im.resize((col_w, int(im.height * scale)))
                im2 = im2.crop((0, 0, col_w, min(im2.height, rh - 22)))
                sheet.paste(im2, (10 + k * (col_w + 10), y + 20))
            y += rh
        p = sheets_dir / f"folha-{s // per + 1:02d}.png"
        sheet.save(p)
        paths.append(str(p))
    return paths


def pick_sample(faces: list[dict], n: int) -> set[str]:
    """Um card por (modelo, tipo de visual) até n, para cobrir a variedade."""
    seen, out = set(), []
    def kind(f):
        h = f["q"] + f["a"]
        return (f["model"], "svg" in h, "figure class=\"code" in h, "<table" in h, "schema" in h, "typeans" in h)
    for f in faces:
        k = kind(f)
        if k not in seen:
            seen.add(k)
            out.append(f"{f['id']}#{f['ord']}")
    for f in faces:
        if len(out) >= n:
            break
        key = f"{f['id']}#{f['ord']}"
        if key not in out:
            out.append(key)
    return set(out[:max(n, len(seen))])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("apkg", type=Path)
    ap.add_argument("--cards", type=Path, required=True, help="cards.json do build_deck.py")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--lint", type=Path, help="lint.json do revisar-flashcards (mostra avisos na galeria)")
    ap.add_argument("--sample", type=int, default=8)
    ap.add_argument("--all-shots", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--title", default=None)
    a = ap.parse_args()

    global MATHJAX
    MATHJAX = find_mathjax()
    cj = json.loads(a.cards.read_text())
    css = cj["css"]
    fields_by_id = {c["id"]: c["fields"] for c in cj["cards"]}
    faces = render_with_anki(a.apkg)
    engine = "anki"
    if faces is None:
        faces, engine = render_fallback(cj), "fallback"
    for f in faces:
        f["q"] = fix_type_placeholders(f["q"], "q", fields_by_id, f["id"])
        f["a"] = fix_type_placeholders(f["a"], "a", fields_by_id, f["id"])
    a.out.mkdir(parents=True, exist_ok=True)
    findings = {}
    if a.lint and a.lint.exists():
        lj = json.loads(a.lint.read_text())
        for item in lj.get("findings", []):
            findings.setdefault(item["id"], []).append(item)
    sample = pick_sample(faces, a.sample)
    layout = {} if a.no_shots else check_and_shoot(faces, css, a.out, sample, a.all_shots)
    flagged = [k for k, v in layout.items() if v["issues"]]
    sheet_keys = sorted(set(sample) | set(flagged), key=lambda k: [f"{f['id']}#{f['ord']}" for f in faces].index(k) if k in [f"{f['id']}#{f['ord']}" for f in faces] else 0)
    sheets = contact_sheets(faces, a.out, sheet_keys) if layout else []
    title = a.title or "Prévia do deck"
    (a.out / "galeria.html").write_text(build_gallery(title, css, faces, findings, layout))
    (a.out / "layout.json").write_text(json.dumps({"engine": engine, "cards": len(faces), "layout": layout,
                                                    "sheets": sheets}, ensure_ascii=False, indent=1))
    print(f"render: {engine} | {len(faces)} cards | com problema de layout: {len(flagged)}")
    for k in flagged:
        for i in layout[k]["issues"][:4]:
            print(f"  {k}: {i}")
    print(f"galeria: {a.out / 'galeria.html'}")
    for s in sheets:
        print(f"folha: {s}")


if __name__ == "__main__":
    main()
