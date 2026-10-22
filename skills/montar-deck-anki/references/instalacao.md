# Instalação por ambiente

Rode `python3 scripts/check_env.py`: ele diz o que falta e o comando para instalar.

| Peça | Para quê | Obrigatória? |
|---|---|---|
| `genanki pygments markdown-it-py pyyaml lxml` (pip) | build do `.apkg`, realce de código | sim |
| `graphviz` (apt) | blocos `dot` e `tree` | só se usar esses diagramas |
| `anki` (pip) | prévia fiel (render do próprio Anki), teste de atualização, ler decks antigos | recomendado |
| `playwright` + Chromium, `pillow` | screenshots e checagem de layout | recomendado |
| `mathjax@3` (npm -g) | matemática nos screenshots | opcional (no Anki ela já funciona) |
| `@mermaid-js/mermaid-cli` (npm) + Chromium | blocos `mermaid` | opcional; prefira `dot` |

## Sandbox do Claude (nuvem)
```bash
pip install --break-system-packages genanki markdown-it-py pyyaml lxml anki
```
O resto (Graphviz, Playwright, Chromium) costuma vir instalado. O `apt` pode estar bloqueado, então use `pip` e `npm`.

## Tablet Android: Terminal Linux (VM Debian) ou desktop Linux
```bash
sudo apt install graphviz python3-pip chromium
pip install --break-system-packages genanki pygments markdown-it-py pyyaml lxml pillow playwright
pip install --break-system-packages anki      # wheels para x86_64 e aarch64 (glibc ≥ 2.35)
export CHROMIUM_PATH=/usr/bin/chromium        # o preview e o mermaid usam este Chromium
```
Se o `anki` não instalar, o preview usa um renderizador próprio equivalente. Só o teste de atualização fica indisponível.

## Mac
```bash
brew install graphviz
pip3 install genanki pygments markdown-it-py pyyaml lxml pillow playwright anki
python3 -m playwright install chromium
```
