# Auditar (ou migrar) um deck que já existe

Este modo serve para quando o aluno já tem um deck `.apkg`, feito à mão, baixado ou gerado por outra ferramenta, e quer saber o que está ruim, ou trazer o deck para o padrão destas skills.

## 1. Extrair
```bash
python3 scripts/apkg_to_spec.py DECK.apkg -o rascunho.cards.yaml --namespace nome-do-deck
```
No Anki desktop, exporte em **Arquivo → Exportar → Pacote de deck**. Se o export for do formato novo (`.anki21b`), instale o pacote `anki`.

## 2. Auditar
```bash
python3 scripts/lint_cards.py rascunho.cards.yaml --json lint.json
```
Depois rode o agent revisor, que segue `rubrica.md`. Entregue ao aluno um relatório curto com:
- a contagem por veredito (`pass`, `flag`, `reject`);
- os 5 padrões de problema mais frequentes, com um exemplo de cada;
- os pares confundíveis que não têm card distinguidor.

Não reescreva o deck inteiro sem o aluno pedir.

## 3. Migrar sem perder histórico (se o aluno pedir)
Os cards antigos têm outro note type e outros GUIDs. Reimportar como deck novo **duplica** os cards e começa o histórico do zero. Há três caminhos:

- **Recomendado: manter os antigos e reescrever só os ruins.** Na especificação nova, entram só os cards reescritos (`reject`/`flag`). No Anki, o aluno suspende os antigos correspondentes; a auditoria lista quais.
- **Migrar tudo:** a mudança de note type tem que ser feita no Anki desktop, em Navegar → Notas → **Alterar tipo de nota**, para "CC Básico v1" ou "CC Cloze v1", mapeando os campos. Isso preserva o histórico.
  - Depois, para o pipeline assumir esses cards, o campo `Id` de cada um precisa conter o id da especificação.
  - Os GUIDs também precisam bater, o que exige o pacote `anki` (`note.guid = guid_for(namespace, id)`) e uma sincronização completa.
  - Explique o custo ao aluno antes de começar.
- **Começar do zero:** só faz sentido quando o deck antigo é pequeno ou o histórico importa pouco.
