#!/usr/bin/env python3
"""Evaluación pedagógica: estudiante novato en álgebra (cero mastery)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

import httpx

# Dominio local (decisiones LARIA sin OpenAI)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.services.pedagogical_engine import PedagogicalEngine, TutorIntent
from src.domain.services.tutor_policy import TutorPolicy

BASE = "http://127.0.0.1:8001/api/v1"
EMAIL = f"novato.algebra.{uuid4().hex[:8]}@example.com"
PASSWORD = "NovatoAlgebra1x"
USERNAME = f"novato_alg_{uuid4().hex[:6]}"

ALGEBRA_CONTENT = """
Álgebra básica — introducción para principiantes

1) Qué es el álgebra
El álgebra usa letras (variables) para representar números desconocidos.
Ejemplo: x puede ser un número que aún no conocemos.

2) Variables y constantes
- Variable: símbolo que puede cambiar (x, y, a).
- Constante: valor fijo (2, 7, -3).

3) Expresiones algebraicas
Una expresión combina números, variables y operaciones: 2x + 3
Significa: dos veces x, más tres.

4) Ecuaciones simples
Una ecuación afirma igualdad: 2x + 3 = 11
Resolver significa encontrar el valor de x.
Pasos: restar 3 → 2x = 8; dividir entre 2 → x = 4.

5) Propiedad distributiva
a(b + c) = ab + ac
Ejemplo: 3(x + 2) = 3x + 6

