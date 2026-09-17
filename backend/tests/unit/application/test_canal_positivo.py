"""El canal positivo existe y es alcanzable (ADR-009).

`celebration` en el envelope y `CELEBRATORY` en el afecto estaban en el código
desde el principio y eran **inalcanzables**: ningún modo mapeaba a celebration
y nadie pasaba `last_score_ratio`. El sistema sabía qué dominaba el estudiante
(`mastered_concepts`) y nunca se lo decía.
"""
from uuid import uuid4

import pytest

from src.application.services.chat_tutor_service import ChatTutorService
from src.application.services.learning_evidence_projector import (
    LearningEvidenceProjector,
)
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.events.domain_events import TutorQuestionAskedEvent
from src.domain.ports.embodiment import AffectState
from src.domain.services.adaptive_policy import AdaptationParameters
from src.domain.services.pedagogical_engine import (
    PedagogicalDecision,
    PedagogicalMode,
)
from src.domain.services.prerequisite_graph import GateAction
from src.domain.value_objects.question import Difficulty
from src.infrastructure.mongodb.outbox_event_bus import _deserialize, _serialize
from src.infrastructure.persistence.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.persistence.in_memory_student_profile_repo import (
    InMemoryStudentProfileRepository,
)
from src.infrastructure.persistence.in_memory_tutor_interaction_repo import (
    InMemoryTutorInteractionRepository,
)
from src.application.services.analyze_document_service import PedagogyPlan


def perfil_con_concepto_dominado(concepto: str = "variable") -> StudentProfile:
    """Mastery ≥ 0.8 y confianza ≥ 0.55: los umbrales de `mastered_concepts`."""
    profile = StudentProfile.create(uuid4())
    for _ in range(8):
        profile.record_concept_result(concepto, 1.0)
    assert concepto in profile.mastered_concepts()
    return profile


def decision(
    mode: PedagogicalMode = PedagogicalMode.EXPLAIN,
    gate: GateAction = GateAction.PROCEED,
) -> PedagogicalDecision:
    return PedagogicalDecision(
        mode=mode,
        target_difficulty=Difficulty.MEDIUM,
        focus_concepts=("variable",),
        anti_spoiler=False,
        objective="o",
        evidence_summary="e",
        gate_action=gate,
    )


class FakeAnalyze:
    def __init__(self, decision_: PedagogicalDecision):
        self._decision = decision_
        self.finalized: list[tuple] = []

    async def prepare_pedagogy(self, document_id, question, student_id):
        return PedagogyPlan(
            document_id=document_id,
            student_id=student_id,
            question=question,
            context="ctx",
            decision=self._decision,
            adaptation=AdaptationParameters(),
        )

    async def answer_from_plan(self, plan):
        return "respuesta"

    def prompt_shaping_for(self, plan):
        return plan.prompt_shaping

    async def finalize_interaction(self, plan, answer, celebrated_concept=None):
        self.finalized.append((plan, answer, celebrated_concept))


class FakeProfiles:
    def __init__(self, profile):
        self._profile = profile

    async def find_by_student(self, student_id):
        return self._profile


# --- El hito ----------------------------------------------------------------------


def test_un_concepto_dominado_es_un_hito_una_sola_vez():
    profile = perfil_con_concepto_dominado()

    assert profile.pending_celebration() == "variable"

    profile.mark_celebrated("variable")

    assert profile.pending_celebration() is None


def test_sin_dominio_no_hay_hito():
    profile = StudentProfile.create(uuid4())
    profile.record_concept_result("variable", 0.4)

    assert profile.pending_celebration() is None


# --- El turno lo comunica ---------------------------------------------------------


@pytest.mark.asyncio
async def test_el_turno_celebra_el_hito_en_el_envelope():
    profile = perfil_con_concepto_dominado()
    analyze = FakeAnalyze(decision())
    svc = ChatTutorService(
        analyze_service=analyze, profile_repository=FakeProfiles(profile)
    )

    result = await svc.answer(uuid4(), "¿y ahora qué sigue?", profile.student_id)

    assert result.envelope.type == "celebration"
    assert result.envelope.payload["celebrated_concept"] == "variable"
    # Y viaja al projector para no repetirse en el turno siguiente.
    assert analyze.finalized[0][2] == "variable"


@pytest.mark.asyncio
async def test_no_se_celebra_mientras_se_remedia():
    """Celebrar en medio del andamiaje sería ruido, no reconocimiento."""
    profile = perfil_con_concepto_dominado()

    for modo, gate in (
        (PedagogicalMode.SCAFFOLD, GateAction.PROCEED),
        (PedagogicalMode.EXPLAIN, GateAction.SEQUENCE),
    ):
        analyze = FakeAnalyze(decision(modo, gate))
        svc = ChatTutorService(
            analyze_service=analyze, profile_repository=FakeProfiles(profile)
        )

        result = await svc.answer(uuid4(), "no entiendo", profile.student_id)

        assert result.envelope.type != "celebration"
        assert analyze.finalized[0][2] is None


@pytest.mark.asyncio
async def test_el_afecto_celebra_un_buen_resultado_calificado():
    doc = uuid4()
    profile = StudentProfile.create(uuid4())
    profile.record_quiz_result(doc, 0.95)
    analyze = FakeAnalyze(decision())
    svc = ChatTutorService(
        analyze_service=analyze, profile_repository=FakeProfiles(profile)
    )

    result = await svc.answer(doc, "otra duda", profile.student_id)

    assert result.envelope.emotion == AffectState.CELEBRATORY


@pytest.mark.asyncio
async def test_un_documento_sin_quizzes_no_cuenta_como_mal_resultado():
    """`last_score_ratio` vale 0.0 por defecto: leerlo sería inventar un fallo."""
    doc = uuid4()
    profile = StudentProfile.create(uuid4())
    profile.record_ask_struggle(doc, strength=0.9, concepts=("variable",))
    analyze = FakeAnalyze(decision())
    svc = ChatTutorService(
        analyze_service=analyze, profile_repository=FakeProfiles(profile)
    )

    result = await svc.answer(doc, "otra duda", profile.student_id)

    assert result.envelope.emotion != AffectState.CELEBRATORY


# --- El perfil lo recuerda --------------------------------------------------------


@pytest.mark.asyncio
async def test_el_projector_marca_el_hito_comunicado():
    profiles = InMemoryStudentProfileRepository()
    bus = InMemoryEventBus()
    projector = LearningEvidenceProjector(
        InMemoryTutorInteractionRepository(), bus, profile_repository=profiles
    )
    await projector.register()
    student, doc = uuid4(), uuid4()

    await bus.publish(
        TutorQuestionAskedEvent(
            aggregate_id=doc,
            student_id=student,
            document_id=doc,
            question="¿y ahora?",
            answer="Vas bien.",
            cognitive_style="simple",
            celebrated_concept="variable",
        )
    )

    profile = await profiles.find_by_student(student)
    assert profile is not None
    assert "variable" in profile.celebrated_concepts


def test_el_hito_viaja_en_el_outbox():
    """Producción usa outbox: un campo que no viaje aquí muere solo en prod."""
    doc, student = uuid4(), uuid4()
    event = TutorQuestionAskedEvent(
        aggregate_id=doc,
        student_id=student,
        document_id=doc,
        question="q",
        answer="a",
        celebrated_concept="variable",
    )

    payload = _serialize(event)
    restored = _deserialize({"event_type": payload["event_type"], "payload": payload})

    assert payload["celebrated_concept"] == "variable"
    assert restored is not None
    assert restored.celebrated_concept == "variable"
