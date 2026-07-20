import pytest
from uuid import UUID

from src.domain.aggregates.user_aggregate import UserAggregate, UserRole


class TestUserAggregate:
    def test_register_creates_user(self):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        assert isinstance(user.id, UUID)
        assert user.username == "ana"
        assert user.email.value == "ana@example.com"
        assert user.role == UserRole.STUDENT
        assert user.is_active is True

    def test_register_emits_event(self):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        assert len(user.events) == 1
        assert user.events[0].event_type == "UserRegisteredEvent"
        assert user.events[0].email == "ana@example.com"

    def test_register_invalid_email(self):
        with pytest.raises(ValueError, match="Email invalido"):
            UserAggregate.register("ana", "invalido", "SecurePass1")

    def test_register_weak_password(self):
        with pytest.raises(ValueError, match="at least 8"):
            UserAggregate.register("ana", "ana@example.com", "Ab1")

    def test_deactivate_active_user(self):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        user.deactivate()
        assert user.is_active is False

    def test_deactivate_emits_event(self):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        prev_events = len(user.events)
        user.deactivate()
        assert len(user.events) == prev_events + 1
        assert user.events[-1].event_type == "UserDeactivatedEvent"

    def test_deactivate_already_inactive(self):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        user.deactivate()
        with pytest.raises(ValueError, match="already deactivated"):
            user.deactivate()

    def test_activate_inactive_user(self):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        user.deactivate()
        user.activate()
        assert user.is_active is True

    def test_activate_already_active(self):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        with pytest.raises(ValueError, match="already active"):
            user.activate()

    def test_change_role(self):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        user.change_role(UserRole.TEACHER)
        assert user.role == UserRole.TEACHER

    def test_change_role_admin(self):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        user.change_role(UserRole.ADMIN)
        assert user.role == UserRole.ADMIN
        assert user.is_admin() is True

    def test_is_admin_false_for_student(self):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        assert user.is_admin() is False

    def test_is_teacher_false_for_student(self):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        assert user.is_teacher() is False

    def test_is_teacher_true(self):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        user.change_role(UserRole.TEACHER)
        assert user.is_teacher() is True

    def test_clear_events(self):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        assert len(user.events) > 0
        user.clear_events()
        assert len(user.events) == 0

    def test_different_users_have_different_ids(self):
        u1 = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        u2 = UserAggregate.register("luis", "luis@example.com", "SecurePass2")
        assert u1.id != u2.id

    def test_register_without_events_saves_immutable(self):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")
        user.clear_events()
        assert user.is_active is True
        assert user.username == "ana"
