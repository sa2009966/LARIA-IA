import hashlib
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class Password:
    MIN_LENGTH = 8

    value: str

    def __post_init__(self):
        if len(str(self.value)) < self.MIN_LENGTH:
            raise ValueError(f"Password must be at least {self.MIN_LENGTH} characters")

    def is_weak(self) -> bool:
        return len(self.value) < 12 or not self._has_mixed_case() or not self._has_digit()

    def _has_mixed_case(self) -> bool:
        return any(c.isupper() for c in self.value) and any(c.islower() for c in self.value)

    def _has_digit(self) -> bool:
        return any(c.isdigit() for c in self.value)

    def hash(self) -> str:
        salt = secrets.token_hex(16)
        return f"{salt}${hashlib.sha256((salt + self.value).encode()).hexdigest()}"

    @staticmethod
    def verify(plain_password: str, hashed: str) -> bool:
        parts = hashed.split("$")
        if len(parts) != 2:
            return False
        salt, digest = parts
        return hashlib.sha256((salt + plain_password).encode()).hexdigest() == digest

    def __str__(self) -> str:
        return "****"

    def __repr__(self) -> str:
        return "Password(****)"