6) Errores frecuentes
- Confundir 2x con 2 + x
- Olvidar aplicar la misma operación a ambos lados de la ecuación
- Mezclar términos no semejantes (2x + 3 no se suma a 5x sin cuidado)
"""


def pp(title: str, data) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        print(data)


def main() -> int:
    client = httpx.Client(timeout=120.0)
    report: dict = {"student": EMAIL, "gaps": [], "observations": []}

    # --- registro / login ---
    r = client.post(
        f"{BASE}/auth/register",
        json={"username": USERNAME, "email": EMAIL, "password": PASSWORD},
    )
    pp("1) REGISTER", {"status": r.status_code, "body": r.json() if r.content else None})
    if r.status_code not in (200, 201):
        return 1

    r = client.post(
        f"{BASE}/auth/token",
        data={"username": EMAIL, "password": PASSWORD},
    )
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    pp("2) LOGIN", {"status": r.status_code, "token_len": len(token)})

    # --- perfil vacío ---
    r = client.get(f"{BASE}/learning/me/profile", headers=h)
    profile0 = r.json()
    pp("3) PERFIL INICIAL (novato)", profile0)
    report["profile_initial"] = profile0

    # --- documento álgebra ---
    r = client.post(
        f"{BASE}/documents/",
        headers=h,
        json={
            "filename": "algebra_basica.txt",
            "content": ALGEBRA_CONTENT.strip(),
            "subject": "Matemática",
        },
    )
    doc = r.json()
    doc_id = doc["id"]
    pp("4) DOCUMENTO ÁLGEBRA", {"status": r.status_code, "id": doc_id, "subject": doc.get("subject")})

    # Decisión esperada ANTES de evidencia (perfil vacío)
    engine = PedagogicalEngine()
    policy = TutorPolicy()
    empty = StudentProfile.create(uuid4())
    from uuid import UUID

    d_ask0 = engine.select(None, UUID(doc_id), TutorIntent.ASK, ("variable", "ecuación"))
    prompt0 = policy.answer_question(ALGEBRA_CONTENT[:500], "No sé nada de álgebra, ¿qué es una variable?", d_ask0)
    pp(
        "5) DECISIÓN LARIA (sin historial) — ask",
        {
            "mode": d_ask0.mode.value,
            "difficulty": d_ask0.target_difficulty.value,
            "objective": d_ask0.objective,
            "evidence_summary": d_ask0.evidence_summary,
            "system_prompt_excerpt": prompt0.system[:500],
        },
    )
    report["decision_before_evidence"] = {
        "mode": d_ask0.mode.value,
        "difficulty": d_ask0.target_difficulty.value,
    }

    # --- ask novato ---
    question = (
        "No sé nada de álgebra. Explícame qué es una variable y dame un ejemplo "
        "muy simple, como si fuera la primera vez que lo veo."
    )
    r = client.post(
        f"{BASE}/documents/{doc_id}/ask",
        headers=h,
        json={"question": question},
    )
    ask_body = r.json() if r.content else {"error": r.text}
    pp("6) ASK NOVICE → respuesta tutor", {"status": r.status_code, "answer": ask_body})
    report["ask_novice"] = {"status": r.status_code, "answer": ask_body}
    if r.status_code != 200:
        report["gaps"].append("ask falló (IA/configuración); no se pudo observar lenguaje del tutor en vivo")

    # --- quiz (LARIA debería pedir easy/practice) ---
    d_quiz0 = engine.select(None, UUID(doc_id), TutorIntent.QUIZ, ("variable", "ecuación"))
    pp(
        "7) DECISIÓN LARIA para generate_quiz (novato)",
        {
            "mode": d_quiz0.mode.value,
            "difficulty": d_quiz0.target_difficulty.value,
            "objective": d_quiz0.objective,
        },
    )
    r = client.post(
        f"{BASE}/documents/{doc_id}/quiz",
        headers=h,
        params={"num_questions": 3},
    )
    quiz = r.json() if r.content else {"error": r.text}
    pp("8) QUIZ GENERADO", {"status": r.status_code, "quiz": quiz})
    report["quiz"] = {"status": r.status_code, "body": quiz}
    if r.status_code != 200:
        report["gaps"].append("generate_quiz falló; no se pudo evaluar adaptación de ítems")
        # Continuar con evaluación de dominio local
    else:
        quiz_id = quiz["id"]
        difficulties = [q.get("difficulty") for q in quiz.get("questions", [])]
        report["quiz_difficulties"] = difficulties
        report["observations"].append(f"dificultades de ítems: {difficulties}")

        # Intento fallido a propósito (elige siempre A — típico novato)
        answers = {str(i): "A" for i in range(len(quiz["questions"]))}
        r = client.post(
            f"{BASE}/quizzes/{quiz_id}/attempts",
            headers=h,
            json={"answers": answers},
        )
        attempt = r.json() if r.content else {"error": r.text}
        pp("9) INTENTO FALLIDO (novato responde casi todo A)", {"status": r.status_code, "result": attempt})
        report["failed_attempt"] = attempt

    # --- perfil tras fallo ---
    r = client.get(f"{BASE}/learning/me/profile", headers=h)
    profile1 = r.json()
    pp("10) PERFIL TRAS QUIZ FALLIDO", profile1)
    report["profile_after_fail"] = profile1

    r = client.get(f"{BASE}/learning/me", headers=h)
    history = r.json()
    pp("11) LEARNING/ME + RECOMENDACIONES", history)
    report["history"] = history

    # --- decisión tras evidencia débil ---
    weak = StudentProfile.create(UUID(profile1["student_id"]))
    for m in profile1.get("mastery_by_document") or []:
        weak.record_quiz_result(UUID(m["document_id"]), float(m["last_score_ratio"]))
    # Si el perfil del API ya trae mastery, usamos engine sobre profile reconstruido
    if profile1.get("mastery_by_document"):
        # reconstrucción más fiel
        weak = StudentProfile.create(UUID(profile1["student_id"]))
        weak.pace = profile1.get("pace", "steady")
        weak.total_attempts = profile1.get("total_attempts", 0)
        for m in profile1["mastery_by_document"]:
            weak.record_quiz_result(UUID(m["document_id"]), float(m["last_score_ratio"]))
        # record_quiz_result altera mastery; para evaluación usamos el mastery del API
        from src.domain.aggregates.student_profile import DocumentMastery

        weak.mastery_by_document = {
            UUID(m["document_id"]): DocumentMastery(
                document_id=UUID(m["document_id"]),
                attempts=m["attempts"],
                mastery=float(m["mastery"]),
                last_score_ratio=float(m["last_score_ratio"]),
            )
            for m in profile1["mastery_by_document"]
        }

    d_ask1 = engine.select(weak, UUID(doc_id), TutorIntent.ASK)
    d_quiz1 = engine.select(weak, UUID(doc_id), TutorIntent.QUIZ)
    prompt1 = policy.answer_question("...", "Sigo sin entender variables", d_ask1)
    pp(
        "12) DECISIÓN TRAS FRACASO",
        {
            "ask_mode": d_ask1.mode.value,
            "ask_difficulty": d_ask1.target_difficulty.value,
            "quiz_mode": d_quiz1.mode.value,
            "quiz_difficulty": d_quiz1.target_difficulty.value,
            "system_excerpt": prompt1.system[:450],
        },
    )
    report["decision_after_fail"] = {
        "ask_mode": d_ask1.mode.value,
        "ask_difficulty": d_ask1.target_difficulty.value,
        "quiz_difficulty": d_quiz1.target_difficulty.value,
    }

    # Segundo ask (si IA disponible)
    r = client.post(
        f"{BASE}/documents/{doc_id}/ask",
        headers=h,
        json={
            "question": "Todavía no entiendo. ¿Puedes darme solo una pista sobre cómo despejar x en 2x+3=11?"
        },
    )
    ask2 = r.json() if r.content else {"error": r.text}
    pp("13) SEGUNDO ASK (tras fracaso)", {"status": r.status_code, "answer": ask2})
    report["ask_after_fail"] = {"status": r.status_code, "answer": ask2}

    # --- evaluación de gaps ---
    gaps = report["gaps"]
    mastery_vals = [m.get("mastery", 0) for m in (profile1.get("mastery_by_document") or [])]
    if not mastery_vals and report.get("failed_attempt") and report["failed_attempt"].get("score") is not None:
        gaps.append("Tras quiz fallido el perfil no refleja mastery (projector/perfil no cableado en runtime)")
    if profile0.get("total_attempts", 0) == 0 and d_ask0.mode.value != "scaffold":
        gaps.append("Novato sin historial debería recibir scaffold; recibió otro modo")
    if d_ask0.mode.value == "scaffold":
        report["observations"].append("OK: sin evidencia → scaffold/easy en ask")
    if d_quiz0.target_difficulty.value == "easy":
        report["observations"].append("OK: sin evidencia → quiz easy")
    recs = history.get("recommendations") or []
    if not recs:
        gaps.append("Sin recomendaciones en /learning/me")
    else:
        report["observations"].append(f"recomendaciones: {[r.get('kind') for r in recs]}")
    # ¿ask usa mastery de interacciones? Hoy solo quiz actualiza perfil
    gaps.append(
        "Las interacciones /ask NO actualizan StudentProfile (solo quiz_attempts) → "
        "decir 'no sé nada' no baja mastery ni cambia estrategia hasta fallar un quiz"
    )
    gaps.append(
        "No hay diagnóstico de conceptos erróneos por pregunta (missed_concepts casi vacío) → "
        "recomendaciones genéricas, no 'repasa variables vs constantes'"
    )
    gaps.append(
        "No hay secuencia de lección (objetivos → práctica → reevaluación) ni multi-turno socrático persistente"
    )
    gaps.append(
        "El LLM recibe el documento completo; no un plan de andamiaje por pasos con estado de sesión"
    )
    if report.get("quiz_difficulties"):
        non_easy = [d for d in report["quiz_difficulties"] if d and str(d).lower() != "easy"]
        if non_easy:
            gaps.append(
                f"Quiz para novato generó dificultades no-easy: {report['quiz_difficulties']} "
                "(el modelo puede ignorar el target de PedagogicalDecision)"
            )

    pp("14) RESUMEN OBSERVACIONES", report["observations"])
    pp("15) GAPS A REFORZAR", gaps)

    out = Path(__file__).resolve().parent / "eval_novice_algebra_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nReporte guardado en {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
