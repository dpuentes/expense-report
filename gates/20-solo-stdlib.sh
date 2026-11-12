#!/usr/bin/env bash
# gates/20-solo-stdlib.sh — policy as code: este repo solo usa la librería estándar de Python.
# Falla si un archivo .py cambiado importa un módulo que no es stdlib ni un paquete del repo.
# La revisión (un LLM) puede dejar pasar un "import openpyxl"; este chequeo es determinista.
files="$(grep -E '\.py$' <<<"$FACTORY_CHANGED" || true)"
[ -n "$files" ] || { echo "Sin archivos .py cambiados."; exit 0; }
# shellcheck disable=SC2086
python3 - $files <<'PY'
import ast, pathlib, sys
local = {p.name for p in pathlib.Path(".").iterdir() if p.is_dir()} | {p.stem for p in pathlib.Path(".").glob("*.py")}
bad = []
for name in sys.argv[1:]:
    path = pathlib.Path(name)
    if not path.exists():
        continue
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
    except SyntaxError as exc:
        bad.append(f"{name}: no compila ({exc.msg}, línea {exc.lineno})")
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            mods = [node.module or ""]
        else:
            continue
        for mod in mods:
            top = mod.split(".")[0]
            if top and top not in sys.stdlib_module_names and top not in local:
                bad.append(f"{name}:{node.lineno}: import de '{top}' (no es de la librería estándar)")
if bad:
    print("Este repo solo usa la librería estándar de Python. Encontré:")
    print("\n".join(bad))
    print("Resuélvelo con stdlib (csv, json, xml.etree, zipfile) o recorta el alcance del ticket.")
    sys.exit(1)
print(f"Solo stdlib en {len(sys.argv) - 1} archivo(s).")
PY
