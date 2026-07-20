from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.application.dto.document_dto import UploadDocumentDTO
from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.application.services.document_service import DocumentService
from src.interfaces.api.openapi_responses import (
    RESP_401_UNAUTHORIZED,
    RESP_403_FORBIDDEN,
    RESP_404_NOT_FOUND,
    RESP_422_VALIDATION,
)
from src.interfaces.api.dependencies import (
    get_analyze_service,
    get_current_user_id,
    get_document_service,
)
from src.interfaces.schemas.document_schemas import (
    AnalysisResponse,
    DocumentResponse,
    DocumentUploadRequest,
    QuestionRequest,
    QuestionResponse,
    QuizQuestionItem,
    QuizResponse,
)

router = APIRouter(prefix="/documents", tags=["Documentos"])


def _map(doc) -> DocumentResponse:
    return DocumentResponse(
        id=str(doc.id),
        owner_id=str(doc.owner_id),
        filename=doc.filename,
        subject=doc.subject.value if hasattr(doc.subject, 'value') else str(doc.subject),
        status=doc.status.value,
        uploaded_at=doc.uploaded_at,
        has_analysis=doc.has_analysis(),
        error_message=doc.error_message,
    )


@router.post(
    "/",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subir documento (texto)",
    description=(
        "Registra un material educativo asociado al usuario del JWT. "
        "El contenido se envía como texto en JSON (no multipart de archivo binario)."
    ),
    response_description="Metadatos del documento creado (incluye resultado de análisis previo si existiera).",
    responses={
        **RESP_401_UNAUTHORIZED,
        **RESP_422_VALIDATION,
    },
)
async def upload_document(
    body: DocumentUploadRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[DocumentService, Depends(get_document_service)],
):
    dto = UploadDocumentDTO(
        filename=body.filename,
        content=body.content,
        subject=body.subject,
    )
    doc = await service.upload(UUID(current_user_id), dto)
    return _map(doc)


@router.get(
    "/",
    response_model=list[DocumentResponse],
    summary="Listar mis documentos",
    description="Devuelve solo los documentos cuyo `owner_id` coincide con el usuario autenticado.",
    response_description="Lista de documentos del propietario.",
    responses={
        **RESP_401_UNAUTHORIZED,
    },
)
async def list_my_documents(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[DocumentService, Depends(get_document_service)],
):
    result = await service.list_by_owner(UUID(current_user_id))
    return [_map(d) for d in result.documents]


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Obtener documento por id",
    description=(
        "Recupera un documento solo si el solicitante es su propietario (`owner_id` = usuario del JWT)."
    ),
    response_description="Metadatos y estado de análisis del documento.",
    responses={
        **RESP_401_UNAUTHORIZED,
        **RESP_403_FORBIDDEN,
        **RESP_404_NOT_FOUND,
    },
)
async def get_document(
    document_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[DocumentService, Depends(get_document_service)],
):
    try:
        doc = await service.get_by_id(UUID(document_id), UUID(current_user_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return _map(doc)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar documento",
    description="Borra el documento si y solo si el usuario autenticado es el propietario.",
    response_description="Sin cuerpo en caso de éxito.",
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "Documento eliminado; no se devuelve JSON.",
        },
        **RESP_401_UNAUTHORIZED,
        **RESP_403_FORBIDDEN,
        **RESP_404_NOT_FOUND,
    },
)
async def delete_document(
    document_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[DocumentService, Depends(get_document_service)],
):
    try:
        await service.delete(UUID(document_id), UUID(current_user_id))
    except (ValueError, PermissionError) as exc:
        code = status.HTTP_403_FORBIDDEN if isinstance(exc, PermissionError) else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=str(exc))


@router.post(
    "/{document_id}/analyze",
    response_model=AnalysisResponse,
    summary="Analizar documento con IA",
    description=(
        "Solo el propietario del documento puede analizarlo. "
        "Si ya existe `analysis_result` guardado, se reutiliza la respuesta (sin llamar a la API de IA) "
        "salvo que se envíe `force_refresh=true`."
    ),
    response_description="Resumen, conceptos clave y preguntas sugeridas.",
    responses={
        **RESP_401_UNAUTHORIZED,
        **RESP_403_FORBIDDEN,
        **RESP_404_NOT_FOUND,
        **RESP_422_VALIDATION,
    },
)
async def analyze_document(
    document_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[AnalyzeDocumentService, Depends(get_analyze_service)],
    force_refresh: bool = Query(
        False,
        description="Si es true, ignora el análisis cacheado y vuelve a invocar a la IA.",
    ),
):
    try:
        analysis = await service.execute(UUID(document_id), UUID(current_user_id), force_refresh=force_refresh)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return AnalysisResponse(
        summary=analysis.summary,
        key_concepts=analysis.key_concepts,
        suggested_questions=analysis.suggested_questions,
    )


@router.post(
    "/{document_id}/ask",
    response_model=QuestionResponse,
    summary="Preguntar sobre el documento",
    description=(
        "Responde en lenguaje natural usando el texto del documento como contexto exclusivo. "
        "Solo el propietario del documento puede usar este endpoint."
    ),
    response_description="Respuesta del tutor virtual.",
    responses={
        **RESP_401_UNAUTHORIZED,
        **RESP_403_FORBIDDEN,
        **RESP_404_NOT_FOUND,
        **RESP_422_VALIDATION,
    },
)
async def ask_question(
    document_id: str,
    body: QuestionRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[AnalyzeDocumentService, Depends(get_analyze_service)],
):
    try:
        answer = await service.answer_question(UUID(document_id), body.question, UUID(current_user_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return QuestionResponse(answer=answer)


@router.post(
    "/{document_id}/quiz",
    response_model=QuizResponse,
    summary="Generar cuestionario",
    description=(
        "Genera una lista de preguntas de comprensión a partir del contenido del documento. "
        "Parámetro opcional `num_questions` (por defecto 5). Solo el propietario puede invocarlo."
    ),
    response_description="Cuestionario con preguntas de opción múltiple.",
    responses={
        **RESP_401_UNAUTHORIZED,
        **RESP_403_FORBIDDEN,
        **RESP_404_NOT_FOUND,
        **RESP_422_VALIDATION,
    },
)
async def generate_quiz(
    document_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[AnalyzeDocumentService, Depends(get_analyze_service)],
    num_questions: int = 5,
):
    try:
        quiz = await service.generate_quiz(UUID(document_id), UUID(current_user_id), num_questions=num_questions)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return QuizResponse(
        questions=[
            QuizQuestionItem(
                text=q.text,
                options=q.options,
                correct_answer=q.correct_answer,
                difficulty=q.difficulty,
            )
            for q in quiz.questions
        ],
        total_points=len(quiz.questions),
    )