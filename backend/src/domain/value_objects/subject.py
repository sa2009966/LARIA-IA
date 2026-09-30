from dataclasses import dataclass


_WHITELIST = frozenset({
    "Matemática", "Matematicas", "Ciencias", "Física", "Fisica",
    "Química", "Quimica", "Biología", "Biologia", "Historia",
    "Geografía", "Geografia", "Lengua", "Literatura", "Filosofía", "Filosofia",
    "Inglés", "Ingles", "Educación Física", "Educacion Fisica", "Artística",
    "General",
})

#: Materia de lo que se sube sin decir cuál. El chat nunca la pregunta: exigirla
#: hacía que TODA subida desde el chat diera 422 "Field required". No tiene área
#: en `subject_areas`, así que no filtra ninguna heurística, que es lo seguro; una
#: materia fija ("Matemática") sí habría contaminado etiquetas y señales.
DEFAULT_SUBJECT = "General"


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
