from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import exp, log
from uuid import UUID


DEFAULT_HALF_LIFE_DAYS = 14.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _norm_concept(label: str) -> str:
    return label.strip().lower()


class EvidenceKind(str, Enum):
    QUIZ_ITEM = "quiz_item"
    ASK_STRUGGLE = "ask_struggle"
    HELP_REQUEST = "help_request"
    HIGH_LATENCY = "high_latency"
    REPEATED_ERROR = "repeated_error"
    SUCCESS = "success"


@dataclass(frozen=True)
class EvidenceSample:
    """Señal de aprendizaje multi-fuente para actualizar mastery."""

    kind: EvidenceKind
    score_ratio: float
    weight: float = 1.0
    latency_ms: float | None = None
    help_level: float = 0.0  # 0..1
    document_id: UUID | None = None
    subject: str | None = None
    at: datetime | None = None


@dataclass
class PedagogicalMemory:
    """Memoria educativa compacta (no historial conversacional)."""

    frequent_misconceptions: list[str] = field(default_factory=list)
    successful_examples: list[str] = field(default_factory=list)
    successful_analogies: list[str] = field(default_factory=list)
    preferred_explanation_style: str = "simple"
    last_effective_strategies: list[str] = field(default_factory=list)

    def remember_misconception(self, label: str) -> None:
        key = _norm_concept(label)
        if not key:
            return
        if key in self.frequent_misconceptions:
            self.frequent_misconceptions.remove(key)
        self.frequent_misconceptions.insert(0, key)
        self.frequent_misconceptions = self.frequent_misconceptions[:15]

    def remember_example(self, example: str) -> None:
        text = (example or "").strip()
        if not text:
            return
        if text in self.successful_examples:
            self.successful_examples.remove(text)
        self.successful_examples.insert(0, text[:240])
        self.successful_examples = self.successful_examples[:10]

    def remember_analogy(self, analogy: str) -> None:
        text = (analogy or "").strip()
        if not text:
            return
        if text in self.successful_analogies:
            self.successful_analogies.remove(text)
        self.successful_analogies.insert(0, text[:240])
        self.successful_analogies = self.successful_analogies[:10]

    def set_preferred_style(self, style: str) -> None:
        self.preferred_explanation_style = (style or "simple").strip().lower()

    def remember_strategy(self, strategy: str) -> None:
        key = (strategy or "").strip().lower()
        if not key:
            return
        if key in self.last_effective_strategies:
            self.last_effective_strategies.remove(key)
        self.last_effective_strategies.insert(0, key)
        self.last_effective_strategies = self.last_effective_strategies[:8]


