---
name: visuais-de-flashcard
description: Decide quando um flashcard precisa de visual e produz o visual certo — código com realce e linhas marcadas, tabelas com dados de exemplo, esquema relacional na pergunta, diagramas Graphviz/SVG (árvores, grafos, ER, autômatos, pilhas, listas, hash, sequência TCP, grafo de commits), oclusão de diagrama — legíveis no celular e no tema escuro do AnkiDroid. Use sempre que for enriquecer cards de estudo com código, diagramas ou tabelas, transformar uma figura de slide em card, ou quando um card de CC "precisa ser mais visual".
---

# Visuais de flashcard

O visual existe para **responder ou entender a pergunta**, não para enfeitar (Wozniak 6). Esta skill
escolhe o visual, escreve o bloco no formato da especificação e confere que ele fica legível.

Referências (relativas à pasta desta skill):
- `examples/catalogo.cards.yaml` — 14 modelos prontos e conferidos em 390/800/1280 px, claro e escuro:
  lista ligada, pilha de chamadas, hash com encadeamento, BFS, AFD, estados de processo, handshake
  TCP (SVG à mão com oclusão), grafo de commits, heap a partir do vetor, tabela de DP, normalização, junção SQL, OSI com oclusão.
  Copie o mais próximo e adapte.
- `../montar-deck-anki/references/formato-da-especificacao.md` — sintaxe de todos os blocos
  (opções de código, `dot`, `tree`, `schema`, `svg`, `mermaid`, cores semânticas, oclusão).

## Quando pôr visual (e qual)

| O card fala de… | Visual | Por quê |
|---|---|---|
| consulta SQL, junção, agregação | ```schema **na pergunta** + tabela com linhas reais | sem esquema, não dá para saber quais colunas existem onde (preferência do aluno) |
| saída de código, bug, trecho a completar | bloco de código ≤ 10 linhas; `err=`/`ok=`/`hl=` quando ajudam | a tarefa é ler código; prosa descrevendo código é pior |
| estado de algoritmo (ordenação, DP, busca) | tabela ou vetor antes → depois | mostra a transformação de um passo |
| heap / árvore completa guardada em vetor | ```heap (do vetor, com `show=vk` para índice) | a relação índice ↔ posição é o que se estuda |
| árvore (BST, AVL, trie) | ```tree (compacto) ou `dot` | estrutura espacial |
| grafo, autômato, estados, fluxo | `dot` | relações |
| ER, modelo conceitual | `dot` com a **notação do professor** | a prova usa a notação dele |
| protocolo, troca de mensagens | `svg` à mão (diagrama de sequência) | o `dot` não faz linha do tempo bem |
| camadas, cabeçalho, figura com partes | `type: occlusion` | uma região por card (Wozniak 8) |
| complexidade, fórmula | matemática `\( \)` | MathJax nativo |
| definição, fato isolado, comando | **nada** | visual só atrasaria |

Se o card **cita** um exemplo, figura ou tabela ("como no slide 10", "na Fig. 5.16"), o visual
citado aparece **no próprio card**. Valores inventados levam "(ilustrativo)" no `extra`.

## Regras de legibilidade (aprendidas com screenshots reais a 390 px)

1. **Diagrama estreito.** O card tem ~360 px úteis no celular. Prefira `rankdir=TB`; com `LR`,
   no máximo ~5 nós por linha. O preview avisa quando o texto do diagrama fica abaixo de 12 px.
2. **Graphviz `record` com `rankdir=LR` empilha os campos na vertical**: use `label="{10|<p>}"`
   (chaves) para manter na horizontal.
3. **Heaps e árvores em vetor**: use ```heap com o vetor real (posições fixas; até ~15 nós
   cabem a 390 px). Mostre índice (`show=k`/`vk`) quando a pergunta for sobre índice; na frente
   de um rastreio, só o estado inicial, sem destaque. **Outras árvores binárias**: use ```tree. Ele já põe nós invisíveis para esquerda/direita ficarem
   simétricas. `*` destaca, `?` esconde o rótulo.
4. **Código ≤ ~42 caracteres por linha** no celular. Quebre consultas SQL em várias linhas. O bloco
   rola, mas o preview avisa, porque rolar no meio da revisão atrapalha.
5. **Pergunta primeiro, apoio depois.** Só o 1º parágrafo da frente é a pergunta (em negrito
   grande); dados, dependências e esquema vêm depois e saem em peso normal.
6. **Cores só semânticas** (`@accent`, `@alert`, `@ok`, `@mark`, `@muted`, `@accent-soft`). Nunca
   `red` ou `#hex`, que ficam ilegíveis no tema escuro. Em SVG à mão, use `currentColor` para o traço.
7. **Destaque não pode entregar a resposta.** Em "qual é o bug?", não marque a linha com `err=`.
   Num cloze com vários buracos, não use `hl=`: o destaque aponta para a linha errada nos irmãos.
8. **Um visual por card**, a não ser que a pergunta compare dois (antes × depois).
9. **Mermaid é último recurso.** Exige Chromium e não deixa usar oclusão nem cores semânticas
   completas; `dot` faz grafo, ER, estados e fluxo.
10. **Oclusão não pode ser deduzível pelos vizinhos.** Rótulos em sequência (índices 0…14,
    camadas numeradas) respondem-se contando, sem lembrar nada: o revisor rejeitou exatamente isso
    no teste. Oclua o que exige memória (nome da camada, campo do cabeçalho, entidade do ER) ou
    troque por uma pergunta de fórmula ("pai do índice 10?").
11. **Imagem de slide** (PNG): só se o diagrama não puder ser redesenhado em `dot`/`svg`.
    Redesenhar dá tema escuro, nitidez e oclusão; a imagem não dá nada disso.

## Processo

1. Leia a especificação (ou fragmento) e, para cada card, decida pela tabela acima. Na dúvida,
   **sem visual**.
2. Escreva o bloco copiando o modelo mais próximo do catálogo. Mantenha `id`, pergunta e resposta.
   Se o visual muda o que a pergunta pede, avise quem escreveu em vez de reescrever o card sozinho.
3. Para código, SQL e algoritmo: **execute** e confira que o visual e a resposta batem
   (o SQL do catálogo foi rodado em sqlite3).
4. Valide e veja:
   ```bash
   python3 ../montar-deck-anki/scripts/build_deck.py SPEC.cards.yaml -o /tmp/v.apkg --work .cc-build --cards-json .cc-build/cards.json
   python3 ../montar-deck-anki/scripts/preview.py /tmp/v.apkg --cards .cc-build/cards.json -o .cc-build/previa
   ```
   Corrija todo aviso de layout. Depois **abra as folhas de contato** (`.cc-build/previa/folhas/*.png`)
   e olhe frente e verso, claro e escuro. Confira três coisas: o diagrama se lê sem zoom? o destaque
   está no lugar certo? a oclusão esconde só o alvo?
5. Reporte quais cards ganharam visual, quais você deixou sem e por quê.
