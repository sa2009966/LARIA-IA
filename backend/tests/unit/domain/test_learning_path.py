import pytest
from uuid import uuid4

from src.domain.aggregates.learning_path import LearningPathAggregate
from src.domain.value_objects.question import Difficulty


class TestLearningPathAggregate:

    def test_create_requires_subject(self):
        with pytest.raises(ValueError, match="materia"):
            LearningPathAggregate.create(owner_id=uuid4(), subject="   ")

    def test_create_default_modules_unlock_first(self):
        path = LearningPathAggregate.create(
            owner_id=uuid4(),
            subject="Matemática",
            modules=[
                {"concept": "grafos"},
                {"concept": "bfs", "prerequisites": ["grafos"]},
            ],
        )
        assert len(path.modules) == 2
        assert path.modules[0].status == "available"
        assert path.modules[1].status == "locked"
        assert path.modules[0].position == 0
        assert path.modules[1].position == 1

    def test_create_canonicalizes_concepts(self):
        path = LearningPathAggregate.create(
            owner_id=uuid4(),
            subject="Matemática",
            modules=[{"concept": "Grafos"}],
        )
        assert path.modules[0].concept == "grafos"

    def test_create_skips_empty_concepts(self):
        path = LearningPathAggregate.create(
            owner_id=uuid4(),
            subject="Matemática",
            modules=[{"concept": "   "}, {"concept": "dfs"}],
        )
        assert len(path.modules) == 1

    def test_record_mastery_completes_and_unlocks(self):
        path = LearningPathAggregate.create(
            owner_id=uuid4(),
            subject="Matemática",
            modules=[
                {"concept": "grafos"},
                {"concept": "bfs", "prerequisites": ["grafos"]},
            ],
        )
        path.record_mastery("grafos", 0.9)
        assert path.modules[0].status == "completed"
        assert path.modules[1].status == "available"
        assert path.modules[0].mastery == pytest.approx(0.9)

    def test_record_mastery_in_progress(self):
        path = LearningPathAggregate.create(
            owner_id=uuid4(),
            subject="Matemática",
            modules=[{"concept": "grafos"}],
        )
        path.record_mastery("grafos", 0.5)
        assert path.modules[0].status == "in_progress"

    def test_record_mastery_clamps(self):
        path = LearningPathAggregate.create(
            owner_id=uuid4(),
            subject="Matemática",
            modules=[{"concept": "grafos"}],
        )
        path.record_mastery("grafos", 1.5)
        assert path.modules[0].mastery == 1.0

    def test_record_mastery_unknown_concept_noop(self):
        path = LearningPathAggregate.create(
            owner_id=uuid4(),
            subject="Matemática",
            modules=[{"concept": "grafos"}],
        )
        path.record_mastery("unknown", 0.8)
        assert path.progress == 0.0

    def test_progress_ratio(self):
        path = LearningPathAggregate.create(
            owner_id=uuid4(),
            subject="Matemática",
            modules=[
                {"concept": "grafos"},
                {"concept": "bfs", "prerequisites": ["grafos"]},
                {"concept": "dfs", "prerequisites": ["grafos"]},
            ],
        )
        assert path.progress == 0.0
        path.record_mastery("grafos", 0.9)
        path.record_mastery("bfs", 0.9)
        assert path.progress == pytest.approx(2 / 3)

    def test_locked_module_does_not_unlock_with_partial_prereq(self):
        path = LearningPathAggregate.create(
            owner_id=uuid4(),
            subject="Matemática",
            modules=[
                {"concept": "grafos"},
                {"concept": "bfs", "prerequisites": ["grafos"]},
            ],
        )
        # In-progress pero no completado → NO desbloquea dependiente
        path.record_mastery("grafos", 0.5)
        assert path.modules[1].status == "locked"

    def test_difficulty_assignment(self):
        path = LearningPathAggregate.create(
            owner_id=uuid4(),
            subject="Matemática",
            modules=[{"concept": "grafos", "difficulty": "hard"}],
        )
        assert path.modules[0].difficulty == Difficulty.HARD

    def test_is_owned_by(self):
        owner = uuid4()
        path = LearningPathAggregate.create(owner_id=owner, subject="M")
        assert path.is_owned_by(owner)
        assert not path.is_owned_by(uuid4())
