---
name: revisar-flashcards
description: Audita flashcards contra as 20 regras de Wozniak e os princípios de Matuschak — linter determinístico (lista, sim/não, vazamento, prolixidade, SQL sem esquema, termos fora do vocabulário, interferência, órfãos) mais julgamento com exemplos rotulados, checagem de fatos contra a fonte e execução de código — e devolve veredito pass/flag/reject com correção. Use para revisar cards recém-gerados (sempre por um revisor que não os escreveu), auditar um deck Anki existente (.apkg) ou quando o aluno disser que um card "está ruim", "vive errando" ou é um leech.
---

# Revisar flashcards

Esta skill nunca reescreve o deck sozinha. Ela **julga** e **propõe**; quem escreveu aplica.
Para cards novos, a revisão é feita por um agent que **não viu** a escrita, para o trabalho não se
autoavaliar. Caminhos relativos à pasta desta skill.

Leia: `references/rubrica.md` (códigos, vereditos, formato de saída) e
`../escrever-flashcards/references/exemplos-ouro.md` (a âncora de julgamento).

## 1. Linter determinístico (primeiro, sempre)
```bash
python3 scripts/lint_cards.py DECK.cards.yaml --json lint.json
```
Ele pega mecanicamente o que LLMs julgam mal: pedidos de lista, sim/não, vazamento da resposta,
pergunta > 25 e resposta > 15 palavras de prosa, cloze grande, SQL sem esquema na pergunta,
exemplo citado e ausente, pronome solto, "slide N" na pergunta, termos fora do vocabulário do deck,
duplicatas, interferência, órfãos, prever saída sem variações, comando digitado longo.
`error` bloqueia o build, `warn` precisa ser corrigido ou justificado, `info` é sugestão.
Para conferir o próprio linter: `python3 tests/test_lint.py`.

## 2. Julgamento (o que regra fixa não pega)
Para cada card, na ordem:
1. **Fato**: confira com a fonte (`source`/`at`); execute código e SQL e compare com o verso.
2. **Uma resposta só**: tente escrever uma 2ª resposta válida. Se conseguir, é `varias-respostas`.
3. **Cinco propriedades**: focado, preciso, consistente, tratável, esforçado.
4. **Âncora**: ache o exemplo rotulado mais parecido em `exemplos-ouro.md` e decida T0–T3.
5. **Visual**: falta o que é preciso para responder? Sobra o que é decorativo?
6. **Vizinhos**: algum card do deck interfere com este? Os irmãos de cloze se entregam?

Depois, o nível do deck: órfãos, pares sem distinguidor, lentes faltando, ordem de introdução.

## 3. Saída
Grave `review.json` no formato de `references/rubrica.md`. Use `fix` com só os campos que mudam e
`split` com notas completas. Nunca proponha mudar o `id` de um card que fica. Termine com um
resumo de 3–5 linhas: contagem por veredito, os padrões de problema mais frequentes e o que falta
no deck.

Quem aplica as correções usa o script, para não reescrever a especificação de cabeça:
```bash
python3 scripts/apply_review.py DECK.cards.yaml review.json -o DECK.cards.yaml
```
Ele recusa `fix` que mude `id` e ids novos que colidam com existentes. Depois de aplicar, rode o
linter de novo. Cards `reject` sem `split` saem do deck e aparecem no resumo.

## Deck existente (.apkg)
Extraia com `scripts/apkg_to_spec.py`, rode os passos 1–3 e siga
`references/auditar-deck-existente.md` (inclui como migrar sem perder o histórico).

## Card que o aluno vive errando (leech)
Quase sempre é o card. Procure, nesta ordem:
- interferência com um vizinho (crie o distinguidor);
- `varias-respostas`;
- card grande demais (divida);
- falta de pré-requisito (crie o card do conceito anterior);
- falta de exemplo concreto.

Proponha a correção mantendo o `id`, para o histórico continuar.
