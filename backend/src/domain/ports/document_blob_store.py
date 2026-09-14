from abc import ABC, abstractmethod


class DocumentBlobStore(ABC):
    """Almacenamiento de cuerpos de documentos fuera del documento BSON (p. ej. GridFS)."""

    @abstractmethod
    async def put(
        self,
        data: bytes,
        *,
        filename: str = "",
        content_type: str = "text/plain",
    ) -> str:
        """Persiste bytes y devuelve un identificador de blob."""
        ...

    @abstractmethod
    async def get(self, blob_id: str) -> bytes:
        """Recupera bytes por id. Lanza KeyError si no existe."""
        ...

    @abstractmethod
    async def delete(self, blob_id: str) -> None:
        """Elimina el blob si existe (idempotente)."""
        ...
