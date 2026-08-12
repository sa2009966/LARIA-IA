#!/usr/bin/env bash
# Gate de pytest antes de empujar código que Render puede auto-desplegar.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT/backend"

if [[ -x "$ROOT/../env_dashboard/bin/python" ]]; then
  PY="$ROOT/../env_dashboard/bin/python"
elif [[ -x "$ROOT/env_dashboard/bin/python" ]]; then
  PY="$ROOT/env_dashboard/bin/python"
else
  PY="$(command -v python3)"
fi

echo "pre-push: pytest backend con $PY" >&2
timeout 180s "$PY" -m pytest tests -q
