---
name: gerar-flashcards-anki
description: Gera um deck Anki completo e bonito para estudar Computação a partir de slides, PDFs, notas do Obsidian, código ou um tema — agents escrevem os cards (regras de Wozniak e Matuschak), um designer adiciona código com realce, diagramas, tabelas e esquemas, um revisor independente audita, e sai um .apkg para AnkiDroid com prévia, atualizável sem perder o histórico. Use quando o usuário pedir flashcards, cards do Anki, deck de revisão espaçada, "transformar esta aula/matéria em Anki" ou atualizar um deck já gerado — mesmo que não diga "Anki".
---

# Gerar flashcards Anki (orquestradora)

Coordena quatro skills especializadas e três agents. Cada skill faz uma coisa, e esta decide a
ordem e o que passa de uma para outra.

| skill | papel |
|---|---|
| `escrever-flashcards` | o que vira card e como a pergunta é redigida (Wozniak + Matuschak) |
| `visuais-de-flashcard` | código, diagramas, tabelas, esquemas, oclusão |
| `revisar-flashcards` | linter + revisão independente + aplicar correções |
| `montar-deck-anki` | build do `.apkg`, prévia, screenshots, atualização |

`SKILLS` = a pasta que contém esta skill e as irmãs (o pai do diretório desta skill). Os agents
ficam em `agents/` desta skill. Para lançar um, use a ferramenta Agent (tipo general-purpose) com o
prompt: "Leia `<SKILLS>/gerar-flashcards-anki/agents/<arquivo>.md` e siga as instruções.
Parâmetros: …", passando o caminho real de `SKILLS`.

## 0. Preparar
- Ambiente: `python3 <SKILLS>/montar-deck-anki/scripts/check_env.py`. Instale o obrigatório que faltar.
- Monte uma tabela de tarefas: entender e mapear → escrever → visuais → revisar → corrigir →
  build e prévia → entregar.

## 1. Entender o pedido (uma rodada de perguntas, no máximo)
Descubra lendo o que der: o material anexado, a pasta da matéria, um `.cards.yaml` ou
`.manifest.json` existente, e o `PLANO.md`/`notacao-do-professor.md`/`conceitos/` se for um workspace de
estudo criado pela skill `montar-estudo-para-prova`. Só pergunte o que falta e muda o resultado:
- matéria e nome do deck. Defina também o `namespace`, um slug que nunca mais muda;
- objetivo: prova (data, o que o professor disse que cai), projeto ou geral. Isso define `priority`;
- tamanho: o padrão é cobrir os pontos-chave com 2–3 ângulos por conceito central, e
  não um número fixo;
- onde salvar: a pasta `anki/` da matéria no vault, quando houver. Senão, entregue os arquivos.

**Deck que já existe:** leia a especificação e o manifesto. Fontes com hash igual são puladas;
gere só o que é novo ou mudou. Nunca mude `namespace` nem um `id` publicado.

## 2. Ler e mapear (Wozniak 1–3, 20)
Leia todo o material. Se houver slides e livro, os **slides vencem** (é o que cai). Escreva
`mapa.md` na pasta de trabalho com:
- os conceitos;
- os pré-requisitos de cada um;
- o peso na prova;
- os **pares confundíveis**;
- a notação do professor;
- o vocabulário do deck (termos preferidos e evitados, que vão para `terms:`);
- as lacunas da fonte.

Divida o material em seções de tamanho parecido (3–6) e dê a cada seção um prefixo de id
(`bd2-tx-iso-…`). No mapa, **cada conceito e cada par confundível tem um único dono** (uma seção).
Sem isso, escritores em paralelo escrevem cards quase iguais. No teste real, 2 de 32 cards eram
duplicatas entre seções.

Fixe também, no `mapa.md`, as **raízes de contexto** permitidas (ex.: `Heaps › …`) e a **grafia
da versão** (ex.: `CPython 3.13`). Três escritores sem essa regra produziram três raízes e quatro
grafias; o linter acusa `contexto-inconsistente` e `versao-inconsistente`.

Escreva `cabecalho.yaml` com `deck`, `namespace`, `context_root`, `lang`, `terms` e `sources`.

