# As 20 regras de Wozniak, operacionalizadas para Computação

Fonte: P. Wozniak, *Effective learning: Twenty rules of formulating knowledge* (SuperMemo, 1999) —
https://www.supermemo.com/en/blog/twenty-rules-of-formulating-knowledge

Cada regra traz: a ideia, um exemplo ruim → bom de CC e **a checagem** que você faz (ou que o
`lint_cards.py` faz, quando marcada com 🔧).

## Índice
1–3 compreensão e base · 4–5 mínimo de informação e cloze · 6–8 imagens, mnemônicos, oclusão ·
9–11 conjuntos, enumerações, interferência · 12–17 redação, contexto, redundância · 18–20 fonte, data, prioridade

---

### 1. Não aprenda o que você não entende
Decorar sem entender custa caro e não transfere.
- Ruim: card sobre "split de nó em B+tree" sem nenhum card antes sobre *por que* nós enchem.
- Checagem: todo termo usado na resposta é definido em outro card do deck ou é pré-requisito
  óbvio para o nível do aluno. Se não for, escreva o card do termo antes (e ponha em `prereqs`).

### 2. Aprenda antes de memorizar
Monte o quadro geral primeiro; depois quebre em itens.
- Checagem: antes de escrever cards, existe um `mapa.md` do tema (conceitos, pré-requisitos,
  pares confundíveis). Cada card tem `context` apontando para o lugar dele no mapa.

### 3. Construa sobre o básico
O básico é barato de manter e caro de esquecer.
- Checagem: `level: basic` para fundamentos; `prereqs` ligando o avançado ao básico. O build
  introduz os básicos primeiro (ordem topológica).

### 4. Princípio da informação mínima 🔧
Cada card pede a menor coisa possível. Card complexo é tão estável quanto sua parte mais fraca
e é revisado vezes demais.
- Ruim: "Explique o three-way handshake do TCP."
- Bom: "No handshake do TCP, o 1º segmento do cliente leva qual flag? → ==SYN=="
- Checagem: a resposta-chave cabe em ≤ 15 palavras (código e tabela não contam); o "porquê" vai
  em `extra`. Respostas com "e", ";" ou listas de 3+ itens → divida.

### 5. Cloze é fácil e eficaz
Transforme uma frase em lacuna.
- Bom: "SQL: `{{c1::HAVING}}` filtra grupos depois do GROUP BY."
- Checagem: o cloze esconde **o termo**, não a frase (≤ 5 palavras 🔧). A frase em volta não
  entrega a resposta por gramática. Em código, esconda um token ou expressão (≤ 30 caracteres 🔧),
  nunca atravessando linhas.

### 6. Use imagens
Material visual é lembrado melhor, mas custa mais para produzir.
- Checagem: tópicos estruturais (árvores, pilha de chamadas, ER, pipeline, estados) ganham
  diagrama. Diagrama decorativo, que não é necessário para responder, sai.

### 7. Use mnemônicos (com parcimônia)
Só ~1–5% dos itens precisam.
- Checagem: mnemônico vai em `extra` (ou entre parênteses na resposta), nunca é a resposta.

### 8. Oclusão gráfica é tão boa quanto cloze
Esconda uma região da imagem; uma figura rende 10–20 itens.
- Bom: esconder um campo do cabeçalho IPv4, uma entidade do ER, uma camada do OSI, um nó da árvore.
- Checagem: **uma região por card** (`type: occlusion` gera um card por alvo).

### 9. Evite conjuntos 🔧
Listas sem ordem são quase impossíveis de reter.
- Ruim: "Liste os princípios SOLID."
- Bom: "SOLID: o L significa? → ==Liskov Substitution==" (+ um card por letra + um card do porquê de cada).
- Checagem: pergunta com "liste", "quais são os…", "cite todos" → quebre.

### 10. Evite enumerações
Listas ordenadas são mais fáceis, mas ainda difíceis.
- Bom (cloze sobreposto): "OSI: Rede → ? → Sessão" (resposta: Transporte).
- Checagem: lista ordenada de N itens vira N cards, cada um mostrando 1–2 vizinhos de contexto.

### 11. Combata a interferência 🔧
Itens parecidos se confundem; é provavelmente a maior causa de esquecimento.
- Pares clássicos: `git reset` × `git revert`; `DELETE` × `TRUNCATE` × `DROP`; `==` × `===`;
  `list.sort()` × `sorted()`; `WHERE` × `HAVING`; chave candidata × primária; processo × thread.
- Checagem: para cada par confundível no `mapa.md`, escreva um **card distinguidor** (pergunta que
  só a diferença responde) e ligue os dois com `pair: [id-do-outro]`. A pergunta deve deixar o
  traço distintivo explícito.

### 12. Otimize a redação 🔧
Redação curta = recordação rápida e confiável.
- Checagem: pergunta ≤ 25 palavras de prosa. Corte "No contexto de…", "É importante notar que…",
  "Considerando o que foi visto…".

### 13. Ligue a memórias existentes
Ancore no que o aluno já sabe.
- Bom: "Como uma interface Java, uma interface Go é satisfeita… → ==implicitamente== (sem `implements`)."
- Checagem: quando houver um conceito anterior análogo, cite-o na pergunta ou no `extra`.

### 14. Personalize e dê exemplos
Exemplos pessoais resistem à interferência.
- Bom: usar o esquema da própria matéria (as tabelas `aluno`, `curso` do professor) em vez de `foo/bar`.
- Checagem: todo conceito abstrato tem pelo menos um card com exemplo concreto (linhas de
  exemplo, trecho de código real).

### 15. Apoie-se em emoção
Exemplos vívidos grudam.
- Bom (no `extra`): "o `DELETE` sem `WHERE` que apagou a produção".
- Checagem: opcional; vai em `extra`.

### 16. Dicas de contexto simplificam a redação 🔧
Um prefixo curto substitui frases inteiras e elimina significados concorrentes.
- Bom: o `context` "BD2 › Transações › Isolamento" aparece no topo do card.
- Checagem: todo card tem `context`. Siglas ambíguas (PK, CAP, DFS, ACK) exigem contexto. Pergunta
  não começa com pronome solto ("Isso…", "Este algoritmo…") 🔧.

### 17. Redundância não contradiz informação mínima
Vários cards simples sobre o mesmo fato, por ângulos diferentes, são bons.
- Formas: termo → definição e definição → termo; exemplo → classificação; causa → efeito;
  representação em código e em diagrama.
- Checagem: conceito central tem **2–3 cards de ângulos diferentes** (ver lentes em
  `principios-matuschak.md`). Card único de um conceito central é "órfão" 🔧.

### 18. Registre a fonte 🔧
Onde o conhecimento veio, como metadado, não como parte do que se aprende.
- Checagem: `source` + `at` ("slide 14"). Nunca "segundo o slide 14" dentro da pergunta 🔧.

### 19. Date o que é volátil 🔧
- Checagem: fatos que dependem de versão levam `version` ("PostgreSQL 16", "Python ≥ 3.10").
  APIs, flags e comportamento padrão de ferramentas mudam; teoria não.

### 20. Priorize
Priorize em todo estágio: fonte, extração, redação, retenção.
- Checagem: `priority` 1 (cai na prova / usa todo dia) a 3 (curiosidade). Peso da prova e o que
  o professor disse que cai mandam. Detalhe opcional vai em `extra` ou não vira card.
