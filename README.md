<p align="center"><img src=".claude-plugin/icon.png" alt="Ícone do cs-flashcards" width="160"></p>

# cs-flashcards — Flashcards de Computação

Flashcards Anki bonitos para estudar Computação. Os cards são escritos por agents seguindo as
**20 regras de Wozniak** e os **princípios de Matuschak/Nielsen**, ganham código com realce,
diagramas, tabelas e esquemas, passam por um revisor independente e saem como `.apkg` para
AnkiDroid/Anki. Dá para atualizar o deck sem perder o histórico de revisão.

## Como usar
Peça, por exemplo: *"gere flashcards da aula 05 de BD2"*, *"transforme esta pasta em deck Anki"*,
*"atualize o deck de BD2 com a aula nova"* ou *"audite meu deck antigo"*.

## Skills
| skill | faz |
|---|---|
| `gerar-flashcards-anki` | orquestra tudo (entender → mapear → escrever → visuais → revisar → corrigir → build → entregar) |
| `escrever-flashcards` | o que vira card e como perguntar: regras de Wozniak e Matuschak, arquétipos de CC, exemplos rotulados |
| `visuais-de-flashcard` | quando e qual visual; catálogo de 14 modelos conferidos em celular e tema escuro |
| `revisar-flashcards` | linter determinístico, rubrica com exemplos rotulados, checagem de fatos, aplicação de correções, auditoria de `.apkg` antigo |
| `montar-deck-anki` | especificação YAML → `.apkg`, prévia com screenshots e checagem de layout, atualização segura |

## Agents
`escritor-de-cards` (um por seção, em paralelo), `designer-de-visuais` e `revisor-de-cards`
(revisa o que não escreveu). Os prompts ficam em `skills/gerar-flashcards-anki/agents/`, para
funcionar no app do Claude, e em `agents/`, para o Claude Code.

## O que o card suporta
- Código em qualquer linguagem do Pygments, com linhas destacadas, linha de erro e de acerto, foco,
  diff e **cloze dentro do código**.
- Diagramas Graphviz e SVG que acompanham o tema claro/escuro, com cores semânticas.
- Árvores binárias em notação compacta e esquema relacional com PK sublinhada.
- **Oclusão de diagrama**: um nó ou região por card.
- Matemática (MathJax nativo), tabelas com dados de exemplo, "digitar a resposta" para comandos,
  dica de toque, breadcrumb de contexto, fonte e versão no rodapé.
- Fontes embutidas: Atkinson Hyperlegible Next e JetBrains Mono, ambas OFL, com ligaduras
  desligadas no código.

## Dependências
`python3 skills/montar-deck-anki/scripts/check_env.py` diz o que falta. O mínimo é
`pip install genanki pygments markdown-it-py pyyaml lxml`, mais `graphviz` para diagramas.
Recomendado: `anki`, `playwright` e Chromium, para a prévia fiel e os screenshots.
Detalhes por ambiente, incluindo o tablet Android, em `skills/montar-deck-anki/references/instalacao.md`.

## O que este plugin executa e acessa

Nada roda sozinho: tudo abaixo só acontece quando você pede um deck, uma prévia ou uma auditoria.

**Scripts Python locais** (em `skills/*/scripts/`), executados na sua máquina ou no ambiente de código do Claude:
- `build_deck.py`, `cardrender.py`, `merge_specs.py` leem a especificação `*.cards.yaml` e os arquivos-fonte que
  você indicar e gravam o `.apkg` e o manifesto na pasta de saída que você escolher.
- `lint_cards.py`, `apply_review.py` e `apkg_to_spec.py` leem e gravam apenas as especificações e os `.apkg`
  que você passar como argumento (incluindo o `review.json`).
- `preview.py` gera screenshots, folhas de contato e `galeria.html`.
- `check_env.py` só verifica quais dependências estão instaladas.
- Arquivos temporários ficam no diretório temporário do sistema (`ccprev-*`, `cardrender-cache`).

**Programas externos chamados por esses scripts**
- `dot` (Graphviz), para os diagramas `dot` e `tree`.
- Chromium headless (via Playwright), para screenshots e checagem de layout da prévia. As páginas são abertas
  como arquivos locais (`file://`).
- `mmdc` (Mermaid CLI) e `npm root -g`, só se você usar blocos `mermaid` ou a matemática nos screenshots.

**Instalação de dependências.** O plugin **não instala nada por conta própria**. `check_env.py` e
`skills/montar-deck-anki/references/instalacao.md` apenas *sugerem* comandos `pip install`, `apt install`,
`playwright install` e `npm i -g` para você (ou o Claude, com a sua aprovação) executar. Não há `npx`, `uvx`
nem download automático de código.

**Rede.** Os scripts não fazem requisições. A única referência de rede é na `galeria.html`, que carrega o
MathJax 3.2.2 de `cdnjs.cloudflare.com` quando você a abre no navegador, para exibir fórmulas. Sem internet,
a galeria funciona, só que as fórmulas aparecem como texto TeX.

**Dados.** O plugin não coleta, envia nem guarda nada fora da sua máquina. Não usa credenciais, chaves de API
nem conectores.

## Testes
```bash
python3 skills/revisar-flashcards/tests/test_lint.py      # o linter pega 10 defeitos plantados, sem falso positivo
python3 skills/montar-deck-anki/tests/test_update.py      # reimportar atualiza sem duplicar e preserva o histórico
```

## Licença e marcas
Código sob licença MIT (veja `LICENSE`). As fontes embutidas seguem a SIL OFL 1.1, em
`skills/montar-deck-anki/assets/fonts/OFL-*.txt`.

Projeto independente: não é afiliado, patrocinado nem endossado pelos mantenedores do Anki ou do AnkiDroid.
"Anki" e "AnkiDroid" são nomes de seus respectivos titulares e aparecem aqui só para indicar o formato de
arquivo (`.apkg`) e os aplicativos compatíveis.
