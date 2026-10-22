# Rubrica do revisor

Julgue cada card **sozinho primeiro** e depois o deck como conjunto. Use
`../escrever-flashcards/references/exemplos-ouro.md` como âncora: compare o card com o exemplo
rotulado mais parecido antes de decidir.

## Veredito por card

| veredito | quando | o que acontece |
|---|---|---|
| `pass` | T3: as cinco propriedades ok, fato confere | fica |
| `flag` | T2, ou um problema corrigível sem mudar o alvo | o escritor aplica `fix` |
| `reject` | T1/T0, fato errado, ou alvo que não vale um card | reescrever do zero (`split`) ou descartar |

## Códigos de motivo

| código | pergunta que você faz | regra |
|---|---|---|
| `falta-contexto` | alguém que só vê este card sabe de que assunto é? | W16, M |
| `varias-respostas` | existem 2+ respostas razoáveis além da do verso? **liste-as** no `reason` | M precise/consistent |
| `raso` | testa só reconhecer o termo, sem entender? | M, N |
| `prolixo` | dá para cortar ⅓ das palavras sem perder nada? | W12 |
| `estreito` | amarrado a um exemplo/fonte, quando o fato é geral? | M provincialismo |
| `vazamento` | a pergunta ou a dica entrega a resposta? | M effortful |
| `sim-nao` | dá para acertar no chute? | M, N |
| `conjunto` | pede lista ou enumeração? | W9, W10 |
| `interferencia` | há card parecido no deck que confunde? Ele tem distinguidor e `pair`? | W11 |
| `fato-nao-verificado` | a resposta confere com a fonte, ou com a execução do código? | — |
| `ressalva-perdida` | a fonte diz "pode/em geral/no pior caso" e o card diz "é"? | — |
| `visual-ausente` | o card precisa de esquema, tabela ou diagrama para ser respondido e não tem? | U, W6 |
| `visual-decorativo` | o visual não ajuda a responder? | W6 |
| `decoreba` | pede código ou texto longo palavra por palavra? | W4, Sivers |
| `provincial` | "slide 12", "o professor" na pergunta? | W18 |
| `sem-versao` | fato que muda com a versão e não tem `version`? | W19 |

**Atenção aos dois pontos cegos de LLM** (Kirkby & Matuschak 2026): você tende a deixar passar
`varias-respostas` e `prolixo`. Para cada card, **tente escrever uma segunda resposta válida**
antes de dar `pass`. Se conseguir, é `varias-respostas`. Conte as palavras da resposta-chave: mais
de 15 é `prolixo`.

## Checagem de fatos
- Compare com o trecho da fonte (`source`/`at`). Se a fonte não está disponível, diga
  `"fact_check": "unverified"` em vez de supor.
- Código, SQL e contas: **execute** (Python, sqlite3) e compare a saída com o verso.
- A notação do professor vence a do livro quando divergem: confira o `notacao-do-professor.md`,
  se existir.

## Nível do deck
Depois dos cards, responda:
- Que conceitos centrais do `mapa.md` ficaram **sem card** ou com **um card só** (órfãos)?
- Que pares confundíveis do mapa estão **sem distinguidor**?
- O deck tem só termo ↔ definição em algum conceito? Que lente falta (exemplo, aplicação,
  causa/efeito, propósito)?
- A ordem de introdução faz sentido? Algum card avançado sem `prereqs`?

## Formato da saída (`review.json`)
```json
{
  "reviews": [
    {"id": "sql-having-vs-where", "verdict": "pass", "tier": "T3", "codes": [], "fact_check": "ok"},
    {"id": "acid-lista", "verdict": "reject", "tier": "T1", "codes": ["conjunto"],
     "reason": "pede as 4 propriedades de uma vez",
     "split": [
       {"id": "acid-atomicidade", "front": "ACID: o A garante o quê numa transação?", "back": "==Tudo ou nada==: ..."},
       {"id": "acid-isolamento", "front": "...", "back": "..."}
     ]},
    {"id": "bfs-ordem", "verdict": "flag", "tier": "T2", "codes": ["varias-respostas"],
     "reason": "sem dizer a ordem dos vizinhos, C também pode ser o 2º",
     "fix": {"front": "BFS a partir de A (vizinhos em ordem alfabética): qual é o 2º vértice visitado?"}}
  ],
  "deck": {"orphans": ["..."], "missing_pairs": [["reset", "revert"]], "missing_lenses": {"normalizacao": ["exemplo"]},
           "order_issues": ["..."], "notes": "..."}
}
```
O `fix` traz só os campos que mudam. O `split` traz notas completas, com ids novos e o mesmo
prefixo. **Nunca** proponha mudar o `id` de um card que fica.
