---
name: montar-deck-anki
description: Transforma uma especificação de cards (.cards.yaml) num deck .apkg bonito e funcional para Anki/AnkiDroid — código com realce, cloze dentro de código, diagramas SVG que acompanham o tema escuro, esquemas relacionais, árvores, oclusão de diagrama, matemática — com GUIDs estáveis para atualizar sem perder o histórico, mais prévia com screenshots e checagem de layout em celular/tablet. Use sempre que precisar gerar, regenerar, atualizar ou pré-visualizar um deck Anki, ou empacotar cards escritos por outra skill.
---

# Montar deck Anki

Scripts em `scripts/` (caminhos relativos à pasta desta skill). A especificação é a fonte da
verdade; o `.apkg` é derivado e sempre pode ser regenerado.

Leia conforme a necessidade:
- `references/formato-da-especificacao.md`: todos os campos, tipos, blocos de código e diagramas.
- `references/atualizacoes.md`: o que **nunca** mudar (namespace, ids, note types) e o fluxo de atualização.
- `references/instalacao.md`: dependências por ambiente (nuvem, tablet Android, Mac).
- `examples/exemplo-cc.cards.yaml`: um card de cada tipo, para copiar o formato.

## 0. Ambiente
```bash
python3 scripts/check_env.py
```
Instale o obrigatório que faltar (ele imprime o comando). Sem Graphviz, blocos `dot`/`tree` falham.
Nesse caso use `svg` escrito à mão. Sem `anki` + Playwright, a prévia sai sem screenshots, e você
precisa dizer isso ao usuário.

## 1. Validar e renderizar (rápido, sem gerar .apkg)
```bash
python3 scripts/build_deck.py DECK.cards.yaml --check --work .cc-build
```
Erros apontam a nota e o problema: id duplicado, prereq inexistente, cloze sem marcador, alvo de
oclusão não encontrado, SVG inválido, Graphviz falhou. Corrija na especificação e repita.

## 2. Gerar o pacote
```bash
python3 scripts/build_deck.py DECK.cards.yaml -o DECK.apkg --work .cc-build \
  --cards-json .cc-build/cards.json --report .cc-build/report.json --manifest DECK.manifest.json
```
- Guarde o `DECK.manifest.json` ao lado da especificação. No próximo build ele informa as notas
  novas, as que **saíram** (o usuário precisa apagá-las à mão no Anki) e as fontes alteradas.
- Para juntar fragmentos de vários escritores, ou aplicar mudanças sobre um deck publicado, use
  `scripts/merge_specs.py` (detalhes em `references/atualizacoes.md`).

## 3. Prévia e checagem visual (sempre, antes de entregar)
```bash
python3 scripts/preview.py DECK.apkg --cards .cc-build/cards.json -o .cc-build/previa \
  [--lint .cc-build/lint.json] [--sample 8] [--all-shots]
```
O script faz quatro coisas:
- renderiza cada card com o **próprio Anki** (pacote `anki`), ou com um renderizador equivalente;
- confere em 390, 800 e 1280 px, nos temas claro e escuro: rolagem horizontal da página,
  elemento vazando, fonte que não carregou, sintaxe `{{c…` ou `[[type:` sobrando, contraste da
  pergunta, texto de diagrama menor que 12 px e card longo demais (mais de 2,2 telas);
- grava `layout.json` e folhas de contato em `folhas/*.png`;
- gera `galeria.html`, uma página única para revisar o deck (frente e verso, claro e escuro,
  celular/tablet/desktop, filtro "só com aviso").

**Olhe as folhas** (Read em cada PNG): o checador mecânico não vê um diagrama confuso ou um
destaque no lugar errado. Corrija todo problema de layout e regenere. Os problemas comuns e as
correções estão em `../visuais-de-flashcard/SKILL.md`.

## 4. Testar a atualização (quando mexer em build_deck.py ou nos note types)
```bash
python3 tests/test_update.py
```
Importa a v1, revisa um card, muda um texto e acrescenta uma nota, importa a v2. Confere que nada
duplicou, que o texto mudou e que o histórico ficou.

## Entrega
- `DECK.apkg` + `DECK.cards.yaml` + `DECK.manifest.json` na pasta do deck (no vault, quando houver).
- `assets/COMO-IMPORTAR.md` copiado para a mesma pasta. Ele traz o import no AnkiDroid/desktop e
  as opções de FSRS recomendadas, que **não** dá para gravar no `.apkg`.
- A galeria publicada como artifact, para o usuário revisar no tablet antes de importar. Quando
  não houver ferramenta de artifact, envie o `galeria.html`.

## O que não fazer
- Não mude `namespace`, `id` publicado, `MODEL_*_ID` nem a lista de campos.
- Não use cores fixas em diagramas; use as cores semânticas `@accent`, `@alert` etc.
- Não use imagem remota: não funciona offline no AnkiDroid.
- Não mande para o Anki HTML escrito à mão nos campos. Tudo passa pelo `cardrender.py`, que
  escapa o HTML e protege o cloze.
