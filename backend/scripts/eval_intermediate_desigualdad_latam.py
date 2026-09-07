#!/usr/bin/env python3
"""Eval: estudiante básico-intermedio en desigualdad social en Latinoamérica.

Observa cómo LARIA adapta modo, dificultad, foco conceptual, recomendaciones,
sesión multi-turno y contexto acotado — frente a un novato vacío.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.aggregates.student_profile import ConceptMastery, DocumentMastery, StudentProfile
from src.domain.aggregates.tutor_session import TutorSession
from src.domain.services.concept_tagger import ConceptTagger
from src.domain.services.context_selector import ContextSelector
from src.domain.services.pedagogical_engine import PedagogicalEngine, TutorIntent
from src.domain.services.tutor_policy import TutorPolicy
from src.domain.value_objects.question import QuizQuestion

BASE = "http://127.0.0.1:8001/api/v1"
PASSWORD = "IntermedioLatam1x"

DOC_CONTENT = """
Desigualdad social en Latinoamérica — guía de estudio

1) Qué es la desigualdad social
La desigualdad social es la distribución desigual de recursos, oportunidades y poder
entre grupos. En Latinoamérica combina renta, educación, género, etnia y territorio.

2) Pobreza y pobreza extrema
La pobreza mide carencia de ingresos y acceso a servicios. La pobreza extrema
afecta la alimentación básica. CEPAL reporta avances desiguales entre países.

3) Índice de Gini
El coeficiente de Gini mide concentración del ingreso (0 = igualdad perfecta,
1 = desigualdad máxima). Varios países de la región tienen Gini alto comparado
con Europa, aunque con diferencias (Uruguay vs. Brasil, por ejemplo).

4) Movilidad social
La movilidad social es la capacidad de mejorar (o empeorar) la posición socioeconómica
entre generaciones. Baja movilidad implica que el origen familiar condiciona fuerte
el futuro educativo y laboral.

5) Informalidad laboral
Gran parte del empleo en la región es informal: sin contrato, seguridad social ni
protección. La informalidad refuerza la desigualdad porque limita ahorro, pensiones
y acceso a crédito.

6) Brecha educativa
La calidad y el acceso educativo varían entre zonas urbanas/rurales y entre clases.
La brecha educativa transmite desigualdad al mercado laboral.

