"""Plantillas `responses` para routers FastAPI (documentación OpenAPI unificada)."""

from fastapi import status

from src.interfaces.schemas.http_errors import HTTPErrorBody

# Respuestas de error reutilizables (cada clave es un código HTTP documentado en /docs).

RESP_401_UNAUTHORIZED = {
    status.HTTP_401_UNAUTHORIZED: {
        "description": (
            "No autenticado: falta la cabecera `Authorization: Bearer <token>`, "
            "el JWT es inválido o ha expirado."
        ),
        "model": HTTPErrorBody,
    },
}

RESP_403_FORBIDDEN = {
    status.HTTP_403_FORBIDDEN: {
        "description": "Autenticado pero sin permisos sobre el recurso (p. ej. documento de otro usuario).",
        "model": HTTPErrorBody,
    },
}

RESP_404_NOT_FOUND = {
    status.HTTP_404_NOT_FOUND: {
        "description": "El recurso solicitado no existe en el sistema.",
        "model": HTTPErrorBody,
    },
}

RESP_409_CONFLICT = {
    status.HTTP_409_CONFLICT: {
        "description": "Conflicto de negocio: email o nombre de usuario ya registrado.",
        "model": HTTPErrorBody,
    },
}

RESP_422_VALIDATION = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "description": "El cuerpo o los parámetros no cumplen el esquema de validación (Pydantic).",
        "model": HTTPErrorBody,
    },
}
