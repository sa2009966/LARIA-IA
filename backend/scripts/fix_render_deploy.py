#!/usr/bin/env python3
"""Fix/redeploy LARIA backend on Render. Secrets from local files; never printed."""
from __future__ import annotations

import json
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE_ID = "srv-d9lq8p2jnfac73b2gokg"
API = "https://api.render.com/v1"
KEY_FILE = ROOT / ".render_api_key.tmp"
ENV_FILE = ROOT / "backend" / ".env"


def die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def load_render_key() -> str:
    if not KEY_FILE.exists():
        die(f"Falta {KEY_FILE.name} (API key Render).")
    key = KEY_FILE.read_text(encoding="utf-8").strip()
    if not key.startswith("rnd_"):
        die("API key Render inválida (debe empezar por rnd_).")
    return key


def load_openai_key() -> str:
    if not ENV_FILE.exists():
        die(f"Falta {ENV_FILE}")
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENAI_API_KEY="):
            val = line.split("=", 1)[1].strip().strip('"').strip("'")
            if val:
                return val
    die("OPENAI_API_KEY vacío en backend/.env")


def api(method: str, path: str, key: str, body: object | None = None) -> tuple[int, object]:
    data = None
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8") or "null"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:300]}
        return e.code, payload


def main() -> None:
    key = load_render_key()
    openai_key = load_openai_key()
    secret = secrets.token_hex(32)
    cors = '["http://localhost:4321","https://localhost:4321"]'

    print("==> Revisando servicio…")
    code, svc_wrap = api("GET", f"/services/{SERVICE_ID}", key)
    if code != 200:
        die(f"No pude leer el servicio ({code}): {svc_wrap.get('message', svc_wrap)}")
    svc = svc_wrap.get("service", svc_wrap)
    details = svc.get("serviceDetails") or {}
    url = details.get("url") or svc.get("url") or ""
    print(f"    name={svc.get('name')} type={svc.get('type')}")
    print(f"    url={url or '(sin url aún)'}")
    print(f"    branch={svc.get('branch') or details.get('branch')}")
    print(f"    rootDir={svc.get('rootDir') or details.get('rootDir')}")
    print(f"    dockerfilePath={svc.get('dockerfilePath') or details.get('dockerfilePath')}")
    print(f"    dockerCommand={svc.get('dockerCommand') or details.get('dockerCommand')}")
    print(f"    suspended={svc.get('suspended')}")

    print("==> Últimos deploys…")
    code, deps = api("GET", f"/services/{SERVICE_ID}/deploys?limit=5", key)
    items = deps if isinstance(deps, list) else (deps.get("data") or [])
    for row in items[:5]:
        d = row.get("deploy", row)
        commit = d.get("commit") or {}
        msg = commit.get("message", "") if isinstance(commit, dict) else ""
        print(f"    {d.get('status')} | {d.get('id')} | {msg[:50]}")

    env_vars = [
        {"key": "APP_ENV", "value": "development"},
        {"key": "DB_PROVIDER", "value": "memory"},
        {"key": "RATE_LIMIT_BACKEND", "value": "memory"},
        {"key": "EVENT_BUS_BACKEND", "value": "memory"},
        {"key": "CACHE_BACKEND", "value": "memory"},
        {"key": "IA_PROVIDER", "value": "openai"},
        {"key": "OPENAI_MODEL", "value": "gpt-4o-mini"},
        {"key": "OPENAI_MODEL_DEFAULT", "value": "gpt-4o-mini"},
        {"key": "DEBUG", "value": "false"},
        {"key": "ENABLE_DOCS", "value": "true"},
        {"key": "RATE_LIMIT_ENABLED", "value": "true"},
        {"key": "LOG_LEVEL", "value": "INFO"},
        {"key": "LOG_FORMAT", "value": "text"},
        {"key": "METRICS_ENABLED", "value": "true"},
        {"key": "ACCESS_TOKEN_EXPIRE_MINUTES", "value": "60"},
        {"key": "SECRET_KEY", "value": secret},
        {"key": "OPENAI_API_KEY", "value": openai_key},
        {"key": "CORS_ORIGINS", "value": cors},
    ]

    print("==> Actualizando variables de entorno (valores ocultos)…")
    code, put = api("PUT", f"/services/{SERVICE_ID}/env-vars", key, env_vars)
    if code not in (200, 201):
        # Algunos planes usan PATCH batch distinto; intentar una a una
        print(f"    PUT batch falló ({code}); intentando upsert individual…")
        for item in env_vars:
            c, r = api("PUT", f"/services/{SERVICE_ID}/env-vars/{urllib.parse.quote(item['key'])}", key, {"value": item["value"]})
            if c not in (200, 201):
                # create
                c2, r2 = api("POST", f"/services/{SERVICE_ID}/env-vars", key, item)
                if c2 not in (200, 201):
                    die(f"No pude setear {item['key']}: {c}/{c2} {r2.get('message', r2)}")
            print(f"    set {item['key']}")
    else:
        print("    env vars OK")

    # Asegurar comando Docker / health si la API lo permite (update service)
    patch = {
        "dockerCommand": "sh -c 'uvicorn src.main:app --host 0.0.0.0 --port $PORT'",
        "healthCheckPath": "/health",
        "rootDir": "backend",
        "dockerfilePath": "./Dockerfile",
        "branch": "feature/backend",
        "autoDeploy": "yes",
    }
    print("==> Parcheando config del servicio…")
    code, patched = api("PATCH", f"/services/{SERVICE_ID}", key, patch)
    if code not in (200, 201):
        print(f"    PATCH parcial/no soportado ({code}): {patched.get('message', 'ok-ish')}")
    else:
        print("    config OK")

    print("==> Disparando deploy…")
    code, deploy = api("POST", f"/services/{SERVICE_ID}/deploys", key, {"clearCache": "clear"})
    if code not in (200, 201):
        die(f"No pude disparar deploy ({code}): {deploy.get('message', deploy)}")
    dep = deploy.get("deploy", deploy)
    deploy_id = dep.get("id")
    print(f"    deploy_id={deploy_id}")

    print("==> Esperando estado del deploy (hasta ~6 min)…")
    final = None
    for _ in range(72):
        time.sleep(5)
        c, dwrap = api("GET", f"/services/{SERVICE_ID}/deploys/{deploy_id}", key)
        d = dwrap.get("deploy", dwrap) if c == 200 else {}
        status = d.get("status") or "unknown"
        print(f"    status={status}")
        if status in {"live", "update_succeeded", "succeeded", "available"}:
            final = status
            break
        if status in {"build_failed", "update_failed", "canceled", "deactivated", "pre_deploy_failed"}:
            die(f"Deploy falló con status={status}. Revisa logs en el dashboard.")
    else:
        print("    timeout esperando; sigue en dashboard (puede ser cold start free).")

    code, svc_wrap = api("GET", f"/services/{SERVICE_ID}", key)
    svc = svc_wrap.get("service", svc_wrap)
    details = svc.get("serviceDetails") or {}
    url = details.get("url") or svc.get("url") or url
    print("==> Resultado")
    print(f"URL={url}")
    if url:
        print(f"Health={url.rstrip('/')}/health")
        print(f"Docs={url.rstrip('/')}/docs")
        print(f"API={url.rstrip('/')}/api/v1")
    if final:
        print(f"deploy_status={final}")

    # Cleanup key file
    try:
        KEY_FILE.unlink(missing_ok=True)
        print("API key temporal eliminada del disco.")
    except OSError:
        pass


if __name__ == "__main__":
    main()
