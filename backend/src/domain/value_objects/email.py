import re
from dataclasses import dataclass


_EMAIL_PATTERN = re.compile(r'^[\w.+-]+@[\w-]+\.[\w.-]+$')


@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self):
        if not _EMAIL_PATTERN.match(self.value):
            raise ValueError(f"Email invalido: {self.value}")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"Email({self.value})"
