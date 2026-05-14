"""Proveedores de dependencias FastAPI: conectan los adaptadores a los servicios."""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.application.services.document_service import DocumentService
from src.application.services.user_service import UserService
from src.infrastructure.config import settings
from src.infrastructure.db.database import get_db_session
from src.infrastructure.db.document_repository_impl import SQLAlchemyDocumentRepository
from src.infrastructure.db.user_repository_impl import SQLAlchemyUserRepository
from src.infrastructure.kimi.kimi_ia_analyst import KimiIAAnalyst

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_user_service(session: Annotated[Session, Depends(get_db_session)]) -> UserService:
    repo = SQLAlchemyUserRepository(session)
    return UserService(repo)


def get_document_service(session: Annotated[Session, Depends(get_db_session)]) -> DocumentService:
    repo = SQLAlchemyDocumentRepository(session)
    return DocumentService(repo)


def get_analyze_service(session: Annotated[Session, Depends(get_db_session)]) -> AnalyzeDocumentService:
    doc_repo = SQLAlchemyDocumentRepository(session)
    ia = KimiIAAnalyst()
    return AnalyzeDocumentService(doc_repo, ia)


def get_current_user_id(token: Annotated[str, Depends(oauth2_scheme)]) -> int:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int | None = payload.get("sub")
        if user_id is None:
            raise credentials_error
        return int(user_id)
    except JWTError:
        raise credentials_error
