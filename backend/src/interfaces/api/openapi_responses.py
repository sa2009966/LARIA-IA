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
        "description": (
            "Autenticado pero con rol insuficiente (p. ej. se requiere `admin`). "
            "Ownership de documentos/quizzes ajenos responde 404, no 403."
        ),
        "model": HTTPErrorBody,
    },
}

RESP_404_NOT_FOUND = {
    status.HTTP_404_NOT_FOUND: {
        "description": (
            "El recurso no existe o no es accesible. "
            "Documentos y quizzes ajenos responden 404 (no 403); "
            "el cuerpo HTTP sigue siendo genérico."
        ),
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

RESP_429_RATE_LIMIT = {
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "description": (
            "Demasiadas solicitudes para esta IP y ruta. "
            "Reintentar tras el valor de `Retry-After` (segundos)."
        ),
        "model": HTTPErrorBody,
    },
}

RESP_500_INTERNAL = {
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": (
            "Error no controlado en el servidor. "
            "El cuerpo es genérico (`detail`); sin stack trace ni secretos."
        ),
        "model": HTTPErrorBody,
    },
}

RESP_502_BAD_GATEWAY = {
    status.HTTP_502_BAD_GATEWAY: {
        "description": (
            "El proveedor de IA falló (`IAAnalysisError`). "
            "El detalle no incluye secretos ni el prompt completo."
        ),
        "model": HTTPErrorBody,
    },
}
