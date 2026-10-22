#!/usr/bin/env python3
"""check_env — diz o que está disponível e o que instalar.

Obrigatório: genanki, pygments, markdown-it-py, pyyaml, lxml
Diagramas:   graphviz (dot)  [mermaid opcional: mmdc + Chromium]
Prévia:      anki (render fiel), playwright + Chromium (screenshots), Pillow, mathjax (npm)
"""
import importlib
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REQ = {"genanki": "genanki", "pygments": "pygments", "markdown_it": "markdown-it-py", "yaml": "pyyaml", "lxml": "lxml"}
OPT = {"anki": "anki", "playwright": "playwright", "PIL": "pillow"}


def has(mod):
    try:
        importlib.import_module(mod)
        return True
    except Exception:
        return False


missing_req = [pkg for mod, pkg in REQ.items() if not has(mod)]
missing_opt = [pkg for mod, pkg in OPT.items() if not has(mod)]
print("Python:", sys.version.split()[0])
for mod, pkg in {**REQ, **OPT}.items():
    print(f"  {'ok ' if has(mod) else '-- '} {pkg}")
dot = shutil.which("dot")
print(f"  {'ok ' if dot else '-- '} graphviz (dot)")
try:
    from cardrender import find_chromium, find_mmdc
    ch, mm = find_chromium(), find_mmdc()
except Exception:
    ch = mm = None
print(f"  {'ok ' if ch else '-- '} chromium {ch or ''}")
print(f"  {'ok ' if mm else '-- '} mermaid-cli {mm or ''}")
try:
    from preview import find_mathjax
    mj = find_mathjax()
except Exception:
    mj = None
print(f"  {'ok ' if mj else '-- '} mathjax (só para screenshots) {mj or ''}")

print()
if missing_req:
    print("INSTALAR (obrigatório):  pip install --break-system-packages " + " ".join(missing_req))
if missing_opt:
    print("Opcional (prévia fiel e screenshots):  pip install --break-system-packages " + " ".join(missing_opt))
if not dot:
    print("Diagramas dot/tree:  sudo apt install graphviz   (sem isso use ```svg escrito à mão)")
if has("playwright") and not ch:
    print("Screenshots: python3 -m playwright install chromium   (ou apt install chromium)")
if not mm:
    print("Mermaid (opcional): PUPPETEER_SKIP_DOWNLOAD=1 npm i -g @mermaid-js/mermaid-cli  + um Chromium")
if not mj:
    print("Matemática nos screenshots (opcional): npm i -g mathjax@3")
sys.exit(1 if missing_req else 0)
