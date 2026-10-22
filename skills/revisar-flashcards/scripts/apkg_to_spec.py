#!/usr/bin/env python3
"""apkg_to_spec — extrai um deck .apkg existente para uma especificação YAML de rascunho,
para auditar com lint_cards.py e com o agent revisor, ou migrar para os note types CC.

  python3 apkg_to_spec.py deck.apkg -o rascunho.cards.yaml [--namespace meu-deck] [--limit 500]

* Usa o pacote oficial `anki` se instalado (lê .anki21b de exports novos); senão lê
  o SQLite legado (collection.anki21/anki2) do zip.
* Campos viram HTML cru dentro do YAML (Markdown aceita HTML). O primeiro campo vira
  front, o segundo back; notas cloze viram type: cloze com text.
* Os ids gerados (old-<id da nota>) servem para a auditoria. Para migrar sem perder
  histórico, NÃO reimporte como deck novo: veja references/auditar-deck-existente.md.
"""
import argparse
import re
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

import yaml


def strip(h: str) -> str:
    return h.replace("&nbsp;", " ").strip()


def read_with_anki(p: Path):
    from anki.collection import Collection, ImportAnkiPackageRequest, ImportAnkiPackageOptions
    td = Path(tempfile.mkdtemp())
    col = Collection(str(td / "c.anki2"))
    try:
        col.import_anki_package(ImportAnkiPackageRequest(package_path=str(p), options=ImportAnkiPackageOptions()))
        out = []
        for nid in col.find_notes(""):
            n = col.get_note(nid)
            nt = n.note_type()
            names = [f["name"] for f in nt["flds"]]
            deck = col.decks.name(col.get_card(n.card_ids()[0]).did) if n.card_ids() else ""
            out.append({"nid": nid, "cloze": nt["type"] == 1, "fields": dict(zip(names, n.fields)), "tags": list(n.tags), "deck": deck})
        return out
    finally:
        col.close()
        shutil.rmtree(td, ignore_errors=True)


def read_legacy(p: Path):
    td = Path(tempfile.mkdtemp())
    try:
        with zipfile.ZipFile(p) as z:
            name = next((n for n in ("collection.anki21", "collection.anki2") if n in z.namelist()), None)
            if not name:
                sys.exit("pacote sem collection.anki21/anki2 (export novo .anki21b): instale `pip install anki`")
            z.extract(name, td)
        db = sqlite3.connect(td / name)
        import json
        models = json.loads(db.execute("select models from col").fetchone()[0])
        decks = json.loads(db.execute("select decks from col").fetchone()[0])
        out = []
        for nid, mid, flds, tags in db.execute("select id, mid, flds, tags from notes"):
            m = models[str(mid)]
            names = [f["name"] for f in m["flds"]]
            did = db.execute("select did from cards where nid=? limit 1", (nid,)).fetchone()
            out.append({"nid": nid, "cloze": m.get("type") == 1, "fields": dict(zip(names, flds.split("\x1f"))),
                        "tags": tags.split(), "deck": decks.get(str(did[0]), {}).get("name", "") if did else ""})
        return out
    finally:
        shutil.rmtree(td, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("apkg", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--namespace", default="importado")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    try:
        rows = read_with_anki(a.apkg)
    except ImportError:
        rows = read_legacy(a.apkg)
    if a.limit:
        rows = rows[:a.limit]
    notes = []
    for r in rows:
        vals = list(r["fields"].values())
        names = list(r["fields"].keys())
        n = {"id": f"old-{r['nid']}"}
        if r["cloze"]:
            text_key = next((k for k in names if k.lower() in {"text", "texto"}), names[0])
            n["type"] = "cloze"
            n["text"] = strip(r["fields"][text_key])
            rest = [k for k in names if k != text_key and strip(r["fields"][k])]
            if rest:
                n["extra"] = "\n\n".join(strip(r["fields"][k]) for k in rest)
        else:
            n["front"] = strip(vals[0]) if vals else ""
            n["back"] = strip(vals[1]) if len(vals) > 1 else ""
            more = [strip(v) for v in vals[2:] if strip(v)]
            if more:
                n["extra"] = "\n\n".join(more)
        if r["tags"]:
            n["tags"] = r["tags"]
        if r["deck"]:
            n["_deck_original"] = r["deck"]
        notes.append(n)
    deck = rows[0]["deck"] if rows else "Importado"
    spec = {"deck": deck, "namespace": a.namespace, "notes": notes}
    a.out.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=110))
    print(f"ok: {len(notes)} notas extraídas → {a.out}")


if __name__ == "__main__":
    main()
