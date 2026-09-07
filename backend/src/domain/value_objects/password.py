from dataclasses import dataclass

import bcrypt


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
        # bcrypt solo procesa los primeros 72 bytes; se truncan explícitamente.
        return bcrypt.hashpw(self.value.encode("utf-8")[:72], bcrypt.gensalt()).decode("ascii")

    @staticmethod
    def verify(plain_password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed.encode("ascii"))
        except ValueError:
            # Hash malformado o de un esquema antiguo no soportado.
            return False

    def __str__(self) -> str:
        return "****"

    def __repr__(self) -> str:
        return "Password(****)"