@dataclass
class ConceptMastery:
    """Dominio estimado de un concepto a partir de evidencia multi-señal + olvido."""

    concept_key: str
    attempts: int = 0
    mastery: float = 0.0
    last_score_ratio: float = 0.0
    document_ids: list[UUID] = field(default_factory=list)
    confidence: float = 0.0
    last_practiced_at: datetime | None = None
    help_requests: int = 0
    latency_ms_ema: float = 0.0
    error_streak: int = 0
    subject: str | None = None
    evidence_count: int = 0
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS

    def apply_result(
        self, score_ratio: float, document_id: UUID | None = None, alpha: float = 0.45
    ) -> None:
        """Compatibilidad: acierto/fallo de ítem como evidencia de quiz."""
        self.apply_evidence(
            EvidenceSample(
                kind=EvidenceKind.QUIZ_ITEM,
                score_ratio=score_ratio,
                weight=alpha / 0.45 if alpha else 1.0,
                document_id=document_id,
            )
        )

    def apply_evidence(self, sample: EvidenceSample, alpha: float = 0.45) -> None:
        ratio = max(0.0, min(1.0, float(sample.score_ratio)))
        w = max(0.05, min(2.0, float(sample.weight)))
        effective_alpha = max(0.05, min(0.9, alpha * w))

        # Ajustes por tipo de señal
        if sample.kind == EvidenceKind.HELP_REQUEST:
            self.help_requests += 1
            ratio = min(ratio, 0.45)
            effective_alpha = max(effective_alpha, 0.35)
        elif sample.kind == EvidenceKind.ASK_STRUGGLE:
            ratio = min(ratio, 0.35)
            effective_alpha = max(effective_alpha, 0.4)
        elif sample.kind == EvidenceKind.HIGH_LATENCY:
            # Latencia alta reduce confianza y tira ligeramente el mastery
            ratio = min(ratio, max(0.0, ratio - 0.15))
            effective_alpha = max(0.2, effective_alpha * 0.7)
        elif sample.kind == EvidenceKind.REPEATED_ERROR:
            ratio = min(ratio, 0.25)
            effective_alpha = max(effective_alpha, 0.5)
            self.error_streak += 1
        elif sample.kind in (EvidenceKind.QUIZ_ITEM, EvidenceKind.SUCCESS):
            if ratio < 0.5:
                self.error_streak += 1
            else:
                self.error_streak = 0

        if sample.help_level > 0:
            self.help_requests += 1 if sample.help_level >= 0.4 else 0
            # Más ayuda → menos crédito al acierto aparente
            ratio = ratio * (1.0 - 0.35 * max(0.0, min(1.0, sample.help_level)))

        self.attempts += 1
        self.evidence_count += 1
        self.last_score_ratio = ratio
        if self.attempts == 1:
            self.mastery = ratio
        else:
            self.mastery = (effective_alpha * ratio) + ((1.0 - effective_alpha) * self.mastery)

        # Confianza crece con evidencia consistente; baja con errores/ayuda
        conf_delta = 0.08 * w
        if ratio >= 0.7 and sample.kind != EvidenceKind.HELP_REQUEST:
            self.confidence = min(1.0, self.confidence + conf_delta)
        elif ratio < 0.5:
            self.confidence = max(0.0, self.confidence - conf_delta * 1.2)
        else:
            self.confidence = min(1.0, self.confidence + conf_delta * 0.4)
        if sample.kind == EvidenceKind.HELP_REQUEST:
            self.confidence = max(0.0, self.confidence - 0.05)

        if sample.latency_ms is not None and sample.latency_ms > 0:
            lat = float(sample.latency_ms)
            if self.latency_ms_ema <= 0:
                self.latency_ms_ema = lat
            else:
                self.latency_ms_ema = 0.3 * lat + 0.7 * self.latency_ms_ema

        if sample.document_id is not None and sample.document_id not in self.document_ids:
            self.document_ids.append(sample.document_id)
        if sample.subject:
            self.subject = _norm_concept(sample.subject)
        self.last_practiced_at = sample.at or _utc_now()

    def effective_mastery(self, now: datetime | None = None) -> float:
        """Mastery con decaimiento exponencial (Ebbinghaus). No castiga: recuerda repasar."""
        base = max(0.0, min(1.0, self.mastery))
        if self.last_practiced_at is None or self.attempts == 0:
            return base
        moment = now or _utc_now()
        practiced = self.last_practiced_at
        if practiced.tzinfo is None:
            practiced = practiced.replace(tzinfo=timezone.utc)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        days = max(0.0, (moment - practiced).total_seconds() / 86400.0)
        half = max(1.0, float(self.half_life_days or DEFAULT_HALF_LIFE_DAYS))
        # retention = 0.5 ** (days / half_life)
        retention = exp(-log(2.0) * days / half)
        # Confianza también decae (suave)
        conf_factor = 0.55 + 0.45 * max(0.0, min(1.0, self.confidence))
        return max(0.0, min(1.0, base * retention * (0.85 + 0.15 * conf_factor)))

    def forgetting_gap(self, now: datetime | None = None) -> float:
        """Cuánto cayó el mastery efectivo respecto al stored (0..1)."""
        stored = max(0.0, min(1.0, self.mastery))
        return max(0.0, stored - self.effective_mastery(now))


@dataclass
class DocumentMastery:
    """Dominio estimado de un documento a partir de intentos y señales ask."""

    document_id: UUID
    attempts: int = 0
    mastery: float = 0.0
    last_score_ratio: float = 0.0
    incorrect_streak: int = 0
    struggle_signals: int = 0

    def apply_result(self, score_ratio: float, alpha: float = 0.4) -> None:
        ratio = max(0.0, min(1.0, float(score_ratio)))
        self.attempts += 1
        self.last_score_ratio = ratio
        if self.attempts == 1:
            self.mastery = ratio
        else:
            self.mastery = (alpha * ratio) + ((1.0 - alpha) * self.mastery)
        if ratio < 0.5:
            self.incorrect_streak += 1
        else:
            self.incorrect_streak = 0

    def apply_soft_struggle(self, pull_toward: float = 0.2, weight: float = 0.5) -> None:
        target = max(0.0, min(1.0, pull_toward))
        w = max(0.0, min(1.0, weight))
        self.mastery = (w * target) + ((1.0 - w) * self.mastery)
        self.struggle_signals += 1
        self.last_score_ratio = min(self.last_score_ratio, target)


