#!/usr/bin/env python3
"""Siembra cuentas de demo con historial suficiente para que el motor se note.

## El problema que resuelve

Una cuenta recién creada **no adapta nada**, y es correcto que así sea:
`min_samples_for_adaptation=5` (ADR-004) y `has_decision_evidence` (ADR-007)
exigen evidencia antes de afirmar nada sobre un estudiante. La consecuencia es
que una demo con cuentas nuevas enseña un tutor genérico: todo el motor está
ahí y nada de lo que hace es visible.

Este guion crea cuentas que ya han vivido algo, con los cuatro estados que el
motor sabe distinguir:

| Estado | Qué lo produce | Dónde se ve |
|---|---|---|
| **dominado** | ítems calificados correctos y repetidos | `mastered_concepts`, celebración |
| **débil** | ítems fallados | `weakest_concepts`, modo `scaffold` |
| **olvidado** | dominio antiguo sin repasar | `forgotten_concepts`, curva de olvido |
| **bloqueado** | fallo medido y repetido en un prerrequisito | `GateAction.SEQUENCE` |

Y con señales de conducta distintas entre cuentas, para que la adaptación y su
explicación (`payload.explanation`) sean **distintas y defendibles** en cada
una. Si las tres cuentas produjeran la misma frase, la demo probaría que el
motor responde, no que discrimina.

## Cómo escribe

Por **eventos de dominio**, a través del `LearningEvidenceProjector` real. No
compone perfiles a mano: el mastery, las rachas y las señales los calcula el
mismo código que corre en producción, así que los números de la demo son los
que el sistema produciría de verdad (invariante 1: el perfil tiene un solo
escritor).

**Una sola excepción, deliberada y marcada:** el estado "olvidado" exige que
haya pasado tiempo, y el tiempo no se puede emitir como evento. Tras proyectar,
el guion retrasa `last_practiced_at` de los conceptos elegidos. Mueve el reloj,
nunca el mastery — el decaimiento lo sigue calculando el dominio.

## Uso

    # ver el plan sin escribir nada (por defecto)
    python scripts/seed_demo_profiles.py

    # sembrar de verdad (exige DB_PROVIDER=mongodb: en memoria no sobrevive)
    python scripts/seed_demo_profiles.py --apply

    # volver a sembrar una cuenta ya existente
    python scripts/seed_demo_profiles.py --apply --recrear

Las credenciales se imprimen al final. Son cuentas de demostración con
contraseña conocida: **no las siembres en un entorno con datos reales.**
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

# Ejecutable directamente desde `backend/` sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASSWORD_DEMO = "LariaDemo2026"


@dataclass(frozen=True)
class Item:
    """Un ítem de quiz ya etiquetado: el concepto al que atribuye evidencia.

    `veces` repite el ítem dentro del mismo quiz. Hace falta porque la
    confianza de un concepto sube 0.08 por observación y `mastered_concepts`
    exige 0.55: **un concepto no cuenta como dominado hasta el séptimo acierto
    calificado**. Sin repetir, una demo de tres quizzes no enseñaría ni un solo
    concepto dominado ni una sola celebración.
    """

    concepto: str
    enunciado: str
    veces: int = 1


@dataclass(frozen=True)
class Ronda:
    """Un intento de quiz: qué ítems se acertaron y cuáles no."""

    aciertos: tuple[str, ...] = ()
    fallos: tuple[str, ...] = ()


@dataclass(frozen=True)
class Persona:
    """Una cuenta de demo y la historia que la explica."""

    slug: str
    titular: str
    material: str
    conceptos: tuple[str, ...]
    items: tuple[Item, ...]
    rondas: tuple[Ronda, ...]
    #: Señales de conducta: (nombre, valor). Se observan `turnos` veces, que es
    #: lo que las lleva por encima de `min_samples_for_adaptation`.
    senales: tuple[tuple[str, float], ...] = ()
    turnos: int = 6
    #: Conceptos a envejecer y cuántos días: el único retoque fuera del flujo.
    olvido: tuple[tuple[str, int], ...] = ()
    pregunta_demo: str = "¿cómo resuelvo esta ecuación?"
    concepto_demo: str = "resolver ecuación"

    @property
    def username(self) -> str:
        return f"{self.slug}_demo"

    @property
    def email(self) -> str:
        return f"{self.slug}.demo@laria.example.com"


def _items(*filas) -> tuple[Item, ...]:
    """`("variable", "enunciado")` o `("variable", "enunciado", 2)`."""
    return tuple(Item(*fila) for fila in filas)


#: Las tres cuentas. Cada una existe para hacer visible algo distinto.
PERSONAS: tuple[Persona, ...] = (
    Persona(
        slug="ana",
        titular="va rápida y abandona las explicaciones largas",
        material="algebra_basica.txt",
        conceptos=(
            "Variable",
            "Expresión algebraica",
            "Ecuación",
            "Resolución de ecuaciones",
            "Verificación de resultados",
        ),
        items=_items(
            ("variable", "¿Qué representa la letra x en 2x + 3?", 2),
            ("expresión algebraica", "¿Cuál de estas es una expresión algebraica?", 2),
            ("ecuación", "¿Qué distingue una ecuación de una expresión?", 2),
            ("resolver ecuación", "Resuelve 2x + 3 = 11"),
            ("ecuación cuadrática", "Resuelve x² - 5x + 6 = 0"),
        ),
        rondas=(
            Ronda(
                aciertos=("variable", "expresión algebraica"),
                fallos=("ecuación", "resolver ecuación", "ecuación cuadrática"),
            ),
            Ronda(
                aciertos=("variable", "expresión algebraica", "ecuación"),
                fallos=("resolver ecuación", "ecuación cuadrática"),
            ),
            Ronda(
                aciertos=("variable", "expresión algebraica", "ecuación", "resolver ecuación"),
                fallos=("ecuación cuadrática",),
            ),
            Ronda(
                aciertos=("variable", "expresión algebraica", "ecuación", "resolver ecuación"),
                fallos=("ecuación cuadrática",),
            ),
        ),
        # Abandona las explicaciones largas y pide ejemplos: la política debería
        # acortar y subir los ejemplos a 3.
        senales=(("long_explanation_abandonment", 1.0), ("example_request_rate", 1.0)),
        pregunta_demo="¿cómo resuelvo una ecuación cuadrática?",
        concepto_demo="ecuación cuadrática",
    ),
    Persona(
        slug="bruno",
        titular="atascado en la aritmética, no en el álgebra",
        material="ecuaciones_lineales.txt",
        conceptos=("Ecuación", "Resolución de ecuaciones", "Jerarquía de operaciones"),
        items=_items(
            ("jerarquía de operaciones", "Calcula 2 + 3 × 4", 2),
            ("operaciones", "Calcula -7 + 12 - 5", 2),
            ("ecuación", "¿Qué es una ecuación?"),
            ("variable", "¿Qué representa la x?"),
        ),
        # Acierta la aritmética suelta y falla el orden: la causa raíz que el
        # tutor debe señalar es específica ("el orden de las operaciones"), no
        # el insulto genérico de "repasa a sumar".
        rondas=(
            Ronda(
                aciertos=("operaciones", "ecuación", "variable"),
                fallos=("jerarquía de operaciones",),
            ),
            Ronda(
                aciertos=("operaciones", "ecuación", "variable"),
                fallos=("jerarquía de operaciones",),
            ),
        ),
        # Pide aclaración y práctica: la política debería pedir práctica antes
        # de avanzar. Nótese que NO se le acorta la explicación: el arbitraje
        # lo veta porque el gate va a andamiar (ADR-004, Decisión 5).
        senales=(("clarification_rate", 1.0), ("practice_seeking", 1.0)),
        pregunta_demo="¿cómo despejo la x en 3x + 5 = 20?",
        concepto_demo="resolver ecuación",
    ),
    Persona(
        slug="carla",
        titular="lo supo hace mes y medio y no lo ha vuelto a tocar",
        material="funciones.txt",
        conceptos=("Funciones", "Gráfica de funciones", "Función lineal"),
        items=_items(
            ("funciones", "¿Qué es una función?", 2),
            ("gráfica de funciones", "¿Qué representa el eje vertical?", 2),
            ("función lineal", "¿Qué forma tiene la gráfica de y = 2x + 1?", 2),
            ("par ordenado", "¿Qué es un par ordenado?"),
        ),
        # Lo dominó de verdad —cuatro rondas limpias— y por eso el olvido se
        # nota: sin dominio previo no hay nada que decaer.
        rondas=tuple(
            Ronda(aciertos=("funciones", "gráfica de funciones", "función lineal", "par ordenado"))
            for _ in range(4)
        ),
        # Se autocorrige sola: la política debería preguntar más en vez de
        # explicar más.
        senales=(("self_correction", 1.0), ("attention_span", 1.0)),
        olvido=(("funciones", 45), ("gráfica de funciones", 45), ("función lineal", 45)),
        pregunta_demo="¿qué era la pendiente de una recta?",
        concepto_demo="función lineal",
    ),
)


# --- Siembra -------------------------------------------------------------------------


@dataclass
class Repos:
    """Los adaptadores que necesita la siembra, resueltos una sola vez."""

    users: object
    documents: object
    quizzes: object
    attempts: object
    profiles: object
    interactions: object
    projector: object = field(default=None)


def _construir_repos() -> Repos:
    from src.application.services.learning_evidence_projector import (
        LearningEvidenceProjector,
    )
    from src.interfaces.api.dependencies import (
        get_attempt_repo,
        get_document_repo,
        get_event_bus,
        get_interaction_repo,
        get_profile_repo,
        get_quiz_repo,
        get_user_repo,
    )

    repos = Repos(
        users=get_user_repo(),
        documents=get_document_repo(),
        quizzes=get_quiz_repo(),
        attempts=get_attempt_repo(),
        profiles=get_profile_repo(),
        interactions=get_interaction_repo(),
    )
    repos.projector = LearningEvidenceProjector(
        interaction_repository=repos.interactions,
        event_bus=get_event_bus(),
        profile_repository=repos.profiles,
        quiz_repository=repos.quizzes,
        attempt_repository=repos.attempts,
    )
    return repos


async def _crear_usuario(persona: Persona, repos: Repos, recrear: bool):
    from src.domain.aggregates.user_aggregate import UserAggregate
    from src.domain.value_objects.email import Email

    existente = await repos.users.find_by_email(Email(persona.email))
    if existente is not None and not recrear:
        return existente, False
    if existente is not None:
        return existente, True
    user = UserAggregate.register(persona.username, persona.email, PASSWORD_DEMO)
    await repos.users.save(user)
    return user, True


async def _crear_material(persona: Persona, user_id, repos: Repos):
    from src.domain.aggregates.document_aggregate import DocumentAggregate
    from src.domain.value_objects.analysis_result import AnalysisResult

    doc = DocumentAggregate.upload(
        owner_id=user_id,
        filename=persona.material,
        content=(
            f"Material de demostración sobre {', '.join(persona.conceptos)}. "
            "Generado por scripts/seed_demo_profiles.py."
        ),
        subject="Matemática",
    )
    doc.complete_analysis(
        AnalysisResult(
            summary=f"Material de demo: {', '.join(persona.conceptos)}.",
            key_concepts=list(persona.conceptos),
            suggested_questions=[persona.pregunta_demo],
            confidence_score=0.9,
        )
    )
    await repos.documents.save(doc)
    return doc


async def _sembrar_quizzes(persona: Persona, user_id, doc_id, repos: Repos) -> int:
    """Un quiz y un intento por ronda, calificados por el propio agregado."""
    from src.domain.aggregates.quiz_aggregate import QuizAggregate
    from src.domain.aggregates.quiz_attempt_aggregate import QuizAttemptAggregate
    from src.domain.value_objects.question import Difficulty, QuizQuestion

    # Un ítem con `veces=2` aparece dos veces: son dos observaciones distintas
    # del mismo concepto, que es exactamente lo que mueve la confianza.
    desplegados = [item for item in persona.items for _ in range(item.veces)]
    preguntas = [
        QuizQuestion(
            text=f"{item.enunciado} ({n + 1})" if item.veces > 1 else item.enunciado,
            options={"A": "correcta", "B": "incorrecta", "C": "tampoco"},
            correct_answer="A",
            difficulty=Difficulty.MEDIUM,
            # Etiqueta explícita: `ConceptTagger` la respeta tal cual, así que
            # la evidencia va exactamente al concepto que la demo quiere mover.
            concept_tags=(item.concepto,),
        )
        for n, item in enumerate(desplegados)
    ]

    intentos = 0
    for ronda in persona.rondas:
        quiz = QuizAggregate.create(doc_id, user_id, preguntas)
        await repos.quizzes.save(quiz)
        respuestas = {
            i: ("B" if item.concepto in ronda.fallos else "A")
            for i, item in enumerate(desplegados)
        }
        intento = QuizAttemptAggregate.create(
            quiz.id, doc_id, user_id, respuestas, quiz.grade(respuestas)
        )
        await repos.attempts.save(intento)
        for evento in intento.events:
            await repos.projector.handle_quiz_attempt(evento)
        intentos += 1
    return intentos


async def _sembrar_senales(persona: Persona, user_id, doc_id, repos: Repos) -> int:
    """Turnos de chat que dejan las señales por encima del umbral de muestras."""
    from src.domain.events.domain_events import TutorQuestionAskedEvent

    if not persona.senales:
        return 0
    for _ in range(persona.turnos):
        evento = TutorQuestionAskedEvent(
            aggregate_id=doc_id,
            student_id=user_id,
            document_id=doc_id,
            question=persona.pregunta_demo,
            answer="(respuesta de demostración)",
            signal_observations=tuple(persona.senales),
            answer_length=320,
        )
        await repos.projector.handle_tutor_question(evento)
    return persona.turnos


async def _envejecer(persona: Persona, user_id, repos: Repos) -> int:
    """Retrasa el reloj de los conceptos que la demo quiere ver olvidados.

    **Única escritura directa del perfil en todo el guion.** No hay forma de
    emitir "pasaron 45 días" como evento. Se mueve `last_practiced_at` y nada
    más: el mastery efectivo lo sigue derivando la curva de olvido del dominio.
    """
    from src.domain.aggregates.student_profile import _norm_concept, _utc_now

    if not persona.olvido:
        return 0
    perfil = await repos.profiles.find_by_student(user_id)
    if perfil is None:
        return 0
    envejecidos = 0
    for concepto, dias in persona.olvido:
        entrada = perfil.mastery_by_concept.get(_norm_concept(concepto))
        if entrada is None:
            continue
        entrada.last_practiced_at = _utc_now() - timedelta(days=dias)
        envejecidos += 1
    if envejecidos:
        await repos.profiles.save(perfil)
    return envejecidos


async def _sembrar(persona: Persona, repos: Repos, recrear: bool) -> dict:
    user, nuevo = await _crear_usuario(persona, repos, recrear)
    if not nuevo:
        return {"persona": persona, "saltada": True, "user": user}

    doc = await _crear_material(persona, user.id, repos)
    intentos = await _sembrar_quizzes(persona, user.id, doc.id, repos)
    turnos = await _sembrar_senales(persona, user.id, doc.id, repos)
    envejecidos = await _envejecer(persona, user.id, repos)
    perfil = await repos.profiles.find_by_student(user.id)
    return {
        "persona": persona,
        "saltada": False,
        "user": user,
        "documento": doc,
        "intentos": intentos,
        "turnos": turnos,
        "envejecidos": envejecidos,
        "perfil": perfil,
    }


# --- Lo que se ve al final ------------------------------------------------------------


def _radiografia(persona: Persona, perfil) -> list[str]:
    """Qué vería el motor con este perfil. Es la prueba de que la siembra sirve."""
    from src.domain.catalog.prerequisite_seeds import build_seeded_graph
    from src.domain.services.adaptation_explainer import explain_adaptation
    from src.domain.services.adaptive_policy import AdaptivePolicy
    from src.domain.services.plan_composer import compose_plan
    from src.domain.services.prerequisite_graph import PrerequisiteGate

    lineas: list[str] = []
    dominados = perfil.mastered_concepts(limit=5)
    debiles = perfil.weakest_concepts(limit=3, use_effective=True)
    olvidados = perfil.forgotten_concepts(limit=3)
    lineas.append(f"    dominados : {', '.join(dominados) or '—'}")
    lineas.append(f"    débiles   : {', '.join(debiles) or '—'}")
    lineas.append(f"    olvidados : {', '.join(olvidados) or '—'}")

    gate = PrerequisiteGate(build_seeded_graph())
    resultado = gate.evaluate(persona.concepto_demo, perfil)
    lineas.append(
        f"    gate      : {resultado.action.value.upper()} sobre "
        f"{persona.concepto_demo!r}"
        + (
            f" → lidera con {', '.join(resultado.remediation_focus)}"
            if resultado.remediation_focus
            else ""
        )
    )

    senales = perfil.signals_for_policy()
    propuesta = AdaptivePolicy().decide(senales)
    plan = compose_plan(None, propuesta)
    forma = plan.prompt_shaping
    lineas.append(
        f"    adapta    : largo={forma.explanation_length} "
        f"ejemplos={forma.examples_per_explanation} "
        f"socrático={forma.socratic_question_rate} "
        f"práctica={forma.practice_before_advance}"
    )
    frase = explain_adaptation(forma, plan.control_flow, senales, plan.overrides)
    lineas.append(f"    explica   : {frase or '(sin nada que explicar)'}")
    return lineas


def _imprimir_plan() -> None:
    print("Cuentas que se sembrarían:\n")
    for p in PERSONAS:
        print(f"  {p.username:12} · {p.titular}")
        print(f"    material   : {p.material} ({len(p.conceptos)} conceptos)")
        items = sum(i.veces for i in p.items)
        print(f"    quizzes    : {len(p.rondas)} intento(s) de {items} ítems")
        print(f"    señales    : {', '.join(n for n, _ in p.senales) or '—'} ×{p.turnos}")
        if p.olvido:
            print(f"    olvido     : {', '.join(c for c, _ in p.olvido)}")
        print()
    print("Simulación. Vuelve a ejecutarlo con --apply para escribir.")


async def _ejecutar(aplicar: bool, recrear: bool) -> int:
    from src.infrastructure.config import settings

    if not aplicar:
        _imprimir_plan()
        return 0

    if settings.DB_PROVIDER != "mongodb":
        print(
            f"DB_PROVIDER={settings.DB_PROVIDER!r}: sembrar en memoria no sirve de "
            "nada, los perfiles se borran al terminar el proceso. Configura "
            "MongoDB antes de --apply.",
            file=sys.stderr,
        )
        return 1

    repos = _construir_repos()
    print(f"Base: {settings.MONGODB_DB_NAME}\n")
    resultados = []
    for persona in PERSONAS:
        resultado = await _sembrar(persona, repos, recrear)
        resultados.append(resultado)
        if resultado["saltada"]:
            print(f"  · {persona.username:12} ya existe — se salta (usa --recrear)")
            continue
        print(
            f"  ✓ {persona.username:12} {resultado['intentos']} intento(s), "
            f"{resultado['turnos']} turno(s)"
            + (f", {resultado['envejecidos']} concepto(s) envejecido(s)" if resultado["envejecidos"] else "")
        )

    print("\nLo que el motor ve ahora:\n")
    for resultado in resultados:
        persona = resultado["persona"]
        perfil = resultado.get("perfil")
        print(f"  {persona.username} — {persona.titular}")
        if perfil is None:
            print("    (sin perfil: cuenta saltada)\n")
            continue
        for linea in _radiografia(persona, perfil):
            print(linea)
        print()

    print("Credenciales (todas con la misma contraseña):\n")
    for persona in PERSONAS:
        print(f"    {persona.email}  /  {PASSWORD_DEMO}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="escribe de verdad")
    parser.add_argument(
        "--recrear",
        action="store_true",
        help="vuelve a sembrar una cuenta que ya existe (acumula evidencia)",
    )
    args = parser.parse_args()

    async def _run() -> int:
        try:
            return await _ejecutar(args.apply, args.recrear)
        finally:
            if args.apply:
                from src.infrastructure.mongodb.database import close_database

                await close_database()

    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
