from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.application.services.document_service import DocumentService
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
)

router = APIRouter(prefix="/documents", tags=["Documentos"])


def _map(doc) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        owner_id=doc.owner_id,
        filename=doc.filename,
        subject=doc.subject,
        uploaded_at=doc.uploaded_at,
        analysis_result=doc.analysis_result,
    )


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    body: DocumentUploadRequest,
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    service: Annotated[DocumentService, Depends(get_document_service)],
):
    doc = service.upload(current_user_id, body.filename, body.content, body.subject)
    return _map(doc)


@router.get("/", response_model=list[DocumentResponse])
def list_my_documents(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    service: Annotated[DocumentService, Depends(get_document_service)],
):
    return [_map(d) for d in service.list_by_owner(current_user_id)]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    _: Annotated[int, Depends(get_current_user_id)],
    service: Annotated[DocumentService, Depends(get_document_service)],
):
    try:
        doc = service.get_by_id(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _map(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    service: Annotated[DocumentService, Depends(get_document_service)],
):
    try:
        service.delete(document_id, current_user_id)
    except (ValueError, PermissionError) as exc:
        code = status.HTTP_403_FORBIDDEN if isinstance(exc, PermissionError) else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=str(exc))


@router.post("/{document_id}/analyze", response_model=AnalysisResponse)
def analyze_document(
    document_id: int,
    _: Annotated[int, Depends(get_current_user_id)],
    service: Annotated[AnalyzeDocumentService, Depends(get_analyze_service)],
):
    try:
        analysis = service.execute(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return AnalysisResponse(
        document_id=analysis.document_id,
        summary=analysis.summary,
        key_concepts=analysis.key_concepts,
        suggested_questions=analysis.suggested_questions,
        model_used=analysis.model_used,
    )


@router.post("/{document_id}/ask", response_model=QuestionResponse)
def ask_question(
    document_id: int,
    body: QuestionRequest,
    _: Annotated[int, Depends(get_current_user_id)],
    service: Annotated[AnalyzeDocumentService, Depends(get_analyze_service)],
):
    try:
        answer = service.answer_question(document_id, body.question)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return QuestionResponse(answer=answer)


@router.post("/{document_id}/quiz", response_model=list[str])
def generate_quiz(
    document_id: int,
    _: Annotated[int, Depends(get_current_user_id)],
    service: Annotated[AnalyzeDocumentService, Depends(get_analyze_service)],
    num_questions: int = 5,
):
    try:
        return service.generate_quiz(document_id, num_questions)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
