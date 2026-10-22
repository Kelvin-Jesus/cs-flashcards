#!/usr/bin/env python3
"""apply_review — aplica um review.json (do agent revisor) a uma especificação de cards.

  python3 apply_review.py DECK.cards.yaml review.json -o DECK.cards.yaml [--dry-run]

* flag + fix   → atualiza só os campos de `fix` (o id fica: histórico preservado)
* reject + split → troca a nota pelas notas de `split`, na mesma posição
* reject sem split → remove a nota (listada no resumo; apague-a no Anki se já foi importada)
* pass → nada
Recusa `fix` que tente mudar `id` e ids novos que colidam com existentes.
"""
import argparse
import json
import sys
from pathlib import Path

import yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("review", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    spec = yaml.safe_load(a.spec.read_text())
    rev = json.loads(a.review.read_text())
    by_id = {r["id"]: r for r in rev.get("reviews", [])}
    existing = {n["id"] for n in spec["notes"]}
    out, fixed, split, removed, unknown = [], [], [], [], set(by_id) - existing
    for n in spec["notes"]:
        r = by_id.get(n["id"])
        if not r or r.get("verdict") == "pass":
            out.append(n)
            continue
        if r.get("split"):
            for s in r["split"]:
                if s.get("id") in existing and s.get("id") != n["id"]:
                    sys.exit(f"ERRO: split de '{n['id']}' cria id já existente '{s['id']}'")
                base = {k: v for k, v in n.items() if k in {"context", "source", "at", "level", "priority", "version", "subdeck", "tags"}}
                out.append({**base, **s})
            split.append(n["id"])
        elif r.get("fix"):
            fx = dict(r["fix"])
            if "id" in fx and fx["id"] != n["id"]:
                sys.exit(f"ERRO: fix de '{n['id']}' tenta mudar o id (perderia o histórico)")
            n2 = dict(n)
            for k, v in fx.items():
                if v is None:
                    n2.pop(k, None)
                else:
                    n2[k] = v
            out.append(n2)
            fixed.append(n["id"])
        elif r.get("verdict") == "reject":
            removed.append(n["id"])
        else:
            out.append(n)
    spec["notes"] = out
    print(f"corrigidos: {len(fixed)} | divididos: {len(split)} | removidos: {len(removed)} | total agora: {len(out)}")
    if removed:
        print("removidos (apague no Anki se já importados):", ", ".join(removed))
    if unknown:
        print("AVISO: review cita ids que não existem na especificação:", ", ".join(sorted(unknown)))
    if not a.dry_run:
        a.out.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=110))


if __name__ == "__main__":
    main()
