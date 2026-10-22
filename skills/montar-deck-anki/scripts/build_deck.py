#!/usr/bin/env python3
"""build_deck — especificação YAML de cards → pacote .apkg para Anki/AnkiDroid.

Garantias (ver references/formato-da-especificacao.md e references/atualizacoes.md):
  * IDs de note type e de deck fixos → reimportar ATUALIZA, não duplica
  * GUID de cada nota = guid_for(namespace, id) → histórico de revisão preservado
  * ordem de introdução (due) por pré-requisitos, depois nível e prioridade
  * fontes e assets com prefixo "_" e versão no nome (Anki não sobrescreve mídia)
  * todo texto passa pelo cardrender (escape de HTML, cloze seguro, SVG temático)

Uso:
  python3 build_deck.py deck.cards.yaml [mais.yaml ...] -o saida.apkg
  python3 build_deck.py deck.cards.yaml --check          # só valida e renderiza
  opções: --cards-json f.json  --report f.json  --manifest f.json  --work DIR
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
sys.path.insert(0, str(HERE))
from cardrender import Renderer, RenderError  # noqa: E402

# ---- constantes congeladas: NUNCA mude depois de publicar um deck -----------
MODEL_BASIC_ID = 2097412722
MODEL_CLOZE_ID = 1824158746
NOTE_TYPE_VERSION = "v1"
BASIC_FIELDS = ["Id", "Contexto", "Frente", "Verso", "Extra", "Dica", "Digitar", "Fonte", "Versao",
                "Reserva1", "Reserva2", "Reserva3"]
CLOZE_FIELDS = ["Id", "Contexto", "Texto", "Extra", "Dica", "Fonte", "Versao", "Reserva1", "Reserva2", "Reserva3"]
FONT_FILES = ["_cc1-atkinson-400.woff2", "_cc1-atkinson-700.woff2", "_cc1-atkinson-400i.woff2",
              "_cc1-jbmono-400.woff2", "_cc1-jbmono-700.woff2"]

LEVELS = {"basic": 0, "basico": 0, "básico": 0, "core": 1, "nucleo": 1, "núcleo": 1, "advanced": 2, "avancado": 2, "avançado": 2}
TYPES = {"basic", "cloze", "type", "occlusion"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")

CTX = '{{#Contexto}}<div class="ctx">{{Contexto}}</div>{{/Contexto}}'
META = ('<div class="meta">{{#Fonte}}<span class="src">{{Fonte}}</span>{{/Fonte}}'
        '{{#Versao}}<span class="ver">{{Versao}}</span>{{/Versao}}</div>')
HINT = '{{#Dica}}<details class="hint"><summary>Dica</summary><div>{{Dica}}</div></details>{{/Dica}}'

BASIC_TEMPLATES = [{
    "name": "Card",
    "qfmt": ('<div class="cc side-q">' + CTX + '<div class="q">{{Frente}}</div>'
             '{{#Digitar}}<div class="typein">{{type:Digitar}}</div>{{/Digitar}}' + HINT + '</div>'),
    "afmt": ('<div class="cc side-a">' + CTX + '<div class="q">{{Frente}}</div><hr id=answer>'
             '{{#Digitar}}<div class="typein">{{type:Digitar}}</div>{{/Digitar}}'
             '<div class="a">{{Verso}}</div>{{#Extra}}<div class="extra">{{Extra}}</div>{{/Extra}}' + META + '</div>'),
}]
CLOZE_TEMPLATES = [{
    "name": "Cloze",
    "qfmt": ('<div class="cc side-q cloze-ask">' + CTX + '<div class="q cloze-body">{{cloze:Texto}}</div>' + HINT + '</div>'),
    "afmt": ('<div class="cc side-a cloze-reveal">' + CTX + '<div class="q cloze-body">{{cloze:Texto}}</div>'
             '<hr id=answer>{{#Extra}}<div class="extra">{{Extra}}</div>{{/Extra}}' + META + '</div>'),
}]


class SpecError(Exception):
    pass


def stable_int(*parts: str, lo: int = 1 << 30, hi: int = 1 << 31) -> int:
    h = int(hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:12], 16)
    return lo + h % (hi - lo)


def slug(s: str) -> str:
    s = s.lower()
    s = (s.replace("á", "a").replace("à", "a").replace("ã", "a").replace("â", "a").replace("é", "e")
         .replace("ê", "e").replace("í", "i").replace("ó", "o").replace("õ", "o").replace("ô", "o")
         .replace("ú", "u").replace("ü", "u").replace("ç", "c"))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "x"


def tag_clean(t: str) -> str:
    t = str(t).strip().replace(" ", "_")
    return re.sub(r"[\"']", "", t)


# ---------------------------------------------------------------------------
def load_specs(paths: list[Path], fragment_ok: bool = False) -> list[dict]:
    specs = []
    for p in paths:
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise SpecError(f"{p}: YAML inválido: {e}") from e
        if not isinstance(data, dict):
            raise SpecError(f"{p}: raiz precisa ser um mapa")
        if fragment_ok and ("deck" not in data or "namespace" not in data):  # fragmento de escritor
            data["_fragment"] = True
            data.setdefault("deck", "fragmento")
            data.setdefault("namespace", "fragmento")
        for k in ("deck", "namespace", "notes"):
            if k not in data:
                raise SpecError(f"{p}: falta a chave obrigatória '{k}'")
        if not ID_RE.match(str(data["namespace"])):
            raise SpecError(f"{p}: namespace '{data['namespace']}' precisa ser slug (a-z, 0-9, -)")
        data["_path"] = p
        specs.append(data)
    return specs


def infer_type(n: dict) -> str:
    t = n.get("type")
    if t:
        return str(t).lower()
    if "text" in n:
        return "cloze"
    if "occlude" in n:
        return "occlusion"
    if "answer" in n:
        return "type"
    return "basic"


def validate(specs: list[dict]) -> list[str]:
    errs: list[str] = []
    seen: dict[tuple, str] = {}
    for sp in specs:
        ns = sp["namespace"]
        src_ids = {s.get("id") for s in sp.get("sources", []) or []}
        ids = set()
        for i, n in enumerate(sp["notes"] or []):
            where = f"{sp['_path'].name}#{i} ({n.get('id', '?')})"
            nid = n.get("id")
            if not nid or not ID_RE.match(str(nid)):
                errs.append(f"{where}: 'id' ausente ou não é slug (a-z, 0-9, -)")
                continue
            if (ns, nid) in seen:
                errs.append(f"{where}: id duplicado (já usado em {seen[(ns, nid)]})")
            seen[(ns, nid)] = where
            ids.add(nid)
            t = infer_type(n)
            if t not in TYPES:
                errs.append(f"{where}: type '{t}' inválido (use {sorted(TYPES)})")
            if t in {"basic", "type"} and not n.get("front"):
                errs.append(f"{where}: falta 'front'")
            if t == "basic" and not n.get("back"):
                errs.append(f"{where}: falta 'back'")
            if t == "type":
                a = str(n.get("answer", ""))
                if not a or "\n" in a.strip():
                    errs.append(f"{where}: 'answer' de card de digitar precisa ser uma linha só")
            if t == "cloze":
                if not re.search(r"\{\{c\d+::", str(n.get("text", ""))):
                    errs.append(f"{where}: cloze sem {{{{cN::...}}}} em 'text'")
            if t == "occlusion":
                if not n.get("diagram") or not n.get("occlude"):
                    errs.append(f"{where}: oclusão precisa de 'diagram' e 'occlude: [alvos]'")
            lv = str(n.get("level", "core")).lower()
            if lv not in LEVELS:
                errs.append(f"{where}: level '{lv}' inválido (basic|core|advanced)")
            if n.get("source") and n["source"] not in src_ids and not sp.get("_fragment"):
                errs.append(f"{where}: source '{n['source']}' não está em sources[]")
        for i, n in enumerate(sp["notes"] or []):
            for pre in n.get("prereqs", []) or []:
                if pre not in ids:
                    errs.append(f"{sp['_path'].name}: '{n.get('id')}' tem prereq inexistente '{pre}'")
    return errs


def order_notes(notes: list[dict]) -> list[dict]:
    """Ordem topológica estável: pré-requisitos primeiro; empate → nível, prioridade, posição."""
    by_id = {n["id"]: n for n in notes}
    indeg = {n["id"]: 0 for n in notes}
    kids: dict[str, list[str]] = {n["id"]: [] for n in notes}
    for n in notes:
        for p in n.get("prereqs", []) or []:
            if p in by_id:
                indeg[n["id"]] += 1
                kids[p].append(n["id"])
    key = lambda nid: (LEVELS[str(by_id[nid].get("level", "core")).lower()], int(by_id[nid].get("priority", 2)), by_id[nid]["_idx"])
    heap = [(key(i), i) for i, d in indeg.items() if d == 0]
    heapq.heapify(heap)
    out = []
    while heap:
        _, nid = heapq.heappop(heap)
        out.append(by_id[nid])
        for k in kids[nid]:
            indeg[k] -= 1
            if indeg[k] == 0:
                heapq.heappush(heap, (key(k), k))
    if len(out) != len(notes):
        cyc = [i for i, d in indeg.items() if d > 0]
        raise SpecError(f"ciclo de pré-requisitos entre: {cyc[:10]}")
    return out


# ---------------------------------------------------------------------------
def context_html(root: str | None, ctx: str | None) -> str:
    parts = []
    if root:
        parts.append(str(root))
    if ctx:
        parts += [p.strip() for p in re.split(r"\s*(?:›|>|/)\s*", str(ctx)) if p.strip()]
    if not parts:
        return ""
    return '<span class="sep">›</span>'.join(html.escape(p) for p in parts)


def source_text(sp: dict, n: dict) -> str:
    sid = n.get("source")
    at = n.get("at")
    if not sid and not at:
        return ""
    title = sid
    for s in sp.get("sources", []) or []:
        if s.get("id") == sid:
            title = s.get("title") or sid
    txt = ", ".join(x for x in [str(title) if title else "", str(at) if at else ""] if x)
    return html.escape(txt)


def expand_occlusions(notes: list[dict]) -> list[dict]:
    out = []
    for n in notes:
        if infer_type(n) != "occlusion":
            out.append(n)
            continue
        for t in n["occlude"]:
            m = dict(n)
            m["id"] = f"{n['id']}--{slug(str(t))}"
            m["_target"] = str(t)
            m["_parent"] = n["id"]
            out.append(m)
    # prereqs que apontam para a oclusão-mãe passam a apontar para todos os filhos
    parents = {}
    for m in out:
        if "_parent" in m:
            parents.setdefault(m["_parent"], []).append(m["id"])
    for m in out:
        pre = []
        for p in m.get("prereqs", []) or []:
            pre += parents.get(p, [p])
        if pre:
            m["prereqs"] = pre
    return out


def render_note(r: Renderer, sp: dict, n: dict) -> tuple[str, dict]:
    t = infer_type(n)
    common = {
        "Id": html.escape(n["id"]),
        "Contexto": context_html(sp.get("context_root"), n.get("context")),
        "Extra": r.render(n.get("extra")),
        "Dica": r.render(n.get("hint")),
        "Fonte": source_text(sp, n),
        "Versao": html.escape(str(n.get("version", ""))) if n.get("version") else "",
        "Reserva1": "", "Reserva2": "", "Reserva3": "",
    }
    if t == "cloze":
        f = dict(common, Texto=r.render(n["text"], cloze_ok=True))
        return "cloze", f
    if t == "occlusion":
        target = n["_target"]
        prompt = n.get("front") or "Qual elemento está escondido no diagrama?"
        front = r.render(prompt) + r.render_occlusion(n["diagram"], target, "front", "occ-front")
        back_txt = n.get("back") or f"==**{target}**=="
        back = ('<div class="occ-back">' + r.render_occlusion(n["diagram"], target, "back") + "</div>"
                + r.render(str(back_txt).replace("{alvo}", target)))
        f = dict(common, Frente=front, Verso=back, Digitar="")
        return "basic", f
    f = dict(common, Frente=r.render(n["front"]), Verso=r.render(n.get("back")),
             Digitar=html.escape(str(n.get("answer", "")).strip()) if t == "type" else "")
    return "basic", f


def auto_tags(sp: dict, n: dict) -> list[str]:
    ns = sp["namespace"]
    tags = [f"cc::tipo::{infer_type(n)}", f"cc::nivel::{slug(str(n.get('level', 'core')))}",
            f"cc::prio::{int(n.get('priority', 2))}"]
    if n.get("context"):
        tags.append(ns + "::" + "::".join(slug(p) for p in re.split(r"\s*(?:›|>|/)\s*", str(n["context"])) if p.strip()))
    if n.get("source"):
        tags.append(f"fonte::{tag_clean(n['source'])}")
    if n.get("archetype"):
        tags.append(f"cc::arq::{slug(str(n['archetype']))}")
    tags += [tag_clean(x) for x in n.get("tags", []) or []]
    return sorted(set(t for t in tags if t))


# ---------------------------------------------------------------------------
def build(spec_paths: list[Path], out: Path | None, work: Path, check_only: bool = False,
          cards_json: Path | None = None, report: Path | None = None, manifest: Path | None = None) -> dict:
    import genanki

    specs = load_specs(spec_paths, fragment_ok=check_only)
    errs = validate(specs)
    if errs:
        raise SpecError("\n".join(errs))
    css = (ASSETS / "card.css").read_text(encoding="utf-8")
    basic = genanki.Model(MODEL_BASIC_ID, f"CC Básico {NOTE_TYPE_VERSION}", fields=[{"name": f} for f in BASIC_FIELDS],
                          templates=BASIC_TEMPLATES, css=css, sort_field_index=2)
    cloze = genanki.Model(MODEL_CLOZE_ID, f"CC Cloze {NOTE_TYPE_VERSION}", fields=[{"name": f} for f in CLOZE_FIELDS],
                          templates=CLOZE_TEMPLATES, css=css, model_type=genanki.Model.CLOZE, sort_field_index=2)
    media_dir = work / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    decks: dict[str, genanki.Deck] = {}
    rendered, warnings, stats = [], [], {"notes": 0, "by_type": {}, "by_level": {}}
    manifest_data = {"built": date.today().isoformat(), "specs": {}}
    errors: list[str] = []

    for sp in specs:
        r = Renderer(base_dir=sp["_path"].parent, media_out=media_dir, cache_dir=work / "cache")
        notes = [dict(n, _idx=i) for i, n in enumerate(sp["notes"] or [])]
        notes = expand_occlusions(notes)
        for i, n in enumerate(notes):
            n["_idx"] = i
        ordered = order_notes(notes)
        per_source: dict[str, list[str]] = {}
        for pos, n in enumerate(ordered):
            try:
                kind, fields = render_note(r, sp, n)
            except RenderError as e:
                errors.append(f"{sp['_path'].name}: nota '{n['id']}': {e}")
                continue
            deck_name = sp["deck"] + (f"::{n['subdeck']}" if n.get("subdeck") else "")
            if deck_name not in decks:
                decks[deck_name] = genanki.Deck(stable_int("deck", deck_name), deck_name)
            model = cloze if kind == "cloze" else basic
            names = CLOZE_FIELDS if kind == "cloze" else BASIC_FIELDS
            note = genanki.Note(model=model, fields=[fields[k] for k in names],
                                guid=genanki.guid_for(sp["namespace"], n["id"]),
                                tags=auto_tags(sp, n), due=(pos + 1) * 10)
            decks[deck_name].add_note(note)
            rendered.append({"id": n["id"], "namespace": sp["namespace"], "deck": deck_name, "model": kind,
                             "type": infer_type(n), "due": (pos + 1) * 10, "fields": fields, "tags": note.tags})
            stats["notes"] += 1
            stats["by_type"][infer_type(n)] = stats["by_type"].get(infer_type(n), 0) + 1
            lv = str(n.get("level", "core"))
            stats["by_level"][lv] = stats["by_level"].get(lv, 0) + 1
            if n.get("source"):
                per_source.setdefault(n["source"], []).append(n["id"])
        warnings += [f"{sp['_path'].name}: {w}" for w in r.warnings]
        srcs = {}
        for s in sp.get("sources", []) or []:
            entry = {"title": s.get("title"), "notes": per_source.get(s.get("id"), [])}
            if s.get("path"):
                p = (sp["_path"].parent / s["path"]).expanduser()
                entry["path"] = s["path"]
                if p.exists() and p.is_file():
                    entry["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
            srcs[s.get("id")] = entry
        manifest_data["specs"][str(sp["_path"])] = {"deck": sp["deck"], "namespace": sp["namespace"], "sources": srcs}

    if errors:
        raise SpecError("\n".join(errors))

    media = [str(ASSETS / "fonts" / f) for f in FONT_FILES]
    media += sorted({str(p) for p in media_dir.glob("cc1-img-*")})
    result = {"stats": stats, "warnings": warnings, "decks": sorted(decks), "apkg": None}
    if not check_only:
        if out is None:
            raise SpecError("informe -o saida.apkg")
        pkg = genanki.Package(list(decks.values()))
        pkg.media_files = media
        out.parent.mkdir(parents=True, exist_ok=True)
        pkg.write_to_file(str(out))
        result["apkg"] = str(out)
    if cards_json:
        cards_json.write_text(json.dumps({"css": css, "cards": rendered, "media": media}, ensure_ascii=False, indent=1))
    if manifest:
        all_ids = sorted(f"{c['namespace']}/{c['id']}" for c in rendered)
        if manifest.exists():
            try:
                prev = json.loads(manifest.read_text())
                prev_ids = set(prev.get("notes", []))
                result["removed"] = sorted(prev_ids - set(all_ids))   # apagar à mão no Anki
                result["added"] = sorted(set(all_ids) - prev_ids)
                old_src = {sid: v.get("sha256") for spv in prev.get("specs", {}).values() for sid, v in spv.get("sources", {}).items()}
                new_src = {sid: v.get("sha256") for spv in manifest_data["specs"].values() for sid, v in spv["sources"].items()}
                result["changed_sources"] = sorted(k for k in new_src if new_src[k] and old_src.get(k) != new_src[k])
            except (json.JSONDecodeError, KeyError):
                pass
        manifest_data["notes"] = all_ids
        manifest.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=1))
    if report:
        report.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("specs", nargs="+", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--check", action="store_true", help="só valida e renderiza, não grava .apkg")
    ap.add_argument("--work", type=Path, default=Path(".cc-build"), help="pasta de trabalho (cache, mídia)")
    ap.add_argument("--cards-json", type=Path)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--manifest", type=Path)
    a = ap.parse_args()
    try:
        res = build(a.specs, a.out, a.work, a.check, a.cards_json, a.report, a.manifest)
    except SpecError as e:
        print("ERRO:\n" + str(e), file=sys.stderr)
        sys.exit(2)
    s = res["stats"]
    print(f"ok: {s['notes']} notas | tipos {s['by_type']} | níveis {s['by_level']} | decks {res['decks']}")
    if res["apkg"]:
        print(f"apkg: {res['apkg']}")
    for w in res["warnings"]:
        print("AVISO:", w)
    if res.get("added") is not None:
        print(f"desde o último build: {len(res['added'])} notas novas")
    if res.get("removed"):
        print(f"SAÍRAM da especificação (apague à mão no Anki, o import não apaga): {', '.join(res['removed'])}")
    if res.get("changed_sources"):
        print(f"fontes alteradas desde o último build: {', '.join(res['changed_sources'])}")


if __name__ == "__main__":
    main()
