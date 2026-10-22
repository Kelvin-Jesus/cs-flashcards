# Arquétipos de card para Computação

Cada arquétipo tem quando usar, a armadilha e um exemplo no formato da especificação
(`montar-deck-anki/references/formato-da-especificacao.md`). Marque o arquétipo em
`archetype:`: ele vira tag (`cc::arq::...`) e o revisor usa para conferir as regras certas.

Os exemplos abaixo são curtos de propósito. As regras visuais (quando pôr diagrama, tabela,
esquema) estão na skill `visuais-de-flashcard`.

## Índice
definition · reverse-definition · distinguisher · classify-example · predict-output · trace-step ·
find-bug · complete-code · complexity-why · when-to-use · procedure-condition · edge-case ·
design-why · sql-result · sql-missing-clause · normal-form · diagram-occlusion · command · creative

---

### definition / reverse-definition
Termo → definição e definição → termo, **em notas separadas** (o reverso não deve ser a mesma frase
invertida; reescreva pelo outro lado).
Armadilha: é só isso que LLMs costumam gerar. Nunca deixe um conceito central só com este par.
```yaml
- id: deadlock-definicao
  context: "SO › Concorrência"
  archetype: definition
  front: "Deadlock: o que acontece com os processos envolvidos?"
  back: "Cada um ==espera um recurso preso por outro do grupo==, e nenhum avança."
- id: deadlock-nome
  context: "SO › Concorrência"
  archetype: reverse-definition
  front: "Como se chama a situação em que processos esperam em ciclo por recursos uns dos outros?"
  back: "==Deadlock== (impasse)."
```

### distinguisher (par confundível — Wozniak 11)
A pergunta só pode ser respondida por quem sabe **a diferença**. Escreva um card para cada lado e
ligue com `pair`.
```yaml
- id: git-revert-uso
  context: "Git › Desfazer"
  archetype: distinguisher
  pair: [git-reset-uso]
  front: "Desfazer um commit **já enviado** sem reescrever o histórico: `reset` ou `revert`?"
  back: "==`git revert`== — cria um commit novo que desfaz o anterior."
```
Aqui a pergunta é "A ou B?", mas não é sim/não: ela força a discriminação. Use só para pares do
`mapa.md`, nunca para dois termos que ninguém confunde.

### classify-example (lente partes/todo)
Dê o exemplo e peça a categoria. Treina reconhecer o conceito "na rua".
```yaml
- id: padrao-observer-exemplo
  context: "Eng. de Software › Padrões"
  archetype: classify-example
  front: "Botão que notifica vários listeners quando é clicado é um exemplo de qual padrão?"
  back: "==Observer=="
```

### predict-output (aplicação — faça variações)
Trecho curto (≤ 10 linhas) + dados → saída exata. **Rode o código** e cole a saída real.
Escreva 3–5 variações (mude um valor, a ordem, um operador) com o mesmo `context`.
```yaml
- id: py-slice-negativo-1
  context: "Python › Fatiamento"
  archetype: predict-output
  version: "Python 3"
  front: |
    O que imprime?
    ```python
    xs = [10, 20, 30, 40, 50]
    print(xs[-3:-1])
    ```
  back: "==`[30, 40]`=="
  extra: "Fim exclusivo: vai do índice -3 (30) até antes de -1 (50)."
```

### trace-step (estado no passo k)
Para algoritmos: mostre o estado antes e peça o estado depois de **um** passo. Use tabela ou
array. Encadeie passos como cards separados (enumeração sobreposta, Wozniak 10).
```yaml
- id: bubble-passo-1
  context: "Algoritmos › Bubble sort"
  archetype: trace-step
  front: |
    Vetor `[5, 1, 4, 2]`. Como fica depois da **1ª passada** do bubble sort (ordem crescente)?
  back: "==`[1, 4, 2, 5]`== — o maior (5) \"borbulha\" para o fim."
```

