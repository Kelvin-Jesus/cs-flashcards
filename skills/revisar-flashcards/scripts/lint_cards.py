#!/usr/bin/env python3
"""lint_cards — checagens determinísticas de qualidade de flashcards.

Implementa como regras fixas o que LLMs julgam mal sobre os próprios cards
(Kirkby & Matuschak 2026: "múltiplas respostas" e "prolixo" têm F1 baixo
quando julgados por LLM). Cada achado cita a regra de origem:
  W# = Wozniak, 20 Rules of Formulating Knowledge (número da regra)
  M  = Matuschak, How to write good prompts
  N  = Nielsen, Augmenting Long-term Memory
  U  = preferência do usuário / AnkiDroid

Uso:
  python3 lint_cards.py deck.cards.yaml [...] [--json lint.json] [--quiet]
Saída: tabela legível no stdout; JSON com {"findings": [...], "summary": {...}}.
Código de saída 1 se houver erro (sev=error).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import yaml

STOP = set("""a o os as um uma uns umas de do da dos das em no na nos nas por para pra com sem
que qual quais quando como onde quem porque por que e ou se nao não sim mais menos muito pouco
ao aos à às é ser são sao foi está esta este esse essa isso isto aquele aquela seu sua seus suas
the a an of in on for to with without and or is are was be by from that which what when how why
this these those it its as at into than then there their""".split())

INTERROG = re.compile(r"\b(qual|quais|quant[oa]s?|como|por ?que|porqu[eê]|quando|onde|quem|o que|que (valor|comando|cl[aá]usula|tipo|fun[cç][aã]o|m[eé]todo)|"
                      r"what|which|why|how|when|where|who)\b", re.I)
BINARY_START = re.compile(r"^\s*(é|e|existe|existem|pode|podem|h[aá]|deve|devem|tem|t[eê]m|est[aá]|ser[aá]|"
                          r"consegue|funciona|vale|is|are|does|do|can|should|will|has|have)\b", re.I)
LIST_ASK = re.compile(r"\b(liste|enumere|cite (as|os|todas|todos|\d+)|quais s[aã]o (as|os|todas|todos)|"
                      r"name (all|the \d+)|list (the|all)|what are the|d[eê] (\d+|tr[eê]s|quatro|cinco) )", re.I)
EXAMPLE_ASK = re.compile(r"\b(d[eê] um exemplo|cite um exemplo|give an example)\b", re.I)
PROVINCIAL = re.compile(r"\b(slide \d+|cap[ií]tulo \d+|aula \d+|segundo o professor|no texto|o autor|nesta aula|in the (article|chapter))\b", re.I)
PRONOUN_START = re.compile(r"^\s*(isso|isto|este|esta|esse|essa|ele|ela|it|this|that)\b", re.I)
VISUAL_CITE = re.compile(r"\b(figura|fig\.|diagrama|tabela|exemplo (acima|abaixo|do slide)|veja o slide|como no slide|"
                         r"figure|diagram|table above|table below)\b", re.I)
VERSIONED = re.compile(r"\b(python|java|javascript|typescript|node(\.js)?|react|vue|angular|django|flask|spring|"
                       r"postgres(ql)?|mysql|sqlite|oracle|mongodb|redis|kotlin|swift|rust|go(lang)?|c\+\+\d\d|"
                       r"docker|kubernetes|linux kernel|android|ios|gradle|npm|pip)\b", re.I)


def deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def strip_visuals(md: str) -> str:
    """Remove blocos de código/diagramas, tabelas, HTML e matemática → só prosa."""
    t = re.sub(r"^(```|~~~).*?^\1[ \t]*$", " ", md or "", flags=re.S | re.M)
    t = "\n".join(l for l in t.splitlines() if not l.strip().startswith("|"))
    t = re.sub(r"<(pre|svg|table|figure|script|style)\b.*?</\1>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\\\(.+?\\\)|\\\[.+?\\\]", " X ", t, flags=re.S)
    t = re.sub(r"`[^`]+`", " C ", t)
    return t


def words(s: str) -> list[str]:
    return re.findall(r"[\wÀ-ÿ]+(?:[-'][\wÀ-ÿ]+)*", s)


def content_tokens(s: str) -> set[str]:
    out = set()
    for w in words(deaccent(s.lower())):
        if any(ch.isdigit() for ch in w):
            out.add(w)         # números contam sempre ("balde 2" ≠ "balde")
        elif len(w) >= 4 and w not in STOP:
            out.add(w[:6])     # radical grosseiro: "normalização" ≈ "normal"
    return out


def code_blocks(md: str) -> list[tuple[str, dict, str]]:
    out = []
    for m in re.finditer(r"^(```|~~~)([^\n]*)\n(.*?)^\1[ \t]*$", md or "", flags=re.S | re.M):
        info = m.group(2).strip()
        lang = (info.split("{")[0].strip() or "text").lower()
        opts = info[info.find("{"):] if "{" in info else ""
        out.append((lang, {"raw": opts}, m.group(3)))
    return out


def answer_key(back: str) -> str:
    marks = re.findall(r"==(.+?)==", back or "")
    if marks:
        return " ".join(marks)
    bold = re.findall(r"\*\*(.+?)\*\*", back or "")
    if bold:
        return " ".join(bold)
    first = strip_visuals(back or "").strip().split("\n")[0]
    return first


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


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


def lint_spec(sp: dict, path: Path, known_ids: set | None = None) -> list[dict]:
    F: list[dict] = []
    notes = sp.get("notes") or []
    has_sources = bool(sp.get("sources"))
    terms = sp.get("terms") or []

    ignore = {n.get("id"): {str(x).split(":")[0].strip() for x in (n.get("lint_ignore") or [])} for n in notes}

    def add(nid, sev, code, rule, msg):
        if code in ignore.get(nid, set()) and sev != "error":
            return  # aviso intencional, justificado na própria nota (lint_ignore)
        F.append({"id": nid, "sev": sev, "code": code, "rule": rule, "msg": msg, "file": path.name})

    fronts = {}
    by_ctx = defaultdict(list)
    ids = {n.get("id") for n in notes} | (known_ids or set())
    predict_ctx = defaultdict(list)

    for n in notes:
        nid = n.get("id", "?")
        t = infer_type(n)
        front = str(n.get("front") or "")
        back = str(n.get("back") or "")
        text = str(n.get("text") or "")
        hint = str(n.get("hint") or "")
        extra = str(n.get("extra") or "")
        q_md = text if t == "cloze" else front
        q_prose = strip_visuals(q_md if t != "cloze" else re.sub(r"\{\{c\d+::(.*?)\}\}", r"\1", text))
        lvl = str(n.get("level", "core")).lower()
        by_ctx[str(n.get("context", "")).strip().lower()].append(nid)
        if str(n.get("archetype", "")).lower() in {"predict-output", "prever-saida"}:
            predict_ctx[str(n.get("context", "")).lower()].append(nid)

        # ---------- estrutura ----------
        if t in {"basic", "type", "occlusion"} and not front and t != "occlusion":
            add(nid, "error", "frente-vazia", "—", "card sem pergunta")
        if t == "basic" and not back:
            add(nid, "error", "verso-vazio", "—", "card sem resposta")
        if t == "cloze" and not re.search(r"\{\{c\d+::", text):
            add(nid, "error", "cloze-ausente", "W5", "nota cloze sem {{cN::...}}")

        # ---------- W4 / W12: mínimo de informação, redação enxuta ----------
        qw = len(words(q_prose))
        if qw > 30:
            add(nid, "warn", "pergunta-longa", "W12", f"pergunta com {qw} palavras de prosa (alvo ≤ 25; código/tabela não contam)")
        if t in {"basic", "type", "occlusion"} and back:
            b_prose = strip_visuals(back)
            first = next((p for p in re.split(r"\n\s*\n", b_prose) if p.strip()), "")
            fw, tw = len(words(first)), len(words(b_prose))
            if fw > 20:
                add(nid, "warn", "resposta-longa", "W4", f"1º parágrafo da resposta com {fw} palavras (alvo ≤ 15). Leve o porquê para 'extra'")
            elif tw > 45:
                add(nid, "warn", "resposta-longa", "W4", f"resposta com {tw} palavras de prosa; divida ou mova para 'extra'")
            bullets = len(re.findall(r"^\s*([-*+]|\d+[.)])\s+", back, flags=re.M))
            if bullets >= 3:
                add(nid, "warn", "resposta-lista", "W9/W10", f"resposta é uma lista de {bullets} itens: um card por item ou clozes sobrepostos")
            if not re.search(r"==.+?==|\*\*.+?\*\*", back) and t == "basic":
                add(nid, "info", "sem-destaque", "U", "marque a resposta-chave com ==...== para leitura em 1 segundo")

        # ---------- W9 / W10: conjuntos e enumerações ----------
        if LIST_ASK.search(q_prose):
            add(nid, "warn", "lista-na-pergunta", "W9", "pergunta pede uma lista/conjunto: quebre em um card por membro")

        # ---------- M: sim/não, aberto, exemplo ----------
        if t != "cloze":
            first_sentence = re.split(r"[?\n]", q_prose.strip())[0] if q_prose.strip() else ""
            if (BINARY_START.search(first_sentence) and not INTERROG.search(first_sentence)) or re.search(r"verdadeiro ou falso|true or false", q_prose, re.I):
                add(nid, "warn", "sim-ou-nao", "M/N", "pergunta de sim/não: reescreva com qual/como/por que")
            if EXAMPLE_ASK.search(q_prose) and str(n.get("archetype", "")).lower() not in {"creative", "criativo"}:
                add(nid, "warn", "exemplo-aberto", "M", "'dê um exemplo' admite várias respostas; peça um exemplo específico ou marque archetype: creative")

        # ---------- W16: contexto ----------
        if not n.get("context"):
            add(nid, "info", "sem-contexto", "W16", "sem 'context' (breadcrumb): ajuda a eliminar interpretações concorrentes")
        if PRONOUN_START.search(q_prose):
            add(nid, "warn", "pronome-solto", "W16/M", "pergunta começa com pronome sem referente ('isso', 'este...')")
        if PROVINCIAL.search(q_prose):
            add(nid, "warn", "provincial", "W18/M", "referência a slide/aula/autor na pergunta: mova para 'source'/'at'")

        # ---------- vazamento da resposta (M: effortful) ----------
        if t in {"basic", "type"} and back:
            key = content_tokens(answer_key(back))
            qtok = content_tokens(q_prose)
            if key and key <= qtok:
                add(nid, "warn", "vazamento", "M", "todas as palavras da resposta-chave já aparecem na pergunta")
            if hint and key and key <= content_tokens(strip_visuals(hint)):
                add(nid, "warn", "dica-entrega", "M", "a dica contém a resposta")
        if t == "cloze":
            for c in re.findall(r"\{\{c\d+::(.*?)\}\}", text):
                ck = content_tokens(c)
                rest = content_tokens(strip_visuals(re.sub(r"\{\{c\d+::.*?\}\}", " ", text)))
                if ck and ck <= rest:
                    add(nid, "warn", "vazamento", "M", f"o texto do cloze '{c[:30]}' aparece em outra parte do card")
                    break

        # ---------- cloze ----------
        if t == "cloze":
            nums = set(re.findall(r"\{\{c(\d+)::", text))
            if len(nums) > 3:
                add(nid, "info", "cloze-demais", "W5", f"{len(nums)} clozes numa nota: confira se os irmãos não se entregam")
            for c in re.findall(r"\{\{c\d+::(.*?)\}\}", text):
                cw = len(words(re.sub(r"<[^>]+>", " ", c)))
                if cw > 5:
                    add(nid, "warn", "cloze-grande", "W4", f"cloze esconde {cw} palavras: esconda o termo, não a frase")
                    break
            for lang, opts, body in code_blocks(text):
                if len(nums) > 1 and re.search(r"\b(hl|err|ok)=", opts["raw"]):
                    add(nid, "warn", "cloze-destaque", "M", "destaque de linha (hl/err) num cloze com vários buracos aponta para a linha errada nos irmãos")
                for c in re.findall(r"\{\{c\d+::(.*?)\}\}", body):
                    if len(c) > 30:
                        add(nid, "warn", "cloze-codigo-grande", "W4", "cloze em código > 30 caracteres: esconda um token/expressão")
                        break

        # ---------- código ----------
        for lang, opts, body in code_blocks(q_md):
            nl = body.count("\n") + 1
            if lang not in {"schema", "dot", "graphviz", "tree", "mermaid", "svg"} and nl > 12:
                add(nid, "warn", "codigo-longo", "W4/Sivers", f"bloco de {nl} linhas na pergunta (alvo ≤ 10): recorte o trecho relevante")
        for lang, opts, body in code_blocks(back + "\n" + extra):
            nl = body.count("\n") + 1
            if lang not in {"schema", "dot", "graphviz", "tree", "mermaid", "svg"} and nl > 20:
                add(nid, "info", "codigo-longo", "W4", f"bloco de {nl} linhas na resposta")

        # ---------- U: SQL sem esquema / exemplo citado ausente ----------
        q_langs = [l for l, _, b in code_blocks(q_md)]
        q_sql = [b for l, _, b in code_blocks(q_md) if l in {"sql", "postgresql", "pgsql", "mysql", "plpgsql"}]
        if any(re.search(r"\b(from|join|update|into)\b", b, re.I) for b in q_sql):
            has_schema = "schema" in q_langs or re.search(r"^\s*\|.+\|", q_md, re.M) or re.search(r"create table", q_md, re.I)
            if not has_schema:
                add(nid, "warn", "sql-sem-esquema", "U", "pergunta com SQL mas sem ```schema (ou tabela) visível na própria pergunta")
        if VISUAL_CITE.search(strip_visuals(q_md + " " + back)):
            has_visual = bool(code_blocks(q_md + back)) or "|" in (q_md + back) or "![" in (q_md + back)
            if not has_visual:
                add(nid, "warn", "exemplo-citado-ausente", "U", "o card cita figura/tabela/diagrama que não está no card")

        # ---------- type ----------
        if t == "type" and len(str(n.get("answer", ""))) > 40:
            add(nid, "warn", "digitar-longo", "AnkiDroid", "resposta digitada > 40 caracteres: comparação letra a letra fica injusta")

        # ---------- W18 / W19 ----------
        if has_sources and not n.get("source"):
            add(nid, "info", "sem-fonte", "W18", "sem 'source'")
        all_txt = strip_visuals(front + back + text)
        if VERSIONED.search(all_txt) and not n.get("version") and lvl != "basic":
            add(nid, "info", "sem-versao", "W19", "menciona tecnologia que muda com versões; considere 'version'")

        # ---------- vocabulário travado ----------
        lower = deaccent((front + " " + back + " " + text + " " + extra).lower())
        for term in terms:
            for bad in term.get("avoid", []) or []:
                if re.search(r"\b" + re.escape(deaccent(bad.lower())) + r"\b", lower):
                    add(nid, "warn", "termo-evitado", "W11", f"use '{term.get('prefer')}' em vez de '{bad}' (vocabulário do deck)")

        # ---------- prereqs ----------
        for p in n.get("prereqs", []) or []:
            if p not in ids:
                add(nid, "error", "prereq-inexistente", "W3", f"prereq '{p}' não existe")

        fronts[nid] = (content_tokens(q_prose), content_tokens(answer_key(back) if back else text), n)

    # ---------- duplicatas e interferência (W11) ----------
    items = list(fronts.items())
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (a, (qa, ka, na)), (b, (qb, kb, nb)) = items[i], items[j]
            if not qa or not qb:
                continue
            sim = jaccard(qa, qb)
            linked = b in (na.get("pair") or []) or a in (nb.get("pair") or [])
            if sim >= 0.8 and jaccard(ka, kb) >= 0.6:
                add(b, "warn", "duplicata", "W11", f"quase igual a '{a}' (pergunta e resposta)")
            elif sim >= 0.6 and not linked and jaccard(ka, kb) < 0.5:
                add(b, "info", "interferencia", "W11", f"pergunta parecida com '{a}' e resposta diferente: crie um card distinguidor ou ligue com 'pair'")

    # ---------- consistência entre escritores paralelos (W11/W16) ----------
    roots = defaultdict(list)
    for n in notes:
        ctx = str(n.get("context", "")).strip()
        if ctx:
            roots[re.split(r"\s*(?:›|>|/)\s*", ctx)[0].strip()].append(n.get("id"))
    norm = defaultdict(list)
    for r in roots:
        norm[deaccent(r.lower()).rstrip("s")[:5]].append(r)
    for variants in norm.values():
        if len(variants) > 1:
            main = max(variants, key=lambda v: len(roots[v]))
            for v in variants:
                if v != main:
                    for nid in roots[v]:
                        add(nid, "warn", "contexto-inconsistente", "W16", f"raiz de contexto '{v}' ≠ '{main}' usada no resto do deck: padronize")
    vers = defaultdict(list)
    for n in notes:
        if n.get("version"):
            vers[str(n["version"]).strip()].append(n.get("id"))
    vnorm = defaultdict(list)
    for v in vers:
        key = re.sub(r"[^a-z]", "", deaccent(v.lower()).replace("cpython", "python"))[:6]
        vnorm[key].append(v)
    for variants in vnorm.values():
        if len(variants) > 1:
            main = max(variants, key=lambda v: len(vers[v]))
            for v in variants:
                if v != main:
                    for nid in vers[v]:
                        add(nid, "warn", "versao-inconsistente", "W19", f"versão '{v}' ≠ '{main}' usada no resto do deck: padronize")

    # ---------- N: órfãos; M: variações de prever-saída ----------
    for ctx, nids in by_ctx.items():
        if ctx and len(nids) == 1:
            n = next(x for x in notes if x.get("id") == nids[0])
            if str(n.get("level", "core")).lower() != "basic":
                add(nids[0], "info", "orfao", "N", "único card deste conceito: 2–3 ângulos diferentes retêm melhor")
    for ctx, nids in predict_ctx.items():
        if len(nids) == 1:
            add(nids[0], "info", "prever-sem-variacao", "M", "card de prever saída sem variações: repetido, vira decoreba (Matuschak sugere ~5 variações)")
    return F


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("specs", nargs="+", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--quiet", action="store_true", help="omite achados 'info' na tabela")
    ap.add_argument("--known", type=Path, action="append", default=[],
                    help="especificação com ids que existem fora deste fragmento (para prereqs entre seções)")
    a = ap.parse_args()
    findings = []
    total = 0
    known = set()
    for k in a.known:
        if k.exists():
            known |= {n.get("id") for n in (yaml.safe_load(k.read_text()) or {}).get("notes") or []}
    for p in a.specs:
        sp = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        total += len(sp.get("notes") or [])
        findings += lint_spec(sp, p, known)
    order = {"error": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda f: (order[f["sev"]], f["id"]))
    summary = {"notes": total, "error": sum(f["sev"] == "error" for f in findings),
               "warn": sum(f["sev"] == "warn" for f in findings), "info": sum(f["sev"] == "info" for f in findings)}
    for f in findings:
        if a.quiet and f["sev"] == "info":
            continue
        print(f"{f['sev']:5} {f['id']:<32} {f['code']:<22} [{f['rule']}] {f['msg']}")
    print(f"\n{summary['notes']} notas | {summary['error']} erros | {summary['warn']} avisos | {summary['info']} infos")
    if a.json:
        a.json.write_text(json.dumps({"findings": findings, "summary": summary}, ensure_ascii=False, indent=1))
    sys.exit(1 if summary["error"] else 0)


if __name__ == "__main__":
    main()
