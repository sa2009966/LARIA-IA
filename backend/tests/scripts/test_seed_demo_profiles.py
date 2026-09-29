"""La siembra de demo produce de verdad los cuatro estados (fase E).

Un guion de fixtures que no se prueba miente en la demo, que es justo donde no
se puede depurar. Estos tests corren la siembra completa contra adaptadores en
memoria y comprueban lo que la fase prometía: cuatro estados distinguibles y
adaptación **ya activa** al entrar con una cuenta semilla.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

from src.application.services.learning_evidence_projector import (
    LearningEvidenceProjector,
)
from src.domain.catalog.prerequisite_seeds import build_seeded_graph
from src.domain.services.adaptive_policy import AdaptivePolicy
from src.domain.services.prerequisite_graph import GateAction, PrerequisiteGate
from src.infrastructure.persistence.in_memory_document_repo import (
    InMemoryDocumentRepository,
)
from src.infrastructure.persistence.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.persistence.in_memory_quiz_attempt_repo import (
    InMemoryQuizAttemptRepository,
)
from src.infrastructure.persistence.in_memory_quiz_repo import InMemoryQuizRepository
from src.infrastructure.persistence.in_memory_student_profile_repo import (
    InMemoryStudentProfileRepository,
)
from src.infrastructure.persistence.in_memory_tutor_interaction_repo import (
    InMemoryTutorInteractionRepository,
)
from src.infrastructure.persistence.in_memory_user_repo import InMemoryUserRepository


def _cargar_guion():
    ruta = Path(__file__).resolve().parents[2] / "scripts" / "seed_demo_profiles.py"
    spec = importlib.util.spec_from_file_location("seed_demo_profiles", ruta)
    modulo = importlib.util.module_from_spec(spec)
    # Registrarlo antes de ejecutarlo: `@dataclass` resuelve las anotaciones
    # mirando `sys.modules[cls.__module__]`, que si no existe revienta.
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


seed = _cargar_guion()


def _repos():
    profiles = InMemoryStudentProfileRepository()
    interactions = InMemoryTutorInteractionRepository()
    quizzes = InMemoryQuizRepository()
    attempts = InMemoryQuizAttemptRepository()
    repos = seed.Repos(
        users=InMemoryUserRepository(),
        documents=InMemoryDocumentRepository(),
        quizzes=quizzes,
        attempts=attempts,
        profiles=profiles,
        interactions=interactions,
    )
    repos.projector = LearningEvidenceProjector(
        interaction_repository=interactions,
        event_bus=InMemoryEventBus(),
        profile_repository=profiles,
        quiz_repository=quizzes,
        attempt_repository=attempts,
    )
    return repos


def _persona(slug: str):
    return next(p for p in seed.PERSONAS if p.slug == slug)


async def _sembrar(slug: str):
    return await seed._sembrar(_persona(slug), _repos(), recrear=False)


# --- Los cuatro estados --------------------------------------------------------------


@pytest.mark.asyncio
async def test_ana_deja_conceptos_dominados_y_uno_debil():
    resultado = await _sembrar("ana")
    perfil = resultado["perfil"]

    assert "variable" in perfil.mastered_concepts(limit=10)
    # El concepto que falla en las tres rondas encabeza las debilidades.
    assert perfil.weakest_concepts(limit=1, use_effective=True) == ["ecuacion cuadratica"]


@pytest.mark.asyncio
async def test_bruno_queda_bloqueado_por_un_prerrequisito():
    """El estado que antes era irreproducible: SEQUENCE observable.

    Falla la aritmética, no el álgebra. Preguntar cómo despejar debe llevar al
    tutor a liderar con la base, no a explicar el despeje.
    """
    resultado = await _sembrar("bruno")
    gate = PrerequisiteGate(build_seeded_graph())

    evaluacion = gate.evaluate("resolver ecuación", resultado["perfil"])

    assert evaluacion.action == GateAction.SEQUENCE
    assert "jerarquia de operaciones" in evaluacion.remediation_focus


@pytest.mark.asyncio
async def test_carla_tiene_conceptos_olvidados_no_debiles():
    """Olvidado ≠ débil: el mastery guardado es alto y el efectivo cayó."""
    resultado = await _sembrar("carla")
    perfil = resultado["perfil"]

    olvidados = perfil.forgotten_concepts(limit=5)
    assert "funciones" in olvidados
    entrada = perfil.mastery_by_concept["funciones"]
    assert entrada.mastery > 0.5  # lo supo
    assert entrada.effective_mastery() < entrada.mastery  # y se le fue


# --- La adaptación ya está encendida al entrar ----------------------------------------


@pytest.mark.asyncio
async def test_las_senales_superan_el_umbral_de_muestras():
    """Sin esto la cuenta semilla no adapta y la demo enseña un tutor genérico."""
    resultado = await _sembrar("ana")

    senales = resultado["perfil"].signals_for_policy()
    observadas = [s for s in senales.values() if s.samples >= 5]

    assert observadas, "ninguna señal llega a min_samples_for_adaptation"


@pytest.mark.asyncio
async def test_dos_cuentas_distintas_reciben_adaptaciones_distintas():
    """Criterio de cierre: la siembra prueba que el motor discrimina, no que responde."""
    ana = await _sembrar("ana")
    carla = await _sembrar("carla")
    politica = AdaptivePolicy()

    forma_ana = politica.decide(ana["perfil"].signals_for_policy()).prompt_shaping
    forma_carla = politica.decide(carla["perfil"].signals_for_policy()).prompt_shaping

    # Ana abandona las explicaciones largas y pide ejemplos.
    assert forma_ana.explanation_length == "short"
    assert forma_ana.examples_per_explanation == 3
    # Carla se autocorrige sola: se le pregunta más y se le puede desarrollar.
    assert forma_carla.socratic_question_rate == "high"
    assert forma_carla.explanation_length == "long"
    assert forma_ana != forma_carla


@pytest.mark.asyncio
async def test_la_radiografia_describe_lo_que_el_motor_hara():
    """Lo que imprime el guion sale del dominio, no de un texto escrito a mano."""
    resultado = await _sembrar("bruno")

    lineas = "\n".join(seed._radiografia(_persona("bruno"), resultado["perfil"]))

    assert "SEQUENCE" in lineas
    assert "jerarquia de operaciones" in lineas


# --- Higiene del guion ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_sembrar_dos_veces_no_duplica_la_cuenta():
    repos = _repos()
    persona = _persona("ana")

    primero = await seed._sembrar(persona, repos, recrear=False)
    segundo = await seed._sembrar(persona, repos, recrear=False)

    assert primero["saltada"] is False
    assert segundo["saltada"] is True


def test_cada_persona_existe_para_hacer_visible_algo_distinto():
    """Tres cuentas que produjeran lo mismo no serían tres cuentas."""
    assert len({p.slug for p in seed.PERSONAS}) == len(seed.PERSONAS)
    assert len({p.email for p in seed.PERSONAS}) == len(seed.PERSONAS)
    assert len({p.senales for p in seed.PERSONAS}) == len(seed.PERSONAS)
