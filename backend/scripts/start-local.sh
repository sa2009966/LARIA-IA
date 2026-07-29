#!/usr/bin/env bash
# Arranque local del backend LARIA para conectar el frontend.
set -euo pipefail
cd "$(dirname "$0")/.."

export APP_ENV="${APP_ENV:-development}"
export DB_PROVIDER="${DB_PROVIDER:-memory}"
export RATE_LIMIT_BACKEND="${RATE_LIMIT_BACKEND:-memory}"
export EVENT_BUS_BACKEND="${EVENT_BUS_BACKEND:-memory}"
export CACHE_BACKEND="${CACHE_BACKEND:-memory}"

UVICORN="${UVICORN:-}"
if [[ -z "$UVICORN" ]]; then
  if [[ -x /home/alex/Descargas/Laria_ia/env_dashboard/bin/uvicorn ]]; then
    UVICORN=/home/alex/Descargas/Laria_ia/env_dashboard/bin/uvicorn
  elif command -v uvicorn >/dev/null 2>&1; then
    UVICORN="$(command -v uvicorn)"
  else
    echo "No se encontró uvicorn. Activa el venv o instala requirements.txt" >&2
    exit 1
  fi
fi

# No hacer 'source .env': bash rompe CORS_ORIGINS JSON. Pydantic lo lee solo.
unset CORS_ORIGINS || true

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "LARIA backend → http://localhost:${PORT}"
echo "  Health:  http://localhost:${PORT}/health"
echo "  Docs:    http://localhost:${PORT}/docs"
echo "  API:     http://localhost:${PORT}/api/v1"
echo "  CORS:    http://localhost:4321 (frontend Astro)"
echo

exec env -u CORS_ORIGINS "$UVICORN" src.main:app --host "$HOST" --port "$PORT"
