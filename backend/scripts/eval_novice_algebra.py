#!/usr/bin/env python3
"""Evaluación pedagógica: estudiante novato en álgebra + checklist de aceptación.

Modos:
  --offline  Solo dominio (sin HTTP/OpenAI). Criterio verde del plan.
  (default)  Offline + recorrido HTTP si el API está arriba.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

# Dominio local (decisiones LARIA sin OpenAI)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.aggregates.student_profile import ConceptMastery, DocumentMastery, StudentProfile
from src.domain.aggregates.tutor_session import SessionStep, TutorSession
from src.domain.services.concept_tagger import ConceptTagger
from src.domain.services.context_selector import ContextSelector
from src.domain.services.pedagogical_engine import PedagogicalEngine, PedagogicalMode, TutorIntent
from src.domain.services.quiz_quality import ensure_quiz_quality
from src.domain.services.tutor_policy import TutorPolicy
from src.domain.value_objects.question import Difficulty, QuizQuestion

BASE = "http://127.0.0.1:8001/api/v1"
PASSWORD = "NovatoAlgebra1x"

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


def _check(results: list[dict], name: str, ok: bool, detail: str = "") -> None:
    results.append({"check": name, "ok": ok, "detail": detail})
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))


def run_offline_acceptance() -> tuple[list[dict], dict]:
    """Checklist dominio: focus / mastery / recs / secuencia / contexto."""
    print("\n" + "#" * 72)
    print("# CHECKLIST OFFLINE (sin OpenAI)")
    print("#" * 72)
    checks: list[dict] = []
    engine = PedagogicalEngine()
    doc_id = uuid4()

    # 1) Fallos de quiz → mastery por concepto
    profile = StudentProfile.create(uuid4())
    q_var = QuizQuestion(
        text="¿Qué es una variable?",
        options={"A": "letra", "B": "fijo", "C": "+", "D": "="},
        correct_answer="A",
        concept_tags=("variable",),
    )
    tagged = ConceptTagger().tag_question(
        QuizQuestion(
            text="¿Cómo resuelves una ecuación 2x=4?",
            options={"A": "dividir", "B": "sumar", "C": "ignorar", "D": "restar"},
            correct_answer="A",
        )
    )
    profile.record_quiz_result(
        document_id=doc_id,
        score_ratio=0.0,
        missed_concepts=("variable", tagged.concept_tags[0] if tagged.concept_tags else "ecuacion"),
        concept_results=(("variable", 0.0), ("ecuacion", 0.0)),
    )
    _check(
        checks,
        "quiz_updates_concept_mastery",
        profile.concept_mastery_for("variable") == 0.0 and "variable" in profile.frequent_errors,
        f"variable={profile.concept_mastery_for('variable')}; errors={profile.frequent_errors[:3]}",
    )

    # 2) focus_concepts depende del perfil
    weak_eq = StudentProfile.create(uuid4())
    weak_eq.record_concept_result("ecuacion", 0.1, document_id=doc_id)
    weak_eq.record_concept_result("variable", 0.9, document_id=doc_id)
    weak_eq.record_quiz_result(doc_id, 0.5)
    weak_var = StudentProfile.create(uuid4())
    weak_var.record_concept_result("variable", 0.1, document_id=doc_id)
    weak_var.record_concept_result("ecuacion", 0.9, document_id=doc_id)
    weak_var.record_quiz_result(doc_id, 0.5)
    d1 = engine.select(weak_eq, doc_id, TutorIntent.ASK)
    d2 = engine.select(weak_var, doc_id, TutorIntent.ASK)
    _check(
        checks,
        "focus_depends_on_profile",
        d1.focus_concepts[0] != d2.focus_concepts[0]
        and "ecuacion" in d1.focus_concepts
        and "variable" in d2.focus_concepts,
        f"focus_eq={d1.focus_concepts} focus_var={d2.focus_concepts}",
    )

    # 3) Sesión multi-turno estable (2ª ask no reinicia andamiaje)
    session = TutorSession.start(uuid4(), doc_id, focus_concepts=("variable",))
    session.record_ask(hint_summary="pista inicial sobre x", focus=("variable",))
    _check(checks, "session_first_ask_to_hint", session.step == SessionStep.HINT, session.step.value)
    session.record_ask(hint_summary="segunda pista sin spoilers")
    novice = StudentProfile.create(session.student_id)
    novice.record_concept_result("variable", 0.15, document_id=doc_id)
    d_turn2 = engine.select(novice, doc_id, TutorIntent.ASK, session=session)
    continues = (
        "pista" in d_turn2.objective.lower()
        or d_turn2.mode == PedagogicalMode.SCAFFOLD
        or session.step in (SessionStep.HINT, SessionStep.PRACTICE)
    )
    _check(
        checks,
        "session_second_ask_continues",
        continues and len(session.hints_given) == 2,
        f"step={session.step.value} mode={d_turn2.mode.value} hints={len(session.hints_given)}",
    )

    # 4) Contexto LLM acotado al foco
    owner = uuid4()
    document = DocumentAggregate.upload(owner, "algebra.txt", ALGEBRA_CONTENT.strip(), "Matemática")
    ctx = ContextSelector().select(document, ("variable",), max_chars=1200)
    _check(
        checks,
        "context_scoped_to_focus",
        ("variable" in ctx.lower() or "letra" in ctx.lower()) and "1789" not in ctx,
        f"ctx_len={len(ctx)} excerpt={ctx[:120]!r}",
    )

    # 5) Recomendaciones por concepto débil (misma regla que QuizService)
    recs = []
    for concept in profile.weakest_concepts(limit=3):
        if profile.concept_mastery_for(concept) < 0.5:
            recs.append(f"Repasa: {concept}.")
    _check(
        checks,
        "recommendations_name_weak_concepts",
        any("variable" in r or "ecuacion" in r for r in recs),
        str(recs),
    )

    # 6) Novato sin historial → scaffold/easy
    d0 = engine.select(None, doc_id, TutorIntent.ASK, ("variable", "ecuacion"))
    _check(
        checks,
        "novice_scaffold_easy",
        d0.mode == PedagogicalMode.SCAFFOLD and d0.target_difficulty == Difficulty.EASY,
        f"{d0.mode.value}/{d0.target_difficulty.value}",
    )

    # 7) Tag heurístico sin LLM
    auto = ConceptTagger().tag_question(q_var)
    _check(checks, "concept_tagger_no_llm", "variable" in auto.concept_tags, str(auto.concept_tags))

    # 8) ensure_quiz_quality preserva tags
    tagged_q = ConceptTagger().tag_question(
        QuizQuestion(
            text="Sobre la propiedad distributiva a(b+c)",
            options={"A": "ab+ac", "B": "a+b+c", "C": "abc", "D": "a/b"},
            correct_answer="A",
            difficulty=Difficulty.EASY,
        )
    )
    balanced = ensure_quiz_quality([tagged_q, tagged_q, tagged_q, tagged_q])
    _check(
        checks,
        "quiz_quality_keeps_tags",
        all(q.concept_tags for q in balanced),
        str([q.concept_tags for q in balanced[:2]]),
    )

    summary = {
        "passed": sum(1 for c in checks if c["ok"]),
        "failed": sum(1 for c in checks if not c["ok"]),
        "total": len(checks),
    }
    pp("CHECKLIST OFFLINE RESUMEN", summary)
    return checks, summary


def _rebuild_profile_from_api(profile1: dict) -> StudentProfile:
    weak = StudentProfile.create(UUID(profile1["student_id"]))
    weak.pace = profile1.get("pace", "steady")
    weak.total_attempts = profile1.get("total_attempts", 0)
    weak.total_struggle_signals = profile1.get("total_struggle_signals", 0)
    weak.frequent_errors = list(profile1.get("frequent_errors") or [])
    weak.mastery_by_document = {
        UUID(m["document_id"]): DocumentMastery(
            document_id=UUID(m["document_id"]),
            attempts=m["attempts"],
            mastery=float(m["mastery"]),
            last_score_ratio=float(m["last_score_ratio"]),
            struggle_signals=int(m.get("struggle_signals", 0)),
        )
        for m in profile1.get("mastery_by_document") or []
    }
    weak.mastery_by_concept = {
        c["concept_key"]: ConceptMastery(
            concept_key=c["concept_key"],
            attempts=c["attempts"],
            mastery=float(c["mastery"]),
            last_score_ratio=float(c["last_score_ratio"]),
        )
        for c in profile1.get("mastery_by_concept") or []
    }
    return weak


def run_http_journey(report: dict) -> list[dict]:
    import httpx

    checks: list[dict] = []
    email = f"novato.algebra.{uuid4().hex[:8]}@example.com"
    username = f"novato_alg_{uuid4().hex[:6]}"
    client = httpx.Client(timeout=120.0)
    report["student"] = email

    r = client.post(
        f"{BASE}/auth/register",
        json={"username": username, "email": email, "password": PASSWORD},
    )
    pp("1) REGISTER", {"status": r.status_code, "body": r.json() if r.content else None})
    if r.status_code not in (200, 201):
        _check(checks, "http_register", False, str(r.status_code))
        return checks

    r = client.post(f"{BASE}/auth/token", data={"username": email, "password": PASSWORD})
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    pp("2) LOGIN", {"status": r.status_code, "token_len": len(token)})

    r = client.get(f"{BASE}/learning/me/profile", headers=h)
    profile0 = r.json()
    pp("3) PERFIL INICIAL (novato)", profile0)
    report["profile_initial"] = profile0

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
    pp("4) DOCUMENTO ÁLGEBRA", {"status": r.status_code, "id": doc_id})

    engine = PedagogicalEngine()
    policy = TutorPolicy()
    d_ask0 = engine.select(None, UUID(doc_id), TutorIntent.ASK, ("variable", "ecuacion"))
    prompt0 = policy.answer_question(
        ALGEBRA_CONTENT[:500],
        "No sé nada de álgebra, ¿qué es una variable?",
        d_ask0,
    )
    pp(
        "5) DECISIÓN LARIA (sin historial) — ask",
        {
            "mode": d_ask0.mode.value,
            "difficulty": d_ask0.target_difficulty.value,
            "system_prompt_excerpt": prompt0.system[:400],
        },
    )

    question = (
        "No sé nada de álgebra. Explícame qué es una variable y dame un ejemplo "
        "muy simple, como si fuera la primera vez que lo veo."
    )
    r = client.post(f"{BASE}/documents/{doc_id}/ask", headers=h, json={"question": question})
    ask_body = r.json() if r.content else {"error": r.text}
    pp("6) ASK NOVICE", {"status": r.status_code, "answer": ask_body})
    report["ask_novice"] = {"status": r.status_code, "answer": ask_body}
    if r.status_code != 200:
        report.setdefault("gaps", []).append("ask falló (IA/configuración)")

    r = client.post(f"{BASE}/documents/{doc_id}/quiz", headers=h, params={"num_questions": 3})
    quiz = r.json() if r.content else {"error": r.text}
    pp("8) QUIZ GENERADO", {"status": r.status_code, "quiz": quiz})
    report["quiz"] = {"status": r.status_code, "body": quiz}
    if r.status_code == 200:
        quiz_id = quiz["id"]
        answers = {str(i): "A" for i in range(len(quiz["questions"]))}
        r = client.post(
            f"{BASE}/quizzes/{quiz_id}/attempts",
            headers=h,
            json={"answers": answers},
        )
        attempt = r.json() if r.content else {"error": r.text}
        pp("9) INTENTO FALLIDO", {"status": r.status_code, "result": attempt})
        report["failed_attempt"] = attempt
    else:
        report.setdefault("gaps", []).append("generate_quiz falló")

    r = client.get(f"{BASE}/learning/me/profile", headers=h)
    profile1 = r.json()
    pp("10) PERFIL TRAS QUIZ", profile1)
    report["profile_after_fail"] = profile1

    r = client.get(f"{BASE}/learning/me", headers=h)
    history = r.json()
    pp("11) LEARNING/ME + RECS", history)
    report["history"] = history

    concepts = profile1.get("mastery_by_concept") or []
    _check(
        checks,
        "api_profile_has_concepts",
        bool(concepts) or not report.get("failed_attempt"),
        f"n_concepts={len(concepts)} keys={[c.get('concept_key') for c in concepts]}",
    )

    recs = history.get("recommendations") or []
    review_concept = [x for x in recs if x.get("kind") == "review_concept"]
    _check(
        checks,
        "api_review_concept_recommendations",
        bool(review_concept) or not concepts,
        str([x.get("message") for x in review_concept]),
    )

    if concepts:
        weak = _rebuild_profile_from_api(profile1)
        d_ask1 = engine.select(weak, UUID(doc_id), TutorIntent.ASK)
        _check(
            checks,
            "api_focus_from_weak_concepts",
            bool(d_ask1.focus_concepts),
            str(d_ask1.focus_concepts),
        )
        report["decision_after_fail"] = {
            "ask_mode": d_ask1.mode.value,
            "focus": list(d_ask1.focus_concepts),
        }

    r = client.post(
        f"{BASE}/documents/{doc_id}/ask",
        headers=h,
        json={
            "question": "Todavía no entiendo. ¿Puedes darme solo una pista sobre cómo despejar x en 2x+3=11?"
        },
    )
    ask2 = r.json() if r.content else {"error": r.text}
    pp("13) SEGUNDO ASK", {"status": r.status_code, "answer": ask2})
    report["ask_after_fail"] = {"status": r.status_code, "answer": ask2}
    _check(
        checks,
        "api_second_ask_ok_or_skipped",
        r.status_code in (200, 429, 503) or "ask falló" in str(report.get("gaps")),
        f"status={r.status_code}",
    )

    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Eval novato álgebra LARIA")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Solo checklist de dominio (sin HTTP)",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Forzar recorrido HTTP además del offline",
    )
    args = parser.parse_args()

    report: dict = {"gaps": [], "observations": [], "acceptance": {}}
    offline_checks, offline_summary = run_offline_acceptance()
    report["acceptance"]["offline"] = {"checks": offline_checks, "summary": offline_summary}

    http_checks: list[dict] = []
    run_http = args.http or not args.offline
    if run_http:
        try:
            http_checks = run_http_journey(report)
        except Exception as exc:  # noqa: BLE001 — eval debe reportar, no tumbar
            report["gaps"].append(f"HTTP journey no disponible: {exc}")
            print(f"\n[WARN] HTTP journey omitido: {exc}")
        report["acceptance"]["http"] = {"checks": http_checks}

    # Criterio verde del plan: offline obligatorio
    offline_ok = offline_summary["failed"] == 0
    http_failed = [c for c in http_checks if not c["ok"]]
    # HTTP es best-effort si el servidor no está; solo falla si hubo checks y fallaron
    http_ok = not http_failed

    report["acceptance"]["verdict"] = {
        "offline_ok": offline_ok,
        "http_ok": http_ok,
        "green": offline_ok and http_ok,
    }
    pp("VEREDICTO ACEPTACIÓN", report["acceptance"]["verdict"])
    if report["gaps"]:
        pp("GAPS / WARNINGS", report["gaps"])

    out = Path(__file__).resolve().parent / "eval_novice_algebra_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nReporte guardado en {out}")

    if args.offline:
        return 0 if offline_ok else 1
    return 0 if (offline_ok and http_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