@dataclass
class StudentProfile:
    """Perfil cognitivo: mastery por documento/concepto + memoria pedagógica."""

    student_id: UUID
    mastery_by_document: dict[UUID, DocumentMastery] = field(default_factory=dict)
    mastery_by_concept: dict[str, ConceptMastery] = field(default_factory=dict)
    frequent_errors: list[str] = field(default_factory=list)
    pace: str = "steady"
    total_attempts: int = 0
    total_struggle_signals: int = 0
    pedagogical_memory: PedagogicalMemory = field(default_factory=PedagogicalMemory)
    learning_velocity: float = 0.0  # EMA de deltas de mastery
    updated_at: datetime = field(default_factory=_utc_now)
    version: int = 0

    @staticmethod
    def create(student_id: UUID) -> "StudentProfile":
        return StudentProfile(student_id=student_id)

    def mastery_for(self, document_id: UUID) -> float:
        entry = self.mastery_by_document.get(document_id)
        return entry.mastery if entry else 0.0

    def concept_mastery_for(self, concept: str) -> float:
        key = _norm_concept(concept)
        entry = self.mastery_by_concept.get(key)
        return entry.mastery if entry else 0.0

    def effective_concept_mastery(self, concept: str, now: datetime | None = None) -> float:
        key = _norm_concept(concept)
        entry = self.mastery_by_concept.get(key)
        return entry.effective_mastery(now) if entry else 0.0

    def record_quiz_result(
        self,
        document_id: UUID,
        score_ratio: float,
        missed_concepts: tuple[str, ...] = (),
        concept_results: tuple[tuple[str, float], ...] = (),
        latency_ms: float | None = None,
        help_level: float = 0.0,
    ) -> None:
        entry = self.mastery_by_document.get(document_id)
        if entry is None:
            entry = DocumentMastery(document_id=document_id)
            self.mastery_by_document[document_id] = entry
        before = entry.mastery
        entry.apply_result(score_ratio)
        self.total_attempts += 1
        self._track_velocity(entry.mastery - before)
        for concept, ratio in concept_results:
            kind = EvidenceKind.QUIZ_ITEM
            if ratio < 0.5:
                cm = self.mastery_by_concept.get(_norm_concept(concept))
                if cm and cm.error_streak >= 1:
                    kind = EvidenceKind.REPEATED_ERROR
            self.record_concept_evidence(
                concept,
                EvidenceSample(
                    kind=kind,
                    score_ratio=ratio,
                    document_id=document_id,
                    latency_ms=latency_ms,
                    help_level=help_level,
                ),
            )
        self._push_errors(missed_concepts)
        for m in missed_concepts:
            self.pedagogical_memory.remember_misconception(m)
        self._update_pace()
        self.updated_at = _utc_now()

    def record_concept_result(
        self,
        concept: str,
        score_ratio: float,
        document_id: UUID | None = None,
    ) -> None:
        self.record_concept_evidence(
            concept,
            EvidenceSample(
                kind=EvidenceKind.QUIZ_ITEM,
                score_ratio=score_ratio,
                document_id=document_id,
            ),
        )

    def record_concept_evidence(self, concept: str, sample: EvidenceSample) -> None:
        key = _norm_concept(concept)
        if not key:
            return
        entry = self.mastery_by_concept.get(key)
        if entry is None:
            entry = ConceptMastery(concept_key=key)
            self.mastery_by_concept[key] = entry
        before = entry.mastery
        entry.apply_evidence(sample)
        self._track_velocity(entry.mastery - before)
        if sample.score_ratio < 0.5:
            self._push_errors((key,))
            self.pedagogical_memory.remember_misconception(key)
        self.updated_at = _utc_now()

    def record_ask_struggle(
        self,
        document_id: UUID,
        strength: float = 0.7,
        concepts: tuple[str, ...] = (),
        latency_ms: float | None = None,
        help_level: float = 0.0,
    ) -> None:
        entry = self.mastery_by_document.get(document_id)
        if entry is None:
            entry = DocumentMastery(document_id=document_id)
            self.mastery_by_document[document_id] = entry
        pull = 0.15 + (0.25 * max(0.0, min(1.0, strength)))
        weight = 0.35 + (0.35 * max(0.0, min(1.0, strength)))
        entry.apply_soft_struggle(pull_toward=pull, weight=weight)
        self.total_struggle_signals += 1
        for concept in concepts:
            key = _norm_concept(concept)
            if not key:
                continue
            kind = EvidenceKind.HELP_REQUEST if help_level >= 0.4 else EvidenceKind.ASK_STRUGGLE
            self.record_concept_evidence(
                key,
                EvidenceSample(
                    kind=kind,
                    score_ratio=max(0.1, 1.0 - strength),
                    weight=0.6 + 0.4 * strength,
                    document_id=document_id,
                    latency_ms=latency_ms,
                    help_level=help_level or (0.5 if kind == EvidenceKind.HELP_REQUEST else 0.0),
                ),
            )
        self._push_errors(concepts)
        if entry.mastery < 0.4:
            self.pace = "slow"
        self.updated_at = _utc_now()

    def clear_document(self, document_id: UUID) -> None:
        self.mastery_by_document.pop(document_id, None)
        for cm in self.mastery_by_concept.values():
            if document_id in cm.document_ids:
                cm.document_ids = [d for d in cm.document_ids if d != document_id]
        self.updated_at = _utc_now()

    def weakest_concepts(
        self,
        limit: int = 5,
        document_id: UUID | None = None,
        *,
        use_effective: bool = True,
        now: datetime | None = None,
    ) -> list[str]:
        items = list(self.mastery_by_concept.values())
        if document_id is not None:
            items = [c for c in items if document_id in c.document_ids or not c.document_ids]

        def rank(c: ConceptMastery) -> tuple[float, int]:
            m = c.effective_mastery(now) if use_effective else c.mastery
            return (m, -c.attempts)

        ranked = sorted(items, key=rank)
        return [c.concept_key for c in ranked[:limit]]

    def forgotten_concepts(self, limit: int = 5, min_gap: float = 0.15) -> list[str]:
        ranked = sorted(
            self.mastery_by_concept.values(),
            key=lambda c: c.forgetting_gap(),
            reverse=True,
        )
        return [c.concept_key for c in ranked if c.forgetting_gap() >= min_gap][:limit]

    def mastered_concepts(
        self, limit: int = 5, min_mastery: float = 0.8, min_confidence: float = 0.55
    ) -> list[str]:
        items = [
            c
            for c in self.mastery_by_concept.values()
            if c.effective_mastery() >= min_mastery and c.confidence >= min_confidence
        ]
        ranked = sorted(items, key=lambda c: (c.effective_mastery(), c.confidence), reverse=True)
        return [c.concept_key for c in ranked[:limit]]

    def _push_errors(self, concepts: tuple[str, ...]) -> None:
        for concept in concepts:
            label = _norm_concept(concept)
            if not label:
                continue
            if label in self.frequent_errors:
                self.frequent_errors.remove(label)
            self.frequent_errors.insert(0, label)
        self.frequent_errors = self.frequent_errors[:20]

    def _track_velocity(self, delta: float) -> None:
        self.learning_velocity = 0.3 * delta + 0.7 * self.learning_velocity

    def _update_pace(self) -> None:
        if self.total_attempts <= 1 and self.total_struggle_signals == 0:
            self.pace = "steady"
            return
        weak = sum(1 for m in self.mastery_by_document.values() if m.mastery < 0.4)
        strong = sum(1 for m in self.mastery_by_document.values() if m.mastery >= 0.7)
        if self.learning_velocity < -0.05 or weak > strong:
            self.pace = "slow"
        elif self.learning_velocity > 0.08 and strong > weak and self.total_attempts >= 3:
            self.pace = "fast"
        else:
            self.pace = "steady"

    def weakest_documents(self, limit: int = 3) -> list[UUID]:
        ranked = sorted(
            self.mastery_by_document.values(),
            key=lambda m: (m.mastery, -m.attempts),
        )
        return [m.document_id for m in ranked[:limit]]
