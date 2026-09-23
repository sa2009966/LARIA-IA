#!/usr/bin/env python3
"""Recorre el contrato completo que el frontend debe usar, y demuestra el lazo.

Existe por la fase 2 del plan de corrección: el cliente generaba y calificaba
quizzes en sus propias rutas y hablaba con OpenAI por su cuenta, así que nada de
lo que hacía el estudiante llegaba al perfil. Este script hace el recorrido
correcto de punta a punta e **imprime el mastery antes y después del intento**:
si sube, el lazo de evidencia está cerrado.

Sirve a la vez de prueba y de ejemplo vivo: cada paso imprime el método, la ruta
y lo que importa de la respuesta, que es justo lo que necesita quien integra.

    # contra el backend local (DB_PROVIDER=memory basta)
    python scripts/smoke_frontend_contract.py

    # contra el despliegue
    python scripts/smoke_frontend_contract.py --base-url https://laria-ia.onrender.com

    # sin gastar llamadas al modelo (solo contrato estructural)
    python scripts/smoke_frontend_contract.py --skip-llm

**Gasta llamadas al proveedor de IA** (análisis, turno de tutoría y generación de
quiz) salvo con `--skip-llm`. Crea un usuario desechable.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid

import httpx

TIMEOUT = 120.0
MATERIAL = """Álgebra básica.

