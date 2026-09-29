"""Borrar una cuenta y todo lo que es de esa persona (ADR-019).

Hasta ahora no existía: el único `DELETE /users/{id}` era de administrador y solo
**desactivaba** la cuenta. Perfil, chats, documentos, originales en R2, intentos e
interacciones se quedaban para siempre. Los términos no podían prometer un
borrado que el sistema no hacía.
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable, Sequence
from uuid import UUID

from src.application.services.document_service import DocumentService
from src.domain.ports.repositories import (
    ChatRepository,
    DocumentRepository,
    LearningPathRepository,
    QuizAttemptRepository,
    QuizRepository,
    StudentProfileRepository,
    TutorInteractionRepository,
    TutorSessionRepository,
    UserRepository,
)
from src.domain.value_objects.password import Password

logger = logging.getLogger("laria.account")

#: Limpieza adicional que depende de la infraestructura (p. ej. eventos antiguos
#: en el outbox de Mongo). Devuelve cuántos registros borró.
Purga = Callable[[UUID], Awaitable[int]]


class AccountService:
    _MSG_NO_ENCONTRADA = "Cuenta no encontrada"
    _MSG_CONTRASENA = "La contraseña no es correcta."

    def __init__(
        self,
        user_repository: UserRepository,
        document_repository: DocumentRepository,
        document_service: DocumentService,
        quiz_repository: QuizRepository,
        attempt_repository: QuizAttemptRepository,
        interaction_repository: TutorInteractionRepository,
        session_repository: TutorSessionRepository,
        profile_repository: StudentProfileRepository,
        chat_repository: ChatRepository,
        learning_path_repository: LearningPathRepository,
        extra_purges: Sequence[Purga] = (),
    ) -> None:
        self._users = user_repository
        self._docs = document_repository
        self._document_service = document_service
        self._quizzes = quiz_repository
        self._attempts = attempt_repository
        self._interactions = interaction_repository
        self._sessions = session_repository
        self._profiles = profile_repository
        self._chats = chat_repository
        self._paths = learning_path_repository
        self._extra = tuple(extra_purges)

    async def delete_account(self, user_id: UUID, password: str) -> dict[str, int]:
        """Borra la cuenta y todos sus datos. Devuelve cuánto se borró de cada cosa.

        Pide la contraseña aunque la petición ya venga autenticada: un token
        robado no debe bastar para destruir la cuenta de alguien.

        La cuenta se borra **al final**. Si algo falla a mitad, la persona sigue
        pudiendo entrar y repetirlo; y como cada paso borra lo que encuentre,
        repetir es seguro.
        """
        user = await self._users.find_by_id(user_id)
        if user is None:
            raise ValueError(self._MSG_NO_ENCONTRADA)
        if not Password.verify(password or "", user.hashed_password):
            raise PermissionError(self._MSG_CONTRASENA)

        borrado: dict[str, int] = {}

        # Los documentos van por su propio servicio: ya sabe borrar en cascada
        # sus quizzes, intentos, interacciones, sesiones y el original en R2.
        documentos = await self._docs.find_by_owner(user_id)
        for doc in documentos:
            await self._document_service.delete(doc.id, user_id)
        borrado["documentos"] = len(documentos)

        # Lo que no cuelga de ningún documento: nivelaciones por tema y su rastro.
        borrado["cuestionarios"] = await self._quizzes.delete_by_owner(user_id)
        borrado["intentos"] = await self._attempts.delete_by_student(user_id)
        borrado["interacciones"] = await self._interactions.delete_by_student(user_id)
        borrado["sesiones"] = await self._sessions.delete_by_student(user_id)

        chats = await self._chats.find_by_owner(user_id)
        for chat in chats:
            await self._chats.delete(chat.id)
        borrado["chats"] = len(chats)

        rutas = await self._paths.find_by_owner(user_id)
        for ruta in rutas:
            await self._paths.delete(ruta.id)
        borrado["rutas"] = len(rutas)

        # Segunda excepción, deliberada, a la invariante 1 (el perfil lo escribe
        # solo el projector): borrar la cuenta borra el perfil. No escribe
        # evidencia; la elimina junto con la persona.
        await self._profiles.delete(user_id)

        for purga in self._extra:
            borrado["eventos"] = borrado.get("eventos", 0) + await purga(user_id)

        await self._users.delete(user_id)
        # Sin email ni nombre en el log: solo el id, que ya no apunta a nadie.
        logger.info("cuenta_borrada user=%s %s", user_id, borrado)
        return borrado
