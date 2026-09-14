#!/usr/bin/env python3
"""Smoke E2E contra API Compose (http://localhost:8000 por defecto).

Requiere Compose arriba. Si no hay OPENAI real, el analyze/ask/quiz fallarán con 502;
usa este script solo cuando la API responde /health y tienes clave, o valida ops:

  COMPOSE_SMOKE=1 python scripts/smoke_compose_e2e.py

Opcional — reinicio + persistencia (requiere docker compose en cwd backend/):

  COMPOSE_SMOKE=1 COMPOSE_SMOKE_RESTART=1 python scripts/smoke_compose_e2e.py

Flujo: health → ready → register → token → upload → (analyze/ask/quiz si IA disponible)
→ learning → (opcional) restart app → re-login → profile/doc.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid

import httpx

BASE = os.environ.get("LARIA_SMOKE_BASE", "http://localhost:8000").rstrip("/")
PASSWORD = "SecurePass1x"


def _wait_health(client: httpx.Client, seconds: int = 60) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            r = client.get("/health")
            if r.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("app did not become healthy in time")


def _poll_profile(
    client: httpx.Client,
    headers: dict[str, str],
    *,
    min_attempts: int = 0,
    min_struggle: int = 0,
    require_mastery: bool = False,
    ticks: int = 20,
) -> dict:
    last: dict = {}
    for _ in range(ticks):
        prof = client.get("/api/v1/learning/me/profile", headers=headers)
        assert prof.status_code == 200, prof.text
        last = prof.json()
        attempts = int(last.get("total_attempts") or 0)
        struggle = int(last.get("total_struggle_signals") or 0)
        mastery = last.get("mastery_by_document") or []
        ok_attempts = attempts >= min_attempts
        ok_struggle = struggle >= min_struggle
        ok_mastery = (not require_mastery) or (isinstance(mastery, list) and len(mastery) >= 1)
        if ok_attempts and ok_struggle and ok_mastery:
            return last
        time.sleep(0.5)
    return last


def _restart_app() -> None:
    print("restarting app via docker compose...")
    subprocess.run(
        ["docker", "compose", "restart", "app"],
        check=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )


def main() -> int:
    if os.environ.get("COMPOSE_SMOKE") != "1":
        print("Set COMPOSE_SMOKE=1 to run against a live Compose stack.")
        return 2
    email = f"smoke_{uuid.uuid4().hex[:8]}@example.com"
    user = f"sm_{uuid.uuid4().hex[:6]}"
    want_restart = os.environ.get("COMPOSE_SMOKE_RESTART") == "1"
    pedagogy_ok = False
    attempts = 0
    struggle = 0
    with httpx.Client(base_url=BASE, timeout=60.0) as c:
        h = c.get("/health")
        h.raise_for_status()
        print("health", h.json())
        rdy = c.get("/ready")
        print("ready", rdy.status_code, rdy.json())
        ready_ok = rdy.status_code == 200
        if not ready_ok:
            print("WARN: /ready not green — no se declara persistencia outbox como PASS")
        reg = c.post(
            "/api/v1/auth/register",
            json={"username": user, "email": email, "password": PASSWORD},
        )
        assert reg.status_code == 201, reg.text
        tok = c.post(
            "/api/v1/auth/token",
            data={"username": email, "password": PASSWORD},
        )
        assert tok.status_code == 200, tok.text
        headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}
        up = c.post(
            "/api/v1/documents/",
            headers=headers,
            json={
                "filename": "smoke.txt",
                "content": "Una fracción tiene numerador y denominador.",
                "subject": "Matemática",
            },
        )
        assert up.status_code == 201, up.text
        doc_id = up.json()["id"]
        print("document", doc_id)

        ia_502 = False
        for path in (
            f"/api/v1/documents/{doc_id}/analyze",
            f"/api/v1/documents/{doc_id}/ask",
        ):
            if path.endswith("/ask"):
                resp = c.post(path, headers=headers, json={"question": "no entiendo"})
            else:
                resp = c.post(path, headers=headers)
            print(path, resp.status_code)
            if resp.status_code == 502:
                print("IA unavailable (502) — ops smoke OK; no se finge evidencia pedagógica")
                m = c.get("/metrics")
                print("metrics_bytes", len(m.text), "metrics_status", m.status_code)
                ia_502 = True
                break
            resp.raise_for_status()

        if not ia_502:
            body = _poll_profile(c, headers, min_struggle=1)
            struggle = int(body.get("total_struggle_signals") or 0)
            print("struggle", struggle)
            assert struggle >= 1, body

            quiz = c.post(f"/api/v1/documents/{doc_id}/quiz?num_questions=1", headers=headers)
            print("quiz", quiz.status_code)
            if quiz.status_code == 502:
                print("IA unavailable (502) on quiz — ops smoke OK")
                ia_502 = True
            else:
                quiz.raise_for_status()
                qid = quiz.json()["id"]
                att = c.post(
                    f"/api/v1/quizzes/{qid}/attempts",
                    headers=headers,
                    json={"answers": {"0": "A"}},
                )
                print("attempt", att.status_code)
                assert att.status_code == 200, att.text
                body = _poll_profile(
                    c, headers, min_attempts=1, min_struggle=1, require_mastery=True
                )
                attempts = int(body.get("total_attempts") or 0)
                struggle = int(body.get("total_struggle_signals") or 0)
                mastery = body.get("mastery_by_document") or []
                print("profile", {"attempts": attempts, "struggle": struggle, "mastery_n": len(mastery)})
                assert attempts >= 1, body
                assert struggle >= 1, body
                assert isinstance(mastery, list) and len(mastery) >= 1, body
                pedagogy_ok = True

        if not want_restart:
            print("OK smoke. Set COMPOSE_SMOKE_RESTART=1 para persistencia post-restart.")
            return 0

        _restart_app()
        _wait_health(c)
        rdy = c.get("/ready")
        print("ready_after_restart", rdy.status_code, rdy.json())
        tok = c.post(
            "/api/v1/auth/token",
            data={"username": email, "password": PASSWORD},
        )
        assert tok.status_code == 200, tok.text
        headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}
        docs = c.get("/api/v1/documents/", headers=headers)
        assert docs.status_code == 200, docs.text
        body = docs.json()
        ids = [d.get("id") for d in body] if isinstance(body, list) else []
        assert doc_id in ids, f"doc {doc_id} missing after restart; got {ids[:5]}"
        print("document_after_restart", doc_id)

        if pedagogy_ok:
            if not ready_ok:
                print("WARN: /ready no era 200 antes del restart; perfil no se declara PASS outbox")
            else:
                prof = c.get("/api/v1/learning/me/profile", headers=headers)
                assert prof.status_code == 200, prof.text
                after = prof.json()
                after_attempts = int(after.get("total_attempts") or 0)
                after_struggle = int(after.get("total_struggle_signals") or 0)
                print("profile_after_restart", {"attempts": after_attempts, "struggle": after_struggle})
                assert after_attempts >= max(attempts, 1), (attempts, after_attempts)
                assert after_struggle >= max(struggle, 1), (struggle, after_struggle)
        print("OK smoke + persistencia post-restart")
    return 0


if __name__ == "__main__":
    sys.exit(main())
