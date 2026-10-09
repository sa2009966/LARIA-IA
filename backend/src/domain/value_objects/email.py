import re
from dataclasses import dataclass


_EMAIL_PATTERN = re.compile(r'^[\w.+-]+@[\w-]+\.[\w.-]+$')


@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self):
        # Un correo es el mismo con o sin mayúsculas. Sin normalizar, "Ana@x.com" (con
        # contraseña) y "ana@x.com" (Clerk, que lo da en minúsculas) eran dos cuentas.
        object.__setattr__(self, "value", (self.value or "").strip().lower())
        if not _EMAIL_PATTERN.match(self.value):
            raise ValueError(f"Email invalido: {self.value}")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"Email({self.value})"
