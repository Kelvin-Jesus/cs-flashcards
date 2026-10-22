---
name: escrever-flashcards
description: Escreve flashcards de Computação seguindo as 20 regras de Wozniak e os princípios de Matuschak/Nielsen — escolhe o que vale virar card, aplica arquétipos de CC (prever saída, distinguidor, find-bug, cloze em código, oclusão…) e entrega no formato de especificação do deck. Use sempre que for criar, reescrever ou dividir cards de estudo (Anki ou não), inclusive quando outra skill ou um agent pedir "escreva os cards desta seção", "transforme este conteúdo em flashcards", "melhore estes cards" ou "faça perguntas de revisão espaçada".
---

# Escrever flashcards (Wozniak + Matuschak, para CC)

Esta skill decide **o que** vira card e **como** a pergunta é redigida. O visual (código, diagramas,
tabelas) é da skill `visuais-de-flashcard`; o empacotamento é da `montar-deck-anki`; a auditoria é
da `revisar-flashcards`. Os caminhos abaixo são relativos à pasta desta skill.

Antes de escrever, leia:
- `references/regras-wozniak.md` — as 20 regras com a checagem de cada uma
- `references/principios-matuschak.md` — 5 propriedades, tipos de prompt, lentes, erros de LLM
- `references/arquetipos-cc.md` — catálogo de arquétipos de Computação com exemplos
- `references/exemplos-ouro.md` — cards rotulados T0–T3 (calibre-se por eles)
- `../montar-deck-anki/references/formato-da-especificacao.md` — o formato YAML de saída

## Processo

### 1. Entender antes de escrever (Wozniak 1–2)
Leia a fonte inteira da seção. Se algo não fizer sentido para você, não vire card: anote como
lacuna. Se existir um `mapa.md` do tema (o orquestrador cria), use os conceitos, pré-requisitos e
pares confundíveis dele; se não existir, faça um mapa curto primeiro (conceitos → pré-requisitos →
pares que se confundem → o que tem mais peso na prova).

### 2. Escolher os alvos (Wozniak 20, Nielsen)
- Priorize o que **cai na prova / é usado no projeto**. `priority: 1` para isso.
- Regra de custo: só vira card o que vale ~10 minutos de revisão ao longo dos anos.
- Ponto de partida: 5–10 cards por seção nos pontos-chave; para cada conceito central, **2–3 cards
  de ângulos diferentes** (lentes). Material denso: ~1 card por 300–400 palavras como ordem de
  grandeza, não como meta.
- Não card: trivia, flags raras que se consultam, código inteiro para decorar, o que o aluno já
  domina.

### 3. Escolher o arquétipo de cada alvo
Para cada alvo, pergunte qual tarefa de recuperação treina o que importa:
fato isolado → `definition`/cloze; diferença entre parecidos → `distinguisher` (com `pair`);
algoritmo → `trace-step`, `complexity-why`, `complete-code`; código → `predict-output` (com
variações), `find-bug`; decisão → `when-to-use`, `design-why`; procedimento → `procedure-condition`;
figura estrutural → `diagram-occlusion`; comando → `command` (`type: type`).
Evite deixar um conceito só com `definition` (o vício de LLM descrito em `principios-matuschak.md`).

### 4. Redigir (as cinco propriedades)
- **Uma resposta só.** Se duas respostas razoáveis cabem, restrinja (pior caso? em PostgreSQL? no
  modelo do professor?).
- **Pergunta ≤ 25 palavras de prosa**, sem enchimento. Código, esquema e tabela não contam.
- **Resposta-chave ≤ 15 palavras**, marcada com `==marca-texto==`; o porquê vai em `extra`.
- **Nada de sim/não**: reescreva com qual/como/por que/quando. "A ou B?" só em distinguidor.
- **Nada de lista**: um card por membro; lista ordenada → clozes sobrepostos com vizinhos.
- **Sem vazamento**: nenhuma palavra da resposta na pergunta; a dica estreita, não entrega.
- **Contexto sempre** (`context: "Área › Tópico"`); nunca comece com pronome solto.
- **Sem provincianismo**: "slide 12" vai em `at`, não na pergunta.
- **Terminologia travada**: use o vocabulário do deck (`terms:` na especificação). Em PT-BR com
  termos técnicos em inglês quando é assim que o professor e o mercado falam (`commit`, `deadlock`);
  escolha uma forma e mantenha no deck inteiro.
- **Preserve ressalvas**: "pode", "em geral", "no pior caso" da fonte não viram "é".

### 5. Tudo que é executável é executado
Código, SQL e contas de `predict-output`, `trace-step`, `sql-result`, `edge-case`: rode antes de
escrever a resposta (Python/sqlite3 no shell; outra linguagem, se disponível) e cole o resultado
real. Valores inventados para ilustrar ganham "(ilustrativo)" no `extra`. Fato que você não conseguiu
verificar na fonte entregue: não escreva, ou registre como lacuna.

### 6. Metadados que o build e a revisão usam
`id` (slug estável, **nunca renomeie um id publicado**), `context`, `level` (basic|core|advanced),
`priority` (1–3), `prereqs`, `pair`, `archetype`, `source` + `at`, `version` (fatos que mudam com
versão), `tags`. Ids com o prefixo da seção que você recebeu, para não colidir com outros escritores.

### 7. Autoconferência antes de entregar
Rode o linter no seu fragmento e corrija todo `warn` (ou, se for intencional, justifique em `lint_ignore: ["codigo: motivo"]` na nota):
```bash
python3 ../revisar-flashcards/scripts/lint_cards.py SEU-FRAGMENTO.cards.yaml
```
Depois, para cada card, faça mentalmente as cinco perguntas: focado? preciso? consistente?
tratável? esforçado? Compare com `exemplos-ouro.md`. Um card T1/T0 não sai.

## Saída
Um arquivo YAML com `notes:` (e `sources:`/`terms:` novos, se houver), no formato da
especificação. Ao terminar, informe: quantos cards por arquétipo, pares confundíveis cobertos,
lacunas (o que não entendeu ou não conseguiu verificar) e cards que você descartou e por quê.
