"""Suite API: chats CRUD + ownership via TestClient."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.application.services.chat_tutor_service import TutorResponse
from src.domain.ports.embodiment import AffectState
from src.domain.services.response_envelope import ResponseEnvelope
from src.main import app
from tests.conftest import clear_dependency_caches


@pytest.fixture
def client():
    clear_dependency_caches()
    with TestClient(app) as c:
        yield c
    clear_dependency_caches()


def _register_and_token(client, prefix):
    email = prefix + "_" + uuid4().hex[:8] + "@example.com"
    username = prefix + "_" + uuid4().hex[:6]
    r = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": "SecurePass1x"},
    )
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/token", data={"username": email, "password": "SecurePass1x"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


class TestChatsAPI:

    def test_create_chat_defaults(self, client):
        token = _register_and_token(client, "chat")
        r = client.post(
            "/api/v1/chats/",
            headers={"Authorization": "Bearer " + token},
            json={},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["title"] == "Nuevo chat"
        assert body["messages"] == []
        assert body["document_id"] is None

    def test_create_chat_with_title(self, client):
        token = _register_and_token(client, "chat")
        r = client.post(
            "/api/v1/chats/",
            headers={"Authorization": "Bearer " + token},
            json={"title": "Dudas de grafos"},
        )
        assert r.status_code == 201
        assert r.json()["title"] == "Dudas de grafos"

    def test_create_chat_with_document_id(self, client):
        token = _register_and_token(client, "chat")
        doc_id = str(uuid4())
        r = client.post(
            "/api/v1/chats/",
            headers={"Authorization": "Bearer " + token},
            json={"document_id": doc_id},
        )
        assert r.status_code == 201
        assert r.json()["document_id"] == doc_id

    def test_list_chats_empty(self, client):
        token = _register_and_token(client, "chat")
        r = client.get("/api/v1/chats/", headers={"Authorization": "Bearer " + token})
        assert r.status_code == 200
        assert r.json()["chats"] == []

    def test_list_chats_returns_summaries(self, client):
        token = _register_and_token(client, "chat")
        headers = {"Authorization": "Bearer " + token}
        client.post("/api/v1/chats/", headers=headers, json={"title": "A"})
        client.post("/api/v1/chats/", headers=headers, json={"title": "B"})

        r = client.get("/api/v1/chats/", headers=headers)
        assert r.status_code == 200
        chats = r.json()["chats"]
        assert len(chats) == 2
        for c in chats:
            assert "messages" not in c
            assert "message_count" in c
            assert "last_message_preview" in c

    def test_get_chat(self, client):
        token = _register_and_token(client, "chat")
        headers = {"Authorization": "Bearer " + token}
        created = client.post("/api/v1/chats/", headers=headers, json={"title": "X"}).json()

        r = client.get("/api/v1/chats/" + created["id"], headers=headers)
        assert r.status_code == 200
        assert r.json()["title"] == "X"

    def test_get_chat_not_found(self, client):
        token = _register_and_token(client, "chat")
        r = client.get("/api/v1/chats/" + str(uuid4()), headers={"Authorization": "Bearer " + token})
        assert r.status_code == 404
        assert r.json()["detail"] == "Recurso no encontrado"

    def test_update_chat_title(self, client):
        token = _register_and_token(client, "chat")
        headers = {"Authorization": "Bearer " + token}
        created = client.post("/api/v1/chats/", headers=headers, json={"title": "Original"}).json()

        r = client.put("/api/v1/chats/" + created["id"], headers=headers, json={"title": "Nuevo"})
        assert r.status_code == 200
        assert r.json()["title"] == "Nuevo"

    def test_update_chat_link_document(self, client):
        token = _register_and_token(client, "chat")
        headers = {"Authorization": "Bearer " + token}
        created = client.post("/api/v1/chats/", headers=headers, json={}).json()
        doc_id = str(uuid4())

        r = client.put("/api/v1/chats/" + created["id"], headers=headers, json={"document_id": doc_id})
        assert r.status_code == 200
        assert r.json()["document_id"] == doc_id

    def test_add_message(self, client, monkeypatch):
        token = _register_and_token(client, "chat")
        headers = {"Authorization": "Bearer " + token}
        created = client.post("/api/v1/chats/", headers=headers, json={"title": "Chat"}).json()

        class FakeTutor:
            async def answer(self, document_id, question, student_id):
                return TutorResponse(
                    content="Respuesta del tutor: " + question,
                    envelope=ResponseEnvelope(
                        type="answer",
                        emotion=AffectState.ENCOURAGING,
                        payload={"content": "Respuesta del tutor: " + question, "intent": "general"},
                    ),
                )

        from src.interfaces.api import dependencies

        app.dependency_overrides[dependencies.get_chat_tutor_service] = lambda: FakeTutor()

        r = client.post(
            "/api/v1/chats/" + created["id"] + "/messages",
            headers=headers,
            json={"role": "user", "content": "Hola tutor"},
        )
        assert r.status_code == 200
        messages = r.json()["messages"]
        assert len(messages) == 2
        assert messages[0]["content"] == "Hola tutor"
        assert messages[0]["role"] == "user"
        assert messages[1]["content"] == "Respuesta del tutor: Hola tutor"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["metadata"]["type"] == "answer"
        assert messages[1]["metadata"]["emotion"] == "encouraging"

    def test_add_message_with_metadata(self, client):
        token = _register_and_token(client, "chat")
        headers = {"Authorization": "Bearer " + token}
        created = client.post("/api/v1/chats/", headers=headers, json={}).json()

        r = client.post(
            "/api/v1/chats/" + created["id"] + "/messages",
            headers=headers,
            json={"role": "assistant", "content": "Respuesta", "metadata": {"source": "tutor"}},
        )
        assert r.status_code == 200
        assert r.json()["messages"][0]["metadata"] == {"source": "tutor"}

    def test_add_message_empty_422(self, client):
        token = _register_and_token(client, "chat")
        headers = {"Authorization": "Bearer " + token}
        created = client.post("/api/v1/chats/", headers=headers, json={}).json()

        r = client.post(
            "/api/v1/chats/" + created["id"] + "/messages",
            headers=headers,
            json={"role": "user", "content": ""},
        )
        assert r.status_code == 422

    def test_add_message_invalid_role_422(self, client):
        token = _register_and_token(client, "chat")
        headers = {"Authorization": "Bearer " + token}
        created = client.post("/api/v1/chats/", headers=headers, json={}).json()

        r = client.post(
            "/api/v1/chats/" + created["id"] + "/messages",
            headers=headers,
            json={"role": "admin", "content": "x"},
        )
        assert r.status_code == 422

    def test_delete_chat(self, client):
        token = _register_and_token(client, "chat")
        headers = {"Authorization": "Bearer " + token}
        created = client.post("/api/v1/chats/", headers=headers, json={}).json()

        r = client.delete("/api/v1/chats/" + created["id"], headers=headers)
        assert r.status_code == 204

        r = client.get("/api/v1/chats/" + created["id"], headers=headers)
        assert r.status_code == 404

    def test_ownership_user_a_cannot_access_user_b_chat(self, client):
        token_a = _register_and_token(client, "chata")
        token_b = _register_and_token(client, "chatb")
        created = client.post(
            "/api/v1/chats/",
            headers={"Authorization": "Bearer " + token_a},
            json={"title": "De A"},
        ).json()
        chat_id = created["id"]
        headers_b = {"Authorization": "Bearer " + token_b}

        r = client.get("/api/v1/chats/" + chat_id, headers=headers_b)
        assert r.status_code == 404

        r = client.put("/api/v1/chats/" + chat_id, headers=headers_b, json={"title": "hack"})
        assert r.status_code == 404

        r = client.post(
            "/api/v1/chats/" + chat_id + "/messages",
            headers=headers_b,
            json={"role": "user", "content": "inyectado"},
        )
        assert r.status_code == 404

        r = client.delete("/api/v1/chats/" + chat_id, headers=headers_b)
        assert r.status_code == 404

        r = client.get(
            "/api/v1/chats/" + chat_id,
            headers={"Authorization": "Bearer " + token_a},
        )
        assert r.status_code == 200
        assert r.json()["title"] == "De A"
        assert r.json()["messages"] == []

    def test_unauthenticated_401(self, client):
        r = client.get("/api/v1/chats/")
        assert r.status_code == 401

    def test_invalid_token_401(self, client):
        r = client.get("/api/v1/chats/", headers={"Authorization": "Bearer fake-token"})
        assert r.status_code == 401

    def test_add_message_user_tutor_error_fallback(self, client):
        token = _register_and_token(client, "chat")
        headers = {"Authorization": "Bearer " + token}
        created = client.post("/api/v1/chats/", headers=headers, json={}).json()

        # Simular que el tutor falla totalmente.
        class FailingTutor:
            async def answer(self, document_id, question, student_id):
                raise RuntimeError("boom")

        from src.interfaces.api import dependencies

        app.dependency_overrides[dependencies.get_chat_tutor_service] = lambda: FailingTutor()

        r = client.post(
            "/api/v1/chats/" + created["id"] + "/messages",
            headers=headers,
            json={"role": "user", "content": "pregunta que falla"},
        )
        assert r.status_code == 200
        messages = r.json()["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "system"
        assert messages[1]["metadata"]["source"] == "error"
        assert messages[1]["metadata"]["type"] == "error"

    def test_add_message_user_with_document_passes_doc_id(self, client):
        token = _register_and_token(client, "chat")
        headers = {"Authorization": "Bearer " + token}
        doc_id = str(uuid4())
        created = client.post(
            "/api/v1/chats/", headers=headers, json={"document_id": doc_id}
        ).json()

        captured = {}

        class CapturingTutor:
            async def answer(self, document_id, question, student_id):
                captured["document_id"] = document_id
                captured["question"] = question
                captured["student_id"] = student_id
                return TutorResponse(
                    content="ok",
                    envelope=ResponseEnvelope(
                        type="answer",
                        emotion=AffectState.CALM,
                        payload={"content": "ok", "intent": "learn"},
                    ),
                )

        from src.interfaces.api import dependencies

        app.dependency_overrides[dependencies.get_chat_tutor_service] = lambda: CapturingTutor()

        r = client.post(
            "/api/v1/chats/" + created["id"] + "/messages",
            headers=headers,
            json={"role": "user", "content": "explícame grafos"},
        )
        assert r.status_code == 200
        assert str(captured["document_id"]) == doc_id
        assert captured["question"] == "explícame grafos"
        assert captured["student_id"] is not None
