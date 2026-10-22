# Atualizar um deck sem perder o histórico

Verificado com Anki 26.09 (pacote oficial) e genanki 0.13: re-importar um `.apkg` com os mesmos
GUIDs **atualiza** as notas e mantém intervalos e histórico de revisão
(`tests/test_update.py` reproduz o ciclo inteiro).

## As regras que garantem isso

1. **`namespace` e `id` nunca mudam.** O GUID é `guid_for(namespace, id)`. Mudar qualquer um
   dos dois cria uma nota nova, e a antiga fica órfã com o histórico. Para "renomear" um card,
   mude o texto e mantenha o id. Para apagar, remova da especificação e apague no Anki à mão
   (o import não apaga nada).
2. **Note types congelados.** Os IDs `MODEL_BASIC_ID` e `MODEL_CLOZE_ID` em `build_deck.py` e a
   lista de campos não mudam. Campos de reserva (`Reserva1..3`) existem para recursos futuros sem
   mudar o esquema. Mudar o CSS ou os templates é seguro: a atualização aplica.
   Se um dia for **inevitável** mudar campos: crie `CC Básico v2` com ID novo e, no import, peça
   para marcar "Mesclar tipos de nota" (merge note types), que exige uma sincronização completa
   de mão única.
3. **Timestamp mais novo.** O Anki só atualiza se o pacote for mais novo que a nota na coleção.
   Nunca fixe `timestamp` no `write_to_file`.
4. **Mídia com nome versionado.** O Anki **não sobrescreve** arquivo de mídia com o mesmo nome.
   Fontes e assets são `_cc1-…` (o `_` impede que "Verificar mídia" apague; o `cc1` é a versão).
   Se trocar uma fonte, mude para `_cc2-…` no CSS e em `FONT_FILES`. Imagens dos cards são nomeadas
   pelo hash do conteúdo, então uma imagem nova tem nome novo automaticamente.
5. **Ordem de cards novos.** `due` é a posição de introdução (de 10 em 10, para caber inserções).
   Re-importar **não reordena** cards novos já existentes; só as notas novas recebem posição.

## Armadilhas do lado do aluno

- **Editar um card no Anki bloqueia a próxima atualização dele** (a edição local fica mais nova
  que o pacote). Regra: corrija na especificação, não no Anki. Se editou, a opção de import
  "Atualizar notas: sempre" força.
- **Abrir o campo no editor HTML do Anki desktop (25.02+) pode apagar atributos de SVG.** Os campos
  são gerados; não edite à mão.
- No AnkiDroid, importe pelo menu ⋮ → Importar, escolhendo o `.apkg`. As mesmas regras valem.

## Fluxo de atualização (o que o orquestrador faz)

1. Ler a especificação atual e o manifesto (`.manifest.json`, com o hash de cada fonte).
2. Fontes com hash igual → pular. Fontes novas ou alteradas → gerar fragmentos só para elas.
3. `merge_specs.py cabecalho.yaml fragmentos/*.yaml --base deck.cards.yaml -o deck.cards.yaml`
   (mesmo id = atualização; id novo = card novo; colisão de id novo entre fragmentos = erro).
4. Lint → revisão → build → prévia, como num deck novo.
5. Entregar o `.apkg` novo e listar no resumo: N cards novos, M atualizados, K que **devem ser
   apagados à mão** no Anki (estavam na versão anterior e saíram da especificação).