Una variable es un símbolo que representa un valor desconocido, por ejemplo x.
Una expresión algebraica combina variables y números, como 2x + 3.
Una ecuación afirma que dos expresiones son iguales, por ejemplo 2x + 3 = 7.
Resolver una ecuación es encontrar el valor de la variable que la hace cierta:
si 2x + 3 = 7, entonces 2x = 4 y por tanto x = 2.
"""

_paso = 0


def paso(titulo: str) -> None:
    global _paso
    _paso += 1
    print(f"\n── {_paso}. {titulo}")


def detalle(texto: str) -> None:
    print(f"     {texto}")


def fallo(mensaje: str) -> None:
    print(f"\n  ✗ {mensaje}\n", file=sys.stderr)
    raise SystemExit(1)


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        fallo(mensaje)


class Contrato:
    def __init__(self, base_url: str, verbose: bool) -> None:
        self.cliente = httpx.Client(base_url=base_url.rstrip("/"), timeout=TIMEOUT)
        self.verbose = verbose
        self.token = ""

    # -- infraestructura mínima ---------------------------------------------
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def pedir(self, metodo: str, ruta: str, **kw) -> httpx.Response:
        resp = self.cliente.request(metodo, ruta, headers=self._headers(), **kw)
        if self.verbose:
            detalle(f"{metodo} {ruta} → {resp.status_code}")
            detalle(resp.text[:400])
        return resp

    def cerrar(self) -> None:
        self.cliente.close()

    # -- pasos del contrato --------------------------------------------------
    def autenticar(self) -> None:
        paso("Alta y token — POST /auth/register, POST /auth/token")
        sufijo = uuid.uuid4().hex[:8]
        email = f"contract_{sufijo}@example.com"
        password = f"Contract-{sufijo}-Ax1"
        r = self.pedir(
            "POST",
            "/api/v1/auth/register",
            json={"username": f"contract_{sufijo}", "email": email, "password": password},
        )
        exigir(r.status_code == 201, f"registro falló: {r.status_code} {r.text[:200]}")
        r = self.pedir(
            "POST", "/api/v1/auth/token", data={"username": email, "password": password}
        )
        exigir(r.status_code == 200, f"token falló: {r.status_code} {r.text[:200]}")
        self.token = r.json()["access_token"]
        detalle(f"usuario {email}")

    def subir_material(self) -> str:
        paso("Subir material — POST /documents/")
        r = self.pedir(
            "POST",
            "/api/v1/documents/",
            json={"filename": "algebra.txt", "content": MATERIAL, "subject": "Matemática"},
        )
        exigir(r.status_code == 201, f"upload falló: {r.status_code} {r.text[:200]}")
        doc_id = r.json()["id"]
        detalle(f"document_id={doc_id}")
        return doc_id

    def analizar(self, doc_id: str) -> None:
        paso("Analizar — POST /documents/{id}/analyze")
        r = self.pedir("POST", f"/api/v1/documents/{doc_id}/analyze")
        exigir(r.status_code == 200, f"analyze falló: {r.status_code} {r.text[:200]}")
        conceptos = r.json().get("key_concepts", [])
        detalle(f"conceptos detectados: {', '.join(conceptos[:5]) or '(ninguno)'}")

    def crear_chat(self, doc_id: str | None) -> str:
        etiqueta = "vinculado al material" if doc_id else "libre (sin material)"
        paso(f"Crear chat {etiqueta} — POST /chats/")
        cuerpo: dict = {"title": "Dudas de álgebra"}
        if doc_id:
            cuerpo["document_id"] = doc_id
        r = self.pedir("POST", "/api/v1/chats/", json=cuerpo)
        exigir(r.status_code == 201, f"crear chat falló: {r.status_code} {r.text[:200]}")
        chat_id = r.json()["id"]
        detalle(f"chat_id={chat_id}")
        return chat_id

    def turno(self, chat_id: str, pregunta: str) -> dict:
        paso("Turno de tutoría — POST /chats/{id}/messages")
        r = self.pedir(
            "POST",
            f"/api/v1/chats/{chat_id}/messages",
            json={"role": "user", "content": pregunta},
        )
        exigir(r.status_code == 200, f"turno falló: {r.status_code} {r.text[:200]}")
        mensajes = r.json()["messages"]
        asistente = [m for m in mensajes if m["role"] == "assistant"]
        exigir(bool(asistente), "el backend no devolvió respuesta del tutor")
        envelope = asistente[-1].get("metadata") or {}
        exigir("type" in envelope, "el mensaje del tutor no trae envelope en metadata")
        payload = envelope.get("payload", {})
        detalle(f"type={envelope.get('type')} emotion={envelope.get('emotion')}")
        detalle(
            f"grounded={payload.get('grounded')} mode={payload.get('mode')} "
            f"difficulty={payload.get('difficulty')} focus={payload.get('focus_concepts')}"
        )
        detalle("↑ esta es la respuesta a mostrar; no hace falta llamar a ningún modelo desde el cliente")
        return envelope

    def turno_streaming(self, chat_id: str, pregunta: str) -> None:
        paso("Turno en streaming — POST /chats/{id}/stream (SSE)")
        eventos: list[str] = []
        envelope_final: dict = {}
        with self.cliente.stream(
            "POST",
            f"/api/v1/chats/{chat_id}/stream",
            headers=self._headers(),
            json={"role": "user", "content": pregunta},
        ) as resp:
            exigir(resp.status_code == 200, f"stream falló: {resp.status_code}")
            evento_actual = ""
            for linea in resp.iter_lines():
                if linea.startswith("event:"):
                    evento_actual = linea.split(":", 1)[1].strip()
                    eventos.append(evento_actual)
                elif linea.startswith("data:") and evento_actual == "envelope":
                    try:
                        envelope_final = json.loads(linea.split(":", 1)[1].strip())
                    except ValueError:
                        pass
        exigir("thinking" in eventos, "faltó el evento 'thinking'")
        exigir("envelope" in eventos, "faltó el evento 'envelope'")
        exigir("done" in eventos, "faltó el evento 'done'")
        tokens = sum(1 for e in eventos if e == "token")
        detalle(f"eventos: thinking → {tokens} token(s) → envelope → done")
        detalle(f"envelope.type={envelope_final.get('type')}")

    def perfil(self) -> dict:
        r = self.pedir("GET", "/api/v1/learning/me/profile")
        exigir(r.status_code == 200, f"perfil falló: {r.status_code} {r.text[:200]}")
        return r.json()

    def generar_quiz(self, chat_id: str, num: int = 3) -> dict:
        paso("Generar quiz del material del chat — POST /chats/{id}/quiz")
        r = self.pedir("POST", f"/api/v1/chats/{chat_id}/quiz?num_questions={num}")
        exigir(r.status_code == 200, f"quiz falló: {r.status_code} {r.text[:300]}")
        quiz = r.json()
        exigir(
            "correct_answer" not in r.text,
            "el quiz reveló las respuestas correctas al cliente (no debe pasar nunca)",
        )
        detalle(f"quiz_id={quiz['id']} preguntas={len(quiz['questions'])} sin respuestas correctas")
        return quiz

    def quiz_sin_material(self, chat_libre: str) -> None:
        paso("Evaluar sin material — POST /chats/{id}/quiz (debe rechazar)")
        r = self.pedir("POST", f"/api/v1/chats/{chat_libre}/quiz")
        exigir(r.status_code == 422, f"se esperaba 422 y llegó {r.status_code}")
        detalle(f"422 · {r.json().get('detail', '')[:90]}")

    def enviar_intento(self, quiz: dict) -> dict:
        paso("Enviar intento — POST /quizzes/{id}/attempts (califica el servidor)")
        respuestas = {}
        for pregunta in quiz["questions"]:
            opciones = sorted(pregunta.get("options", {}).keys())
            respuestas[str(pregunta["index"])] = opciones[0] if opciones else "A"
        r = self.pedir(
            "POST", f"/api/v1/quizzes/{quiz['id']}/attempts", json={"answers": respuestas}
        )
        exigir(r.status_code == 200, f"intento falló: {r.status_code} {r.text[:300]}")
        intento = r.json()
        detalle(f"score={intento['score']}/{intento['total_points']} (calificado en servidor)")
        return intento

    def esperar_evidencia(self, antes: dict, intentos: int = 10) -> dict:
        paso("Evidencia proyectada — GET /learning/me/profile")
        conceptos_antes = {c["concept_key"]: c for c in antes.get("mastery_by_concept", [])}
        for _ in range(intentos):
            despues = self.perfil()
            conceptos = {c["concept_key"]: c for c in despues.get("mastery_by_concept", [])}
            if conceptos and conceptos != conceptos_antes:
                return despues
            time.sleep(1.0)
        return self.perfil()

    def recomendaciones(self) -> None:
        r = self.pedir("GET", "/api/v1/learning/me")
        if r.status_code == 200:
            recs = r.json().get("recommendations", [])
            detalle(f"recomendaciones derivadas del perfil: {len(recs)}")
            for rec in recs[:3]:
                detalle(f"  · [{rec.get('kind')}] {rec.get('message', '')[:80]}")


def comparar_mastery(antes: dict, despues: dict) -> bool:
    a = {c["concept_key"]: c["mastery"] for c in antes.get("mastery_by_concept", [])}
    d = {c["concept_key"]: c["mastery"] for c in despues.get("mastery_by_concept", [])}
    print("\n  mastery por concepto")
    print(f"    antes:   {a or '(vacío)'}")
    print(f"    después: {d or '(vacío)'}")
    print(f"    intentos registrados: {antes.get('total_attempts', 0)} → {despues.get('total_attempts', 0)}")
    return bool(d) and d != a


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--skip-llm", action="store_true", help="omite análisis, turno y quiz (no gasta modelo)"
    )
    parser.add_argument("--verbose", action="store_true", help="imprime cada request y respuesta")
    args = parser.parse_args()

    print(f"Contrato del frontend contra {args.base_url}")
    c = Contrato(args.base_url, args.verbose)
    try:
        c.autenticar()
        doc_id = c.subir_material()
        chat_libre = c.crear_chat(None)
        c.quiz_sin_material(chat_libre)

        if args.skip_llm:
            print("\n  (--skip-llm) contrato estructural verificado; sin evidencia que proyectar.")
            return 0

        c.analizar(doc_id)
        chat_id = c.crear_chat(doc_id)
        envelope = c.turno(chat_id, "¿cómo resuelvo 2x + 3 = 7?")
        exigir(
            envelope.get("payload", {}).get("grounded") is True,
            "el turno con material debería venir marcado como grounded",
        )
        c.turno_streaming(chat_id, "no entiendo por qué se resta 3 en los dos lados")

        antes = c.perfil()
        quiz = c.generar_quiz(chat_id)
        c.enviar_intento(quiz)
        despues = c.esperar_evidencia(antes)
        cerrado = comparar_mastery(antes, despues)
        c.recomendaciones()

        print()
        if cerrado:
            print("  ✓ El lazo está cerrado: lo que el estudiante hizo llegó a su perfil.")
            return 0
        print(
            "  ✗ El intento se calificó pero el perfil no cambió: la evidencia no llegó.\n"
            "    Revisa el projector y, en producción, el worker del outbox.",
            file=sys.stderr,
        )
        return 1
    finally:
        c.cerrar()


if __name__ == "__main__":
    raise SystemExit(main())
