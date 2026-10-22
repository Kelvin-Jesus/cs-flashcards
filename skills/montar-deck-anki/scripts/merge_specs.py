#!/usr/bin/env python3
"""merge_specs — junta fragmentos de cards (um por agent escritor) numa especificação.

  python3 merge_specs.py cabecalho.yaml fragmentos/*.cards.yaml -o deck.cards.yaml [--base deck-atual.cards.yaml]

* cabecalho.yaml: deck, namespace, context_root, lang, terms, sources (sem notes, ou com notes)
* fragmentos: arquivos com `notes:` (e opcionalmente `sources:`/`terms:` extras)
* --base: especificação já publicada. Notas da base são mantidas na ordem original;
  um fragmento com o MESMO id substitui a nota (atualização), ids novos são anexados.
  Ids nunca são renomeados: isso apagaria o histórico do card no Anki.
Falha se dois fragmentos criarem o mesmo id novo.
"""
import argparse
import sys
from pathlib import Path

import yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("header", type=Path)
    ap.add_argument("fragments", nargs="*", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--base", type=Path)
    a = ap.parse_args()

    head = yaml.safe_load(a.header.read_text()) or {}
    base = yaml.safe_load(a.base.read_text()) if a.base and a.base.exists() else None
    spec = dict(base or head)
    for k in ("deck", "namespace", "context_root", "lang"):
        if base and head.get(k) and base.get(k) and head[k] != base[k] and k == "namespace":
            sys.exit(f"ERRO: namespace mudou ({base[k]} → {head[k]}). Isso duplicaria o deck inteiro no Anki.")
        if head.get(k) and not spec.get(k):
            spec[k] = head[k]
    notes = list((base or {}).get("notes") or head.get("notes") or [])
    index = {n["id"]: i for i, n in enumerate(notes)}
    sources = {s["id"]: s for s in (spec.get("sources") or []) + (head.get("sources") or [])}
    terms = {t["prefer"]: t for t in (spec.get("terms") or []) + (head.get("terms") or [])}
    new_from: dict[str, str] = {}
    updated = added = 0
    for fp in a.fragments:
        frag = yaml.safe_load(fp.read_text()) or {}
        for s in frag.get("sources") or []:
            sources.setdefault(s["id"], s)
        for t in frag.get("terms") or []:
            terms.setdefault(t["prefer"], t)
        for n in frag.get("notes") or []:
            nid = n.get("id")
            if not nid:
                sys.exit(f"ERRO: nota sem id em {fp}")
            if nid in index and nid not in new_from:
                notes[index[nid]] = n
                updated += 1
            elif nid in new_from:
                sys.exit(f"ERRO: id '{nid}' criado em {new_from[nid]} e em {fp}")
            else:
                index[nid] = len(notes)
                notes.append(n)
                new_from[nid] = str(fp)
                added += 1
    spec["sources"] = list(sources.values())
    spec["terms"] = list(terms.values())
    spec["notes"] = notes
    order = ["deck", "namespace", "context_root", "lang", "terms", "sources", "notes"]
    out = {k: spec[k] for k in order if k in spec}
    out.update({k: v for k, v in spec.items() if k not in out})
    a.out.write_text(yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=110))
    print(f"ok: {len(notes)} notas ({added} novas, {updated} atualizadas) → {a.out}")


if __name__ == "__main__":
    main()
