# Exemplos rotulados (padrão-ouro)

Usados pelo escritor (para calibrar) e pelo revisor (como âncora de julgamento). No estudo de
Kirkby & Matuschak (2026), dar exemplos rotulados ao juiz subiu a precisão de 56% para 78%.

**Níveis**
- **T3 pronto**: passa nas cinco propriedades.
- **T2 usável mas prolixo**: dá para estudar, mas tem palavras ou partes demais.
- **T1 ambíguo**: admite várias respostas, ou falta contexto.
- **T0 fora do alvo**: trivial, errado, não testa o que importa, ou é decoreba de código.

**Códigos de motivo** (os mesmos do revisor): `falta-contexto`, `varias-respostas`, `raso`,
`prolixo`, `estreito`, `vazamento`, `sim-nao`, `conjunto`, `interferencia`, `fato-nao-verificado`,
`visual-ausente`, `visual-decorativo`, `decoreba`, `provincial`.

---

## T3 — prontos

1. **"SQL › Agregação". Que cláusula filtra grupos depois do `GROUP BY`?** → ==`HAVING`==
   (o esquema `pedido(*id, cliente, valor)` aparece na pergunta)
   Por que é T3: focado, com uma resposta só, e o contexto elimina outros sentidos.

2. **"Git › Desfazer". Desfazer um commit já enviado sem reescrever o histórico: `reset` ou `revert`?** → ==`revert`==
   Por que é T3: é um distinguidor de par confundível, ligado a `git-reset-uso` por `pair`.

3. **"Python › Fatiamento". O que imprime `[10, 20, 30, 40, 50][-3:-1]`?** → ==`[30, 40]`==
   Por que é T3: é aplicação, a saída foi executada, e há 4 variações no deck.

4. **"BD › Normalização". O que dispara a passagem da 2FN para a 3FN?** → ==dependência transitiva==
   Por que é T3: pergunta procedural de condição, não "qual o passo 3".

5. **Oclusão no diagrama ER: qual entidade está escondida?** (um alvo por card) → ==Matrícula==
   Por que é T3: Wozniak 8, uma região por card.

## T2 — usáveis, mas prolixos

6. **"No contexto de bancos de dados relacionais, considerando o que vimos sobre agregação, qual a cláusula que serve para filtrar os grupos?"** → HAVING
   Motivo: `prolixo`.
   Reescrita: o card 1.

7. **"Por que a busca binária é O(log n)?"** → "Porque a cada iteração do laço o algoritmo compara o elemento do meio com o alvo e, dependendo do resultado, descarta a metade esquerda ou a direita, de modo que o tamanho do intervalo cai pela metade até sobrar um elemento, o que leva log₂ n passos."
   Motivo: `prolixo` (a resposta tem 45 palavras).
   Reescrita: "Cada passo ==descarta metade== do intervalo; só dá para dividir \(\log_2 n\) vezes."

## T1 — ambíguos

8. **"O que é normalização?"**
   Motivo: `varias-respostas`, `raso`.
   Reescrita: dividir em cards pelas lentes. Exemplos: "Normalização elimina que tipo de anomalia ao atualizar? → ==anomalia de atualização==" e "Qual o objetivo de decompor uma relação na normalização? → ==reduzir redundância==".

9. **"Dê um exemplo de deadlock."**
   Motivo: `varias-respostas` (é inconsistente).
   Reescrita: classify-example ("2 threads, cada uma com um lock esperando o lock da outra: que situação é essa? → deadlock"), ou marcar `archetype: creative`.

10. **"Qual a complexidade?"** com um trecho de código, mas sem dizer se é melhor caso, pior caso ou médio.
    Motivo: `varias-respostas`, `falta-contexto`.
    Reescrita: "Qual o custo **no pior caso**…?"

11. **"Isso roda antes ou depois do GROUP BY?"**
    Motivo: `falta-contexto`, já que "isso" não tem referente.
    Reescrita: "Em SQL, o `WHERE` é avaliado antes ou depois do `GROUP BY`?" (aqui "antes ou depois" é discriminação, não sim/não).

12. **"Qual o resultado?"** com `SELECT nome FROM aluno WHERE curso_id = 2;`, mas sem tabela nem esquema.
    Motivo: `falta-contexto`, `visual-ausente`. É impossível responder.
    Reescrita: incluir ```schema e as linhas de exemplo na pergunta.

13. **"É possível usar HAVING sem GROUP BY?"**
    Motivo: `sim-nao`. Acerta-se no chute com 50%.
    Reescrita: "Sem `GROUP BY`, sobre qual conjunto o `HAVING` filtra? → ==a tabela inteira como um grupo só==".

14. **"Quais são as propriedades ACID?"**
    Motivo: `conjunto`.
    Reescrita: um card por letra ("ACID: o I garante o quê?") e um card por porquê.

15. Dois cards, **"O que `git reset` faz?"** e **"O que `git revert` faz?"**, sem nada que marque a diferença.
    Motivo: `interferencia`.
    Reescrita: distinguidores como o card 2, ligados por `pair`.

## T0 — fora do alvo

16. **"Em que ano foi criado o SQL?"** (sem que a prova peça isso)
    Motivo: `raso`, trivia.
    Ação: não criar, porque não vale 10 minutos de revisão.

17. **Cloze escondendo a função inteira de 12 linhas da busca binária.**
    Motivo: `decoreba`.
    Reescrita: esconder um token (`lo <= hi`, `meio + 1`).

18. **"A cláusula HAVING filtra grupos. Que cláusula filtra grupos?"**
    Motivo: `vazamento`, a resposta está na pergunta.

19. **"Segundo o slide 12, qual índice o professor recomendou?"**
    Motivo: `provincial`.
    Reescrita: enunciar o fato geral e pôr o slide em `source`/`at`.

20. **"PostgreSQL: o nível de isolamento padrão é SERIALIZABLE."**
    Motivo: `fato-nao-verificado`. O padrão é READ COMMITTED, e sem `version` o card ainda envelhece.
    Ação: conferir na fonte e adicionar `version`.

21. **Diagrama colorido de uma "nuvem de banco de dados" no card "Qual cláusula filtra grupos?"**
    Motivo: `visual-decorativo`, porque a resposta não depende do desenho.
    Ação: remover o diagrama.

22. **Oclusão de um índice numa árvore com rótulos 0…14 em sequência.** O aluno responde contando os vizinhos, sem lembrar nada.
    Motivo: `raso` (falso positivo).
    Reescrita: perguntar pela fórmula ("pai do índice 10 num heap base 0? → ==4==, `(10-1)>>1`") ou ocluir algo que não se deduz dos vizinhos.

23. **Dois escritores, dois cards: "Por que `heapify` é melhor que `heappush` repetido?" e "Montar heap com a lista inteira: qual função?"**
    Motivo: `interferencia` (é o mesmo alvo por dois caminhos, sem `pair`).
    Ação: fundir num card só, ou transformar num par distinguidor explícito (lista pronta × itens chegando um a um).
