#!/usr/bin/env bash
# gates/30-mutantes-sombra.sh — mutation testing en MODO SOMBRA: mide, no bloquea (siempre sale 0).
# Pregunta que responde: ¿los tests que escribió el builder detectan un bug sembrado en su propio código?
# Muta las líneas agregadas en report/ dentro de una copia temporal y corre los tests ahí.
# Un gate nuevo empieza en sombra; pasa a bloquear cuando su tasa de aciertos medida lo justifique.
set -u
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
cp -r report tests data "$tmp"/ 2>/dev/null
git diff -U0 "$FACTORY_BASE" -- report | python3 - "$tmp" <<'PY'
import re, subprocess, sys, pathlib
tmp = pathlib.Path(sys.argv[1])
SWAPS = [(" + ", " - "), (" == ", " != "), (" < ", " >= "), (" > ", " <= "), ("sorted(", "list("), (" not ", " "), ("+= ", "-= ")]
added, f, n = [], None, 0
for line in sys.stdin:
    if line.startswith("+++ b/"): f = line[6:].strip()
    elif m := re.match(r"@@ -\S+ \+(\d+)", line): n = int(m.group(1))
    elif line.startswith("+") and not line.startswith("+++"):
        added.append((f, n)); n += 1
killed = survived = 0
for f, n in added:
    if killed + survived >= 6: break
    path = tmp / f
    src = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for a, b in SWAPS:
        if a in src[n - 1] and not src[n - 1].lstrip().startswith(("#", '"', "import", "from")):
            mut = src.copy(); mut[n - 1] = mut[n - 1].replace(a, b, 1)
            path.write_text("".join(mut), encoding="utf-8")
            try:
                r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"], cwd=tmp, capture_output=True, timeout=20)
                dead = r.returncode != 0
            except subprocess.TimeoutExpired:
                dead = True
            path.write_text("".join(src), encoding="utf-8")
            killed += dead; survived += not dead
            print(f"{'matado     ' if dead else 'SOBREVIVE  '} {f}:{n}  {a.strip()!r} -> {b.strip()!r}")
            break
total = killed + survived
print(f"Mutantes: {killed}/{total} matados." if total else "Sin líneas mutables en report/.")
PY
exit 0
