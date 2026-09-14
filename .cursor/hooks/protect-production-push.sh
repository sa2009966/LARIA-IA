#!/usr/bin/env bash
# Bloquea force-push y pide confirmación antes de git push / deploy Render.
# El pytest real vive en .githooks/pre-push (también aplica fuera de Cursor).
set -euo pipefail

input="$(cat)"
command="$(
  printf '%s' "$input" | python3 -c '
import json, sys
raw = sys.stdin.read()
try:
    data = json.loads(raw) if raw.strip() else {}
except json.JSONDecodeError:
    data = {}
cmd = data.get("command") or ""
tool_input = data.get("tool_input")
if not cmd and isinstance(tool_input, dict):
    cmd = tool_input.get("command") or ""
print(cmd)
'
)"

python3 - "$command" <<'PY'
import json, re, sys

cmd = sys.argv[1] if len(sys.argv) > 1 else ""
compact = " ".join(cmd.split())
lower = compact.lower()

def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(0)

is_push = re.search(r"(^|[;&|]\s*)git(\s+-C\s+\S+)?\s+push\b", compact) is not None
is_render_deploy = (
    "deploy-render-api.sh" in lower
    or "fix_render_deploy" in lower
    or "set_cors_and_redeploy" in lower
)
if not is_push and not is_render_deploy:
    emit({"permission": "allow"})

force = bool(
    re.search(r"(^|\s)(-f|--force|--force-with-lease)(\s|$)", compact)
    or re.search(r"\s\+[A-Za-z0-9._/-]+", compact)
)
protected = bool(
    re.search(r"(feature/backend|\bmain\b|\bdevelop\b)", compact)
    or not re.search(r"\sorigin\s+\S+", compact)
)
if is_push and force and protected:
    emit(
        {
            "permission": "deny",
            "user_message": (
                "Force-push bloqueado: Render auto-despliega feature/backend "
                "(https://laria-ia.onrender.com). Un rewrite puede tumbar el demo público."
            ),
            "agent_message": (
                "Hook denegó git push --force hacia el branch que alimenta Render."
            ),
        }
    )

emit(
    {
        "permission": "ask",
        "user_message": (
            "Este comando puede desplegar el demo público "
            "https://laria-ia.onrender.com (auto-deploy de feature/backend). "
            "El hook git pre-push ejecutará pytest antes de subir."
        ),
        "agent_message": (
            "Push/deploy a Render requiere confirmación; pytest corre en pre-push."
        ),
    }
)
PY
