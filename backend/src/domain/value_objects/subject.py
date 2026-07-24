from dataclasses import dataclass


_WHITELIST = frozenset({
    "Matemática", "Matematicas", "Ciencias", "Física", "Fisica",
    "Química", "Quimica", "Biología", "Biologia", "Historia",
    "Geografía", "Geografia", "Lengua", "Literatura", "Filosofía", "Filosofia",
    "Inglés", "Ingles", "Educación Física", "Educacion Fisica", "Artística",
})


@dataclass(frozen=True)
class Subject:
    value: str

    def __post_init__(self):
        if self.value not in _WHITELIST:
            raise ValueError(
                f"Asunto invalido: {self.value}. Asuntos validos: {sorted(_WHITELIST)}"
            )

    def __str__(self) -> str:
        return self.value