7) Extractivismo y territorio
Economías basadas en recursos naturales pueden generar renta concentrada y conflictos
territoriales, afectando pueblos indígenas y comunidades rurales.
"""

DOC_CONCEPTS = (
    "desigualdad social",
    "pobreza",
    "indice de gini",
    "movilidad social",
    "informalidad laboral",
    "brecha educativa",
    "extractivismo",
)


def pp(title: str, data) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        print(data)


def seed_intermediate_profile(student_id, doc_id) -> StudentProfile:
    """Perfil básico-intermedio: domina lo básico, flaquea en Gini/movilidad/extractivismo."""
    p = StudentProfile.create(student_id)
    # Dominio documento ~ intermedio
    p.mastery_by_document[doc_id] = DocumentMastery(
        document_id=doc_id,
        attempts=4,
        mastery=0.58,
        last_score_ratio=0.6,
        struggle_signals=1,
    )
    p.total_attempts = 4
    p.total_struggle_signals = 1
    p.pace = "steady"
    # Conceptos: base OK, intermedio débil
    seeds = {
        "desigualdad social": 0.72,
        "pobreza": 0.65,
        "brecha educativa": 0.55,
        "informalidad laboral": 0.48,
        "indice de gini": 0.28,  # débil
        "movilidad social": 0.32,  # débil
        "extractivismo": 0.22,  # más débil
    }
    for key, mastery in seeds.items():
        p.mastery_by_concept[key] = ConceptMastery(
            concept_key=key,
            attempts=3 if mastery >= 0.5 else 2,
            mastery=mastery,
            last_score_ratio=mastery,
            document_ids=[doc_id],
        )
    p.frequent_errors = ["extractivismo", "indice de gini", "movilidad social"]
    return p


def run_offline_observation(report: dict) -> None:
    print("\n" + "#" * 72)
    print("# OBSERVACIÓN OFFLINE — básico-intermedio vs novato")
    print("#" * 72)
    engine = PedagogicalEngine()
    policy = TutorPolicy()
    selector = ContextSelector()
    tagger = ConceptTagger()
    doc_id = uuid4()
    student = uuid4()

    intermediate = seed_intermediate_profile(student, doc_id)
    novice = StudentProfile.create(uuid4())

    d_int_ask = engine.select(intermediate, doc_id, TutorIntent.ASK, DOC_CONCEPTS)
    d_nov_ask = engine.select(None, doc_id, TutorIntent.ASK, DOC_CONCEPTS)
    d_int_quiz = engine.select(intermediate, doc_id, TutorIntent.QUIZ, DOC_CONCEPTS)
    d_nov_quiz = engine.select(None, doc_id, TutorIntent.QUIZ, DOC_CONCEPTS)

    contrast = {
        "intermediate_ask": {
            "mode": d_int_ask.mode.value,
            "difficulty": d_int_ask.target_difficulty.value,
            "focus": list(d_int_ask.focus_concepts),
            "objective": d_int_ask.objective,
            "evidence": d_int_ask.evidence_summary,
        },
        "novice_ask": {
            "mode": d_nov_ask.mode.value,
            "difficulty": d_nov_ask.target_difficulty.value,
            "focus": list(d_nov_ask.focus_concepts),
            "objective": d_nov_ask.objective,
        },
        "intermediate_quiz": {
            "mode": d_int_quiz.mode.value,
            "difficulty": d_int_quiz.target_difficulty.value,
            "focus": list(d_int_quiz.focus_concepts),
        },
        "novice_quiz": {
            "mode": d_nov_quiz.mode.value,
            "difficulty": d_nov_quiz.target_difficulty.value,
        },
    }
    pp("1) CONTRASTE DECISIONES (intermedio vs novato)", contrast)
    report["offline_contrast"] = contrast

    # Recomendaciones tipo QuizService
    recs = []
    for concept in intermediate.weakest_concepts(limit=3):
        if intermediate.concept_mastery_for(concept) < 0.5:
            recs.append({"kind": "review_concept", "message": f"Repasa: {concept}."})
    pp("2) RECOMENDACIONES PARA INTERMEDIO", recs)
    report["recommendations"] = recs

    # Sesión multi-turno: ya conoce base, pide profundizar Gini
    session = TutorSession.start(student, doc_id, focus_concepts=d_int_ask.focus_concepts)
    session.record_ask(
        hint_summary="Relaciona Gini con concentración del ingreso sin dar la fórmula completa",
        focus=d_int_ask.focus_concepts,
    )
    d_after_1 = engine.select(intermediate, doc_id, TutorIntent.ASK, DOC_CONCEPTS, session=session)
    step_after_1 = session.step.value
    session.record_ask(hint_summary="Pide que compare Brasil y Uruguay con datos relativos")
    d_after_2 = engine.select(intermediate, doc_id, TutorIntent.ASK, DOC_CONCEPTS, session=session)
    session_obs = {
        "after_ask1": {
            "step": step_after_1,
            "mode": d_after_1.mode.value,
            "objective": d_after_1.objective,
            "session_step_in_decision": d_after_1.session_step,
        },
        "after_ask2": {
            "step": session.step.value,
            "mode": d_after_2.mode.value,
            "difficulty": d_after_2.target_difficulty.value,
            "objective": d_after_2.objective,
            "session_step_in_decision": d_after_2.session_step,
            "hints_stored": list(session.hints_given),
            "turns": session.turns,
        },
    }
    pp("3) SESIÓN MULTI-TURNO", session_obs)
    report["session"] = session_obs
    d_turn2 = d_after_1

    # Contexto acotado al foco débil
    document = DocumentAggregate.upload(uuid4(), "desigualdad_latam.txt", DOC_CONTENT.strip(), "Historia")
    ctx = selector.select(document, d_int_ask.focus_concepts, max_chars=900)
    prompt = policy.answer_question(
        ctx,
        "Ya entiendo pobreza, pero no me queda claro cómo el índice de Gini "
        "explica la desigualdad en Latinoamérica. ¿Me das una pista?",
        d_turn2,
    )
    ctx_obs = {
        "focus_used": list(d_int_ask.focus_concepts),
        "context_chars": len(ctx),
        "context_excerpt": ctx[:500],
        "system_excerpt": prompt.system[:450],
        "mentions_gini_or_extractivismo": (
            "gini" in ctx.lower() or "extractiv" in ctx.lower() or "movilidad" in ctx.lower()
        ),
        "full_doc_chars": len(DOC_CONTENT),
        "reduction_ratio": round(len(ctx) / max(len(DOC_CONTENT), 1), 2),
    }
    pp("4) CONTEXTO ACOTADO + PROMPT", ctx_obs)
    report["context"] = ctx_obs

    # Tagging de ítems típicos
    sample_q = tagger.tag_question(
        QuizQuestion(
            text="¿Qué mide el coeficiente de Gini en la región?",
            options={
                "A": "Concentración del ingreso",
                "B": "Inflación",
                "C": "Tipo de cambio",
                "D": "Población indígena",
            },
            correct_answer="A",
        ),
        DOC_CONCEPTS,
    )
    pp("5) TAG HEURÍSTICO ÍTEM GINI", {"concept_tags": list(sample_q.concept_tags)})
    report["sample_tags"] = list(sample_q.concept_tags)

    observations = []
    if d_int_ask.focus_concepts[0] in ("extractivismo", "indice de gini", "movilidad social"):
        observations.append(
            f"OK: foco prioriza concepto débil ({d_int_ask.focus_concepts[0]}), no 'desigualdad social' que ya domina"
        )
    if d_int_ask.mode.value != d_nov_ask.mode.value or d_int_ask.target_difficulty.value != d_nov_ask.target_difficulty.value:
        observations.append(
            f"OK: modo/dificultad distinto al novato "
            f"({d_int_ask.mode.value}/{d_int_ask.target_difficulty.value} vs "
            f"{d_nov_ask.mode.value}/{d_nov_ask.target_difficulty.value})"
        )
    else:
        observations.append(
            "NOTA: mismo modo que novato — el concepto dominante débil (<0.4) fuerza scaffold/easy "
            "aunque el documento esté en ~0.58; pedagogía correcta: enseñar por el eslabón más débil"
        )
    if recs:
        observations.append(f"OK: recomendaciones concretas: {[r['message'] for r in recs]}")
    if ctx_obs["reduction_ratio"] < 0.85:
        observations.append(
            f"OK: contexto reducido al {int(ctx_obs['reduction_ratio']*100)}% del documento"
        )
    if "pista" in d_after_1.objective.lower() or d_after_1.session_step in ("hint", "practice"):
        observations.append("OK: tras 1ª ask la sesión avanza (hint) y el objetivo recuerda pistas previas")
    if session.step.value == "practice" and session.turns >= 2:
        observations.append("OK: 2ª ask no reinicia andamiaje — pasa a practice con historial de pistas")
    report["observations"] = observations
    pp("6) OBSERVACIONES PEDAGÓGICAS", observations)


def run_http(report: dict) -> None:
    import httpx

    email = f"inter.latam.{uuid4().hex[:8]}@example.com"
    username = f"inter_latam_{uuid4().hex[:6]}"
    client = httpx.Client(timeout=120.0)
    report["student"] = email

    r = client.post(
        f"{BASE}/auth/register",
        json={"username": username, "email": email, "password": PASSWORD},
    )
    pp("H1) REGISTER", {"status": r.status_code})
    if r.status_code not in (200, 201):
        report.setdefault("gaps", []).append(f"register failed: {r.status_code}")
        return

    r = client.post(
        f"{BASE}/auth/token",
        data={"username": email, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if r.status_code != 200 or not r.content:
        report.setdefault("gaps", []).append(f"token failed: {r.status_code} {r.text[:200]}")
        pp("H1b) TOKEN FAIL", {"status": r.status_code, "body": r.text[:300]})
        return
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    r = client.post(
        f"{BASE}/documents/",
        headers=h,
        json={
            "filename": "desigualdad_latam.txt",
            "content": DOC_CONTENT.strip(),
            "subject": "Historia",
        },
    )
    doc = r.json()
    doc_id = doc["id"]
    pp("H2) DOCUMENTO", {"status": r.status_code, "id": doc_id})

    # Simular historial básico-intermedio con un quiz parcial vía API es limitado
    # (el perfil nace vacío). Sembramos evidencia con asks + un quiz y luego
    # contrastamos decisiones locales reconstruyendo el perfil intermedio.
    engine = PedagogicalEngine()
    seeded = seed_intermediate_profile(UUID(doc.get("owner_id", str(uuid4()))), UUID(doc_id))
    # Usamos student real del token vía profile endpoint after asks

    ask1 = (
        "Ya tengo una idea básica de desigualdad y pobreza en Latinoamérica. "
        "No me queda claro el índice de Gini: ¿cómo lo interpreto sin darme la respuesta completa?"
    )
    r = client.post(f"{BASE}/documents/{doc_id}/ask", headers=h, json={"question": ask1})
    ask1_body = r.json() if r.content else r.text
    pp("H3) ASK1 (intermedio, foco Gini)", {"status": r.status_code, "answer": ask1_body})
    report["ask1"] = {"status": r.status_code, "answer": ask1_body}

    ask2 = (
        "Gracias. Todavía me confunde la movilidad social: ¿una pista sobre cómo se relaciona "
        "con la brecha educativa, sin spoilear todo?"
    )
    r = client.post(f"{BASE}/documents/{doc_id}/ask", headers=h, json={"question": ask2})
    ask2_body = r.json() if r.content else r.text
    pp("H4) ASK2 (multi-turno)", {"status": r.status_code, "answer": ask2_body})
    report["ask2"] = {"status": r.status_code, "answer": ask2_body}

    r = client.post(f"{BASE}/documents/{doc_id}/quiz", headers=h, params={"num_questions": 3})
    quiz = r.json() if r.content else {"error": r.text}
    pp("H5) QUIZ ADAPTATIVO", {"status": r.status_code, "quiz": quiz})
    report["quiz"] = quiz

    if r.status_code == 200 and quiz.get("questions"):
        # Responde bien en pobreza/desigualdad (si puede) — heurística: elige B/C variado
        # Novato fallaba todo A; intermedio mezcla
        answers = {}
        for i, q in enumerate(quiz["questions"]):
            text = (q.get("text") or "").lower()
            if "gini" in text or "movilidad" in text or "extractiv" in text:
                answers[str(i)] = "B"  # probable fallo en débil
            else:
                answers[str(i)] = q.get("correct_answer") or "A"  # si API no expone, A
        # La API pública no debe revelar correct_answer — usar A/B/C mix
        answers = {str(i): ["A", "B", "C", "D"][i % 4] for i in range(len(quiz["questions"]))}
        r = client.post(
            f"{BASE}/quizzes/{quiz['id']}/attempts",
            headers=h,
            json={"answers": answers},
        )
        attempt = r.json() if r.content else r.text
        pp("H6) INTENTO QUIZ", {"status": r.status_code, "result": attempt})
        report["attempt"] = attempt

    r = client.get(f"{BASE}/learning/me/profile", headers=h)
    profile = r.json()
    pp("H7) PERFIL TRAS INTERACCIÓN", profile)
    report["profile"] = profile

    r = client.get(f"{BASE}/learning/me", headers=h)
    history = r.json()
    pp("H8) RECOMENDACIONES API", history.get("recommendations"))
    report["history_recs"] = history.get("recommendations")

    # Decisión local con perfil sembrado (lo que LARIA haría con historial intermedio real)
    d = engine.select(seed_intermediate_profile(uuid4(), UUID(doc_id)), UUID(doc_id), TutorIntent.ASK, DOC_CONCEPTS)
    pp(
        "H9) DECISIÓN ESPERADA CON PERFIL INTERMEDIO SEMBRADO",
        {
            "mode": d.mode.value,
            "difficulty": d.target_difficulty.value,
            "focus": list(d.focus_concepts),
            "objective": d.objective,
        },
    )
    report["seeded_decision"] = {
        "mode": d.mode.value,
        "difficulty": d.target_difficulty.value,
        "focus": list(d.focus_concepts),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--http", action="store_true")
    args = parser.parse_args()

    report: dict = {"gaps": [], "topic": "desigualdad social latinoamerica", "level": "basico-intermedio"}
    run_offline_observation(report)

    if args.http or not args.offline:
        try:
            run_http(report)
        except Exception as exc:  # noqa: BLE001
            report["gaps"].append(f"HTTP omitido: {exc}")
            print(f"\n[WARN] HTTP: {exc}")

    out = Path(__file__).resolve().parent / "eval_intermediate_desigualdad_latam_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nReporte: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
