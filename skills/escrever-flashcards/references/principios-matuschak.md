# Princípios de Matuschak (e Nielsen) para prompts que geram entendimento

Fontes: A. Matuschak, *How to write good prompts* (https://andymatuschak.org/prompts/) e notas em
notes.andymatuschak.org; M. Nielsen, *Augmenting Long-term Memory* (http://augmentingcognition.com/ltm.html);
Kirkby & Matuschak, *Evaluating LLM-generated flashcards* (memory-machines.com/report, 2026).

Ideia central: escrever um prompt é **projetar uma tarefa** que o seu eu futuro vai repetir. O
ganho vem do esforço de recuperar, não de reler. Respostas inconsistentes enfraquecem memórias
vizinhas.

## As cinco propriedades (todo card precisa das cinco)

| Propriedade | Teste | Falha típica em CC |
|---|---|---|
| **Focado** | um detalhe por card | "Explique normalização" |
| **Preciso** | a pergunta diz exatamente o que se quer | "Por que usar índice?" quando o certo é "Que operação um índice B-tree acelera que um hash não acelera?" |
| **Consistente** | mesma resposta em toda revisão | "Dê um exemplo de deadlock" (cada vez um) |
| **Tratável** | você quase sempre consegue responder (~90%) | card que exige reconstruir uma prova inteira |
| **Esforçado** | a dica estreita, não entrega | a palavra da resposta aparece na pergunta |

**Uma resposta só.** Se duas respostas razoáveis cabem, o card está vago: escolha um ângulo que
tenha uma resposta só (o exemplo da omelete: "primeiro passo?" tem várias respostas; "como a
frigideira deve estar antes dos ovos?" tem uma).

## Tipos de prompt

- **Factual**: um detalhe. "Porta padrão do PostgreSQL? → ==5432=="
- **Explicação**: "como/por que", redigido para só uma explicação caber.
  "Por que a busca binária exige vetor ordenado? → porque ==descarta metade== comparando com o meio"
- **Lista fechada**: um buraco por card, lista sempre na mesma ordem (para aprender a "forma").
  Depois, um card integrador e um "por que este item está na lista".
- **Lista aberta** (cresce, tipo tags): três tipos. Instância → categoria ("`useMemo` é exemplo de? →
  memoização"), perguntas sobre a categoria, e categoria → exemplos (frágil sozinho).
- **Procedural**: guarde só as palavras que carregam o detalhe crítico e transforme cada uma em
  pergunta. Pergunte **as condições** que disparam cada passo, as **ramificações** e o **porquê**
  dos passos importantes. Pule o óbvio para o nível do aluno.
  "Antes de `git rebase` num branch compartilhado, verificar o quê? → ==se alguém já puxou o branch=="
- **Conceitual: as cinco lentes.** Use como caixa de ferramentas; cada conceito central ganha 2–3:
  1. *atributos e tendências*: o que é sempre/às vezes/nunca verdade
     ("Toda relação em 3FN está em 2FN? → reformule: Que forma normal é pré-requisito da 3FN? → 2FN")
  2. *semelhanças e diferenças*: "índice hash × B-tree: qual suporta busca por intervalo?"
  3. *partes e todo*: exemplos, subconceitos, categoria maior
  4. *causas e efeitos*: o que faz, o que não faz, quando se usa
  5. *significado e implicações*: por que importa, o que muda na prática
- **Saliência**: mantém uma ideia em mente para ela ser aplicada, redigida com o contexto onde se
  aplica. "Log do ORM mostra N consultas iguais dentro de um laço: o que suspeitar? → ==N+1=="
- **Criativo/generativo**: pede uma resposta nova a cada vez ("escreva uma consulta com função de
  janela que você ainda não usou"). Isentos da regra de consistência: marque `archetype: creative`.
- **Aplicação** (prever saída, calcular): viram decoreba se repetidos idênticos. Faça **~5 variações**
  (mude valores, ordem, um operador) e ligue por `context` igual.

## Regras de prática

- **Escreva mais prompts do que parece natural.** Prompts grossos não reduzem o que há para
  aprender; só tornam a revisão mais difícil. Nielsen: pelo menos 2–3 cards por ideia; 5–20 por
  artigo; algumas dezenas por teorema.
- **Comece com 5–10 por seção, no que importa**, e acrescente em passadas seguintes. Não persiga
  completude.
- **Menos cards para o que o aluno já domina**; mais para o que é novo e difícil.
- **Frustração na revisão = card ruim.** Revise o card (e os vizinhos), não o aluno.
- **Custo**: um card custa ~5–10 min de revisão ao longo dos anos. Só vale se o fato valer isso.
- **Ligue cards a um uso real** (a prova, o projeto). Cards "para algum dia" são frios.
- **Programação**: cards não constroem habilidade sozinhos. Rode o exemplo, mexa nele, e então
  card o que você precisou procurar ou errou (Janki: depois de cada erro, escreva o card que o
  teria evitado).

## Testes de fumaça (falsos positivos e falsos negativos)

- **Falso positivo** (acerta sem saber): pergunta longa ou de formato único que se reconhece pela
  forma; pergunta binária; cloze colado do texto-fonte. → Encurte, varie a forma, reescreva com
  palavras próprias.
- **Falso negativo** (sabe, mas erra): contexto de menos, outras respostas parecem válidas. →
  Acrescente contexto ou restrinja ("em PostgreSQL", "no modelo do professor").
- **Provincianismo**: amarrar conhecimento geral a uma fonte ("no exemplo da aula…"). Enuncie o geral
  de forma geral; a fonte vai no metadado.
- **Forma única no deck**: se só um card começa com "Quem…?", qualquer "Quem" puxa a mesma
  resposta (Quantum Country). Varie as formas.

## O que LLMs erram ao gerar cards (Kirkby & Matuschak 2026; Matuschak 2023)

1. A falha dominante é de **construção**, não de alvo: mesmo o melhor modelo testado teve ~36% de
   cards inutilizáveis. Os rótulos que mais pesam: *falta contexto*, *admite várias respostas*,
   *raso*, *prolixo*, *estreito demais*.
2. LLMs julgam bem "falta contexto", mas **julgam mal "várias respostas" e "prolixo"**. Por isso
   essas duas viram checagem determinística (`lint_cards.py`) e o revisor recebe **exemplos
   rotulados** (`exemplos-ouro.md`), que no estudo subiram a precisão do juiz de 56% para 78%.
3. Em material conceitual, LLMs tendem a só fazer termo ↔ definição. Faltam: classificar
   exemplos, gerar exemplos, aplicação, ligações, propósito. Use as lentes de propósito.
4. "Pode ser" vira "é" sem ninguém perceber. Preserve as ressalvas da fonte.
5. Fatos inventados: só escreva o que está na fonte entregue ou o que você executou/verificou.
