"""Nivelación por rondas: qué preguntar, y qué veredicto sale (ADR-016, ADR-017).

Responde a "quiero aprender X" cuando no hay evidencia sobre el estudiante. No
genera texto ni habla con el modelo: eso es del prompt y del adaptador. Aquí solo
está la pedagogía.

Tres ideas sostienen el diseño:

1. **Rondas, no una tanda mezclada.** Una ronda que se aprueba y da paso a otra
   más dura es una experiencia que el estudiante entiende sin explicársela, y
   —sobre todo— produce un **veredicto de nivel**, que es lo que decide por dónde
   empieza la ruta de aprendizaje.
2. **Se prueba la base, no solo el tema.** Los ítems fáciles van a los
   prerrequisitos del grafo. Sin evidencia sobre la base, `PrerequisiteGate` no
   puede escalar a `OFFER` ni a `SEQUENCE`, y medio motor queda invisible.
3. **Aprobar es exigente.** En una nivelación, un falso "avanzado" hace más daño
   que un falso "intermedio": deja al estudiante con material por encima de su
   nivel y al sistema sin saber por qué se atasca.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.domain.aggregates.concept_graph import ConceptGraph
from src.domain.concept_identity import canonicalize_concept
from src.domain.value_objects.question import Difficulty

#: Cuántos prerrequisitos directos entran. Más de dos y la nivelación deja de ser
#: sobre el tema que el estudiante pidió.
MAX_PREREQUISITES = 2

#: Proporción de aciertos para superar una ronda. Hipótesis nombrada, como los
#: cutoffs del ADR-004: no es una constante física (ADR-017, decisión 2).
PASSING_RATIO = 0.75


class PlacementLevel(str, Enum):
    """Veredicto de nivel sobre un tema."""

    BASICO = "basico"
    INTERMEDIO = "intermedio"
    AVANZADO = "avanzado"


class PlacementRound(str, Enum):
    """Qué ronda se está administrando."""

    #: Lo básico del tema y su base. La que recibe quien llega sin historial.
    BASE = "base"
    #: El dominio real del tema. Solo la ve quien superó la anterior.
    AVANZADA = "avanzada"


@dataclass(frozen=True)
class DiagnosticRung:
    """Un peldaño: cuántos ítems, de qué dificultad y sobre qué conceptos."""

    difficulty: Difficulty
    items: int
    concepts: tuple[str, ...]


@dataclass(frozen=True)
class DiagnosticPlan:
    """Qué medir y cómo, antes de generar una sola pregunta."""

    topic: str
    round: PlacementRound
    concepts: tuple[str, ...]
    rungs: tuple[DiagnosticRung, ...]

    @property
    def total_items(self) -> int:
        return sum(r.items for r in self.rungs)

    @property
    def prerequisites(self) -> tuple[str, ...]:
        """Los conceptos del plan que no son el tema pedido."""
        return tuple(c for c in self.concepts if c != self.topic)


def round_for(level: PlacementLevel | None) -> PlacementRound:
    """Qué ronda le toca a quien ya tiene este nivel en el tema.

    Quien no tiene nivel empieza por la base. Quien ya la superó —intermedio o
    avanzado— va a la avanzada: revalidar es legítimo y el mastery se actualiza
    con la evidencia nueva (ADR-017, decisión 4).
    """
    if level in (PlacementLevel.INTERMEDIO, PlacementLevel.AVANZADO):
        return PlacementRound.AVANZADA
    return PlacementRound.BASE


def resolve_placement(
    round_: PlacementRound, score_ratio: float, previous: PlacementLevel | None = None
) -> PlacementLevel:
    """Veredicto tras una ronda. Función pura.

    Suspender la ronda avanzada no degrada a quien ya era avanzado: el nivel
    guardado es el mejor alcanzado, y un mal día no borra lo demostrado. Lo que sí
    se mueve siempre es el mastery, que es la medida continua (ADR-017, decisión 5).
    """
    aprobo = score_ratio >= PASSING_RATIO
    if round_ == PlacementRound.BASE:
        alcanzado = PlacementLevel.INTERMEDIO if aprobo else PlacementLevel.BASICO
    else:
        alcanzado = PlacementLevel.AVANZADO if aprobo else PlacementLevel.INTERMEDIO
    if previous is None:
        return alcanzado
    orden = list(PlacementLevel)
    return max(alcanzado, previous, key=orden.index)


def has_next_round(round_: PlacementRound, level: PlacementLevel) -> bool:
    """Si tras esta ronda queda otra por administrar.

    Depende de la ronda que se acaba de hacer, no solo del nivel: quien suspende
    la avanzada también queda en `intermedio`, y mirando solo el nivel se le
    ofrecería repetirla en bucle. Se avanza por aprobar, no por quedarse.
    """
    return round_ == PlacementRound.BASE and level != PlacementLevel.BASICO


#: Reparto de cada ronda: (dificultad, ítems). El total sale de sumarlos.
_REPARTO: dict[PlacementRound, tuple[tuple[Difficulty, int], ...]] = {
    PlacementRound.BASE: ((Difficulty.EASY, 4), (Difficulty.MEDIUM, 2)),
    PlacementRound.AVANZADA: ((Difficulty.MEDIUM, 3), (Difficulty.HARD, 5)),
}


def plan_diagnostic(
    topic: str,
    graph: ConceptGraph | None = None,
    round_: PlacementRound = PlacementRound.BASE,
) -> DiagnosticPlan:
    """Plan de una ronda de nivelación. Pura: mismo tema y ronda, mismo plan.

    Si el tema no está en el grafo —uno que el currículum no cubre— el plan sigue
    siendo válido y se mide solo el tema. Un tema desconocido no es un error: es un
    tema sin base declarada.
    """
    tema = canonicalize_concept(topic)
    if not tema:
        raise ValueError("El tema del diagnóstico no puede estar vacío.")

    prereqs: tuple[str, ...] = ()
    if graph is not None:
        tema = graph.canonicalize(tema)
        prereqs = graph.prerequisites_of(tema)[:MAX_PREREQUISITES]

    base = prereqs or (tema,)
    rungs = tuple(
        DiagnosticRung(
            difficulty=dificultad,
            items=items,
            # Lo fácil prueba la base; todo lo demás, el tema. Es lo que hace que
            # fallar la ronda base señale un hueco de prerrequisito y no del tema.
            concepts=base if dificultad == Difficulty.EASY else (tema,),
        )
        for dificultad, items in _REPARTO[round_]
    )
    return DiagnosticPlan(
        topic=tema,
        round=round_,
        concepts=(tema,) + prereqs,
        rungs=rungs,
    )
