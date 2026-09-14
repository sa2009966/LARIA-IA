"""Tests de los refuerzos de seguridad: SECRET_KEY, bcrypt, RBAC y límites de entrada."""
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.domain.aggregates.user_aggregate import UserAggregate, UserRole
from src.domain.value_objects.password import Password
from src.infrastructure.config import Settings, validate_security_settings
from src.interfaces.schemas.document_schemas import DocumentUploadRequest
from src.interfaces.schemas.user_schemas import UserRegisterRequest


class TestSecretKeyValidation:
    def test_rechaza_clave_vacia(self):
        s = Settings(SECRET_KEY="", _env_file=None)
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            validate_security_settings(s)

    def test_rechaza_clave_por_defecto_conocida(self):
        s = Settings(SECRET_KEY="cambia-esto-en-produccion", _env_file=None)
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            validate_security_settings(s)

    def test_rechaza_clave_corta(self):
        s = Settings(SECRET_KEY="corta123", _env_file=None)
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            validate_security_settings(s)

    def test_acepta_clave_segura(self):
        s = Settings(SECRET_KEY="a" * 64, _env_file=None)
        validate_security_settings(s)


class TestBcryptHashing:
    def test_hash_usa_bcrypt(self):
        hashed = Password("SecurePass1x").hash()
        assert hashed.startswith("$2")

    def test_verify_correcto(self):
        hashed = Password("SecurePass1x").hash()
        assert Password.verify("SecurePass1x", hashed) is True

    def test_verify_incorrecto(self):
        hashed = Password("SecurePass1x").hash()
        assert Password.verify("otraClave123", hashed) is False

    def test_verify_hash_malformado(self):
        assert Password.verify("SecurePass1x", "no-es-un-hash") is False

    def test_hashes_distintos_por_salt(self):
        pw = Password("SecurePass1x")
        assert pw.hash() != pw.hash()


class TestRequireAdmin:
    @pytest.mark.asyncio
    async def test_admin_pasa(self):
        from src.interfaces.api.dependencies import require_admin

        admin = UserAggregate.register("root", "root@example.com", "SecurePass1x")
        admin.change_role(UserRole.ADMIN)
        result = await require_admin(admin)
        assert result is admin

    @pytest.mark.asyncio
    async def test_student_recibe_403(self):
        from src.interfaces.api.dependencies import require_admin

        student = UserAggregate.register("alu", "alu@example.com", "SecurePass1x")
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(student)
        assert exc_info.value.status_code == 403


class TestInputLimits:
    def test_content_demasiado_largo(self):
        with pytest.raises(ValidationError):
            DocumentUploadRequest(filename="a.txt", content="x" * 100_001, subject="Historia")

    def test_content_valido(self):
        req = DocumentUploadRequest(filename="a.txt", content="hola", subject="Historia")
        assert req.content == "hola"

    def test_register_password_min_length_schema(self):
        with pytest.raises(ValidationError):
            UserRegisterRequest(
                username="ana",
                email="ana@example.com",
                password="Short1x",
            )

    def test_register_ignora_campo_role(self):
        req = UserRegisterRequest(
            username="ana",
            email="ana@example.com",
            password="SecurePass1x",
            role="admin",
        )
        assert not hasattr(req, "role")

    def test_register_rechaza_password_debil_en_dominio(self):
        with pytest.raises(ValueError, match="débil"):
            UserAggregate.register("ana", "ana@example.com", "passwordpassword")