### find-bug
≤ 8 linhas, **um** bug, nomeie a classe do bug na resposta. Se a pergunta é "qual o bug", não
destaque a linha (`err=`) — isso entrega. Destaque só se a pergunta for "por que esta linha falha".
```yaml
- id: c-off-by-one
  context: "C › Laços"
  archetype: find-bug
  front: |
    Qual é o bug?
    ```c
    int v[5];
    for (int i = 0; i <= 5; i++) v[i] = 0;
    ```
  back: "==Escreve em `v[5]`==, fora do vetor (off-by-one). O certo é `i < 5`."
```

### complete-code (cloze em código)
Esconda **um token ou expressão** (≤ 30 caracteres), nunca uma linha inteira, nunca atravessando
linhas. Vários clozes na mesma nota viram cards irmãos: confira se um não entrega o outro e não use
`hl=` se houver mais de um buraco.

### complexity-why
Peça a complexidade **e** o porquê em cards separados, ou a complexidade com o porquê no `extra`.
```yaml
- id: heap-insercao-custo
  context: "Estruturas de dados › Heap binário"
  archetype: complexity-why
  front: "Por que inserir num heap binário custa \\(O(\\log n)\\)?"
  back: "O elemento sobe no máximo ==a altura da árvore==, que é \\(\\lfloor \\log_2 n \\rfloor\\)."
```

### when-to-use (saliência)
Cenário concreto → escolha. É o card que faz o conhecimento ser **usado**.
```yaml
- id: indice-quando-hash
  context: "BD › Índices"
  archetype: when-to-use
  front: "Consulta só por igualdade (`WHERE email = ?`), nunca por intervalo: que tipo de índice basta?"
  back: "==Hash== (B-tree também serve; hash só não atende intervalo e ordenação)."
```

### procedure-condition
Para procedimentos: pergunte **quando** fazer o passo, não "qual o passo 3".
```yaml
- id: normalizacao-quando-3fn
  context: "BD › Normalização"
  archetype: procedure-condition
  front: "Na normalização, o que dispara a passagem da 2FN para a 3FN?"
  back: "Existir ==dependência transitiva==: atributo não-chave dependendo de outro não-chave."
```

### edge-case / contraexemplo
"Que entrada quebra?" ou "Em que caso X deixa de valer?". Ótimo para algoritmos e SQL com NULL.
```yaml
- id: sql-count-null
  context: "SQL › Agregação"
  archetype: edge-case
  front: |
    Tabela `aluno(*id, nota)` com notas `7, NULL, 9`. Quanto vale `COUNT(nota)`?
  back: "==2== — `COUNT(coluna)` ignora NULL; `COUNT(*)` daria 3."
```

### design-why (lente significado)
Por que a decisão de projeto existe. Nível avançado, depois dos fatos.
```yaml
- id: tcp-por-que-isn-aleatorio
  context: "Redes › TCP"
  archetype: design-why
  level: advanced
  front: "Por que o número de sequência inicial do TCP é aleatório e não 0?"
  back: "Para ==segmentos atrasados de uma conexão antiga== não serem aceitos na nova (e dificultar spoofing)."
```

### sql-result / sql-missing-clause
**Sempre** com ```schema na pergunta e, para resultado, a tabela de dados de exemplo. Rode a
consulta (sqlite3 em Python serve) e cole o resultado real.

### normal-form
Dada a relação e as dependências funcionais, qual forma normal ela viola e por quê. Mostre o
esquema com PK sublinhada e as DFs como lista curta na pergunta.

### diagram-occlusion (Wozniak 8)
Um diagrama, vários alvos, **um alvo por card**. Ver `type: occlusion` no formato.

### command (digitar a resposta)
Comando curto (≤ 40 caracteres) que você precisa produzir de memória: `type: type`. A comparação é
letra a letra, então só para respostas com uma forma canônica.

### creative
Prompt generativo (resposta nova a cada vez). Isento da regra de consistência. Use pouco e só em
nível avançado.