## 3. Escrever (agents em paralelo)
Lance **um `escritor-de-cards` por seção**, todos na mesma mensagem, para rodarem em paralelo.
Cada um recebe:
- `SKILLS`;
- o caminho do trecho da fonte;
- o `mapa.md`;
- a seção e o prefixo de id;
- o vocabulário, as raízes de contexto e a grafia da versão;
- os conceitos e pares de que a seção é dona (e os que são de outras seções, para não repetir);
- o objetivo e a prioridade;
- o arquivo de saída `fragmentos/<secao>.cards.yaml`;
- em atualização, os ids existentes daquela seção.

Junte os fragmentos:
```bash
python3 <SKILLS>/montar-deck-anki/scripts/merge_specs.py cabecalho.yaml fragmentos/*.cards.yaml \
  -o DECK.cards.yaml [--base DECK.cards.yaml]
```

## 4. Visuais
Lance um `designer-de-visuais` sobre `DECK.cards.yaml`. Para decks grandes, use um por seção, com
arquivos separados, e junte de novo. Ele edita a especificação no lugar, roda build e prévia e
corrige o layout.

## 5. Revisar (independente)
Rode o linter e gere os cards:
```bash
python3 <SKILLS>/revisar-flashcards/scripts/lint_cards.py DECK.cards.yaml --json .cc-build/lint.json
python3 <SKILLS>/montar-deck-anki/scripts/build_deck.py DECK.cards.yaml --check --work .cc-build
```
Lance um `revisor-de-cards` **novo**, que não viu a escrita. Ele recebe a especificação, o
`lint.json`, o `mapa.md` e os trechos da fonte, e grava `review.json`.

## 6. Corrigir (no máximo 2 rodadas)
```bash
python3 <SKILLS>/revisar-flashcards/scripts/apply_review.py DECK.cards.yaml review.json -o DECK.cards.yaml
```
- Para `split`s e lacunas do deck (órfãos, pares sem distinguidor), lance o escritor da seção de
  novo, passando os itens do `review.json`.
- Rode o linter de novo. Se ainda houver muitos `reject`, faça uma 2ª revisão só dos cards novos.
- Depois de 2 rodadas, siga em frente e liste o que ficou pendente.

## 7. Build, prévia e conferência visual
```bash
python3 <SKILLS>/montar-deck-anki/scripts/build_deck.py DECK.cards.yaml -o DECK.apkg --work .cc-build \
  --cards-json .cc-build/cards.json --manifest DECK.manifest.json
python3 <SKILLS>/montar-deck-anki/scripts/preview.py DECK.apkg --cards .cc-build/cards.json \
  -o .cc-build/previa --lint .cc-build/lint.json --title "<deck>"
```
**Olhe as folhas de contato**: abra cada PNG de `.cc-build/previa/folhas/`. Corrija todo problema
de layout e regenere. Se o deck tem mais de ~25 cards, confira além disso, com um agent separado,
uma amostra de 10 cards contra a fonte. O build imprime as notas que **saíram** da especificação;
guarde essa lista para o resumo.

## 8. Entregar
- Na pasta do deck: `DECK.cards.yaml` (fonte da verdade), `DECK.apkg`, `DECK.manifest.json` e
  `COMO-IMPORTAR.md` (copie de `<SKILLS>/montar-deck-anki/assets/`).
- A **galeria** (`.cc-build/previa/galeria.html`) publicada como artifact, para o aluno revisar no
  tablet antes de importar.
- O `.apkg` enviado ao aluno (SendUserFile).
- Resumo curto:
  - quantos cards, por tipo e por arquétipo;
  - os pares confundíveis cobertos;
  - as lacunas da fonte;
  - o que o revisor rejeitou e por quê, em uma linha;
  - em atualização: novos, atualizados e **os que ele deve apagar à mão** no Anki.
- Próximo passo: importar, ajustar as opções do deck (o FSRS está no `COMO-IMPORTAR.md`) e, depois
  de alguns dias, mandar os cards que viraram leech para reescrever.

## Regras que valem o tempo todo
- Fonte da verdade é a especificação. Não edite o `.apkg`, nem peça ao aluno para editar cards no
  Anki.
- Tudo que é executável foi executado: SQL, código, contas.
- Nenhum fato fora da fonte entregue sem verificação; o que não deu para verificar vira lacuna.
- Nenhuma pergunta de SQL sem o esquema na própria pergunta. Nenhum exemplo citado sem estar no card.
