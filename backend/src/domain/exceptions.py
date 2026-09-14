"""Excepciones de dominio / infraestructura de persistencia visibles a aplicación."""


class ConcurrencyError(Exception):
    """Conflicto de versión optimista al persistir un agregado."""

    def __init__(self, message: str = "Conflicto de concurrencia al guardar") -> None:
        super().__init__(message)
