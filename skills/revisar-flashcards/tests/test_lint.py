#!/usr/bin/env python3
"""Garante que o linter pega cada defeito plantado em cards-ruins.cards.yaml
e não acusa avisos no deck de exemplo bom. Rode: python3 tests/test_lint.py"""
import sys
from pathlib import Path
import yaml
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from lint_cards import lint_spec  # noqa

EXPECT = {"lista": {"lista-na-pergunta", "resposta-lista"}, "binaria": {"sim-ou-nao"}, "vazamento": {"vazamento"},
          "sql-sem-esquema": {"sql-sem-esquema"}, "provincial": {"provincial"}, "pronome": {"pronome-solto"},
          "termo": {"termo-evitado"}, "cloze-grande": {"cloze-grande"}, "resposta-longa": {"resposta-longa"},
          "exemplo-citado": {"exemplo-citado-ausente"}}
p = HERE / "cards-ruins.cards.yaml"
found = {}
for f in lint_spec(yaml.safe_load(p.read_text()), p):
    found.setdefault(f["id"], set()).add(f["code"])
fail = 0
for nid, codes in EXPECT.items():
    miss = codes - found.get(nid, set())
    if miss:
        fail += 1
        print(f"FALHOU {nid}: não detectou {miss} (achou {found.get(nid)})")
good = HERE.parents[1] / "montar-deck-anki" / "examples" / "exemplo-cc.cards.yaml"
warns = [f for f in lint_spec(yaml.safe_load(good.read_text()), good) if f["sev"] != "info"]
for w in warns:
    fail += 1
    print(f"FALSO POSITIVO no exemplo bom: {w['id']} {w['code']}: {w['msg']}")
print("ok" if not fail else f"{fail} falha(s)")
sys.exit(1 if fail else 0)
