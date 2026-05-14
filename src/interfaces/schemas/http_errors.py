"""Modelos Pydantic para documentar errores HTTP en OpenAPI (`/docs`, `/openapi.json`)."""

from typing import Any

from pydantic import BaseModel, Field


class HTTPErrorBody(BaseModel):
    """Cuerpo habitual de `HTTPException` en FastAPI (`{"detail": ...}`)."""

    detail: str | list[Any] = Field(
        ...,
        description="Mensaje de error legible o, en 422, lista de errores por campo.",
        json_schema_extra={"examples": ["No se pudo validar las credenciales."]},
    )
