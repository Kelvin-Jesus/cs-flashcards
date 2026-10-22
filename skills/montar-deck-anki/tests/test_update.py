#!/usr/bin/env python3
"""Teste ponta a ponta da atualização: importa v1, revisa um card, muda o texto
de um card + acrescenta uma nota, importa v2. Confere: nada duplicado, texto
atualizado, histórico de revisão preservado, nota nova entra.
Precisa do pacote `anki` (pip install anki). Rode: python3 tests/test_update.py"""
import shutil, sys, tempfile, time
from pathlib import Path
import yaml
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from build_deck import build  # noqa
try:
    from anki.collection import Collection, ImportAnkiPackageRequest, ImportAnkiPackageOptions
except ImportError:
    print("pacote anki ausente: teste pulado"); sys.exit(0)

td = Path(tempfile.mkdtemp())
spec = yaml.safe_load((HERE.parent / "examples" / "exemplo-cc.cards.yaml").read_text())
p1 = td / "v1.cards.yaml"; p1.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False))
build([p1], td / "v1.apkg", td / "w1")
col = Collection(str(td / "c" / "collection.anki2")) if (td / "c").mkdir() is None else None
imp = lambda f: col.import_anki_package(ImportAnkiPackageRequest(package_path=str(f), options=ImportAnkiPackageOptions(with_scheduling=False, merge_notetypes=True))).log
log1 = imp(td / "v1.apkg")
n_notes, n_cards = col.note_count(), col.card_count()
cid = col.find_cards("Id:git-log-oneline")[0]
card = col.get_card(cid); card.start_timer(); col.sched.answer_card(col.sched.build_answer(card=card, states=col._backend.get_scheduling_states(card.id), rating=3)) if hasattr(col.sched, "build_answer") else None
rev_before = col.db.scalar("select count() from revlog")
time.sleep(1.1)  # o .apkg novo precisa ter timestamp mais novo
spec["notes"][0]["extra"] = "TEXTO ATUALIZADO"
spec["notes"].append({"id": "nota-nova", "front": "Pergunta nova?", "back": "==resposta=="})
p2 = td / "v2.cards.yaml"; p2.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False))
build([p2], td / "v2.apkg", td / "w2")
log2 = imp(td / "v2.apkg")
ok = True
def check(cond, msg):
    global ok
    print(("ok   " if cond else "FALHA"), msg); ok &= cond
check(col.note_count() == n_notes + 1, f"notas: {n_notes} → {col.note_count()} (esperado +1, sem duplicar)")
check(len(log2.updated) >= 1, f"notas atualizadas: {len(log2.updated)}")
check(len(log2.new) == 1, f"notas novas: {len(log2.new)}")
check(len(log2.conflicting) == 0, f"conflitos de note type: {len(log2.conflicting)}")
nid = col.find_notes(f"Id:{spec['notes'][0]['id']}")[0]
check("TEXTO ATUALIZADO" in col.get_note(nid)["Extra"], "campo Extra atualizado")
check(col.db.scalar("select count() from revlog") == rev_before, f"histórico de revisão preservado ({rev_before} entradas)")
check(sum(1 for m in col.models.all_names_and_ids() if m.name.startswith("CC ")) == 2, "só 2 note types CC (sem 'CC Básico v1+')")
col.close(); shutil.rmtree(td, ignore_errors=True)
sys.exit(0 if ok else 1)
