#!/usr/bin/env python3
"""Actualiza CORS_ORIGINS en Render y redeploy. No imprime secretos."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE_ID = "srv-d9lq8p2jnfac73b2gokg"
API = "https://api.render.com/v1"
KEY_FILE = ROOT / ".render_api_key.tmp"
CORS_VALUE = '["https://laria-chatbot.vercel.app","http://localhost:4321"]'


def api(method: str, path: str, key: str, body: object | None = None):
    data = None
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode() or "null"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:300]}
        return e.code, payload


def main() -> None:
    key = KEY_FILE.read_text().strip()
    print("==> Set CORS_ORIGINS…")
    # Intentar upsert por key
    code, resp = api(
        "PUT",
        f"/services/{SERVICE_ID}/env-vars/CORS_ORIGINS",
        key,
        {"value": CORS_VALUE},
    )
    if code not in (200, 201):
        code, resp = api(
            "POST",
            f"/services/{SERVICE_ID}/env-vars",
            key,
            {"key": "CORS_ORIGINS", "value": CORS_VALUE},
        )
    if code not in (200, 201):
        # fallback: replace all known by GET+PUT batch with only this key merge
        c2, existing = api("GET", f"/services/{SERVICE_ID}/env-vars", key)
        if c2 != 200:
            print("FAIL get env", c2, resp.get("message") if isinstance(resp, dict) else resp)
            raise SystemExit(1)
        items = existing if isinstance(existing, list) else existing.get("data", [])
        merged = []
        seen = False
        for row in items:
            ev = row.get("envVar", row)
            k = ev.get("key")
            if k == "CORS_ORIGINS":
                merged.append({"key": k, "value": CORS_VALUE})
                seen = True
            else:
                # Keep existing; Render PUT batch may need values — use generateValue skip
                # Prefer only updating CORS via PUT single; if that failed, use dashboard.
                merged.append({"key": k, "value": ev.get("value")})
        if not seen:
            merged.append({"key": "CORS_ORIGINS", "value": CORS_VALUE})
        # Filter None values
        merged = [m for m in merged if m.get("value") is not None]
        code, resp = api("PUT", f"/services/{SERVICE_ID}/env-vars", key, merged)
    if code not in (200, 201):
        print("FAIL set cors", code, resp.get("message") if isinstance(resp, dict) else "")
        raise SystemExit(1)
    print("    CORS OK (vercel + localhost:4321)")

    print("==> Redeploy…")
    code, deploy = api("POST", f"/services/{SERVICE_ID}/deploys", key, {"clearCache": "do_not_clear"})
    if code not in (200, 201):
        print("FAIL deploy", code, deploy.get("message") if isinstance(deploy, dict) else "")
        raise SystemExit(1)
    dep = deploy.get("deploy", deploy)
    deploy_id = dep.get("id")
    print("    deploy", deploy_id)

    for _ in range(72):
        time.sleep(5)
        c, dwrap = api("GET", f"/services/{SERVICE_ID}/deploys/{deploy_id}", key)
        d = dwrap.get("deploy", dwrap) if c == 200 else {}
        status = d.get("status")
        print("    status=", status)
        if status in {"live", "update_succeeded", "succeeded"}:
            break
        if status in {"build_failed", "update_failed", "canceled", "pre_deploy_failed"}:
            raise SystemExit(f"deploy failed: {status}")
    else:
        print("timeout; check dashboard")

    KEY_FILE.unlink(missing_ok=True)
    print("Done. Test: Origin https://laria-chatbot.vercel.app")


if __name__ == "__main__":
    main()
