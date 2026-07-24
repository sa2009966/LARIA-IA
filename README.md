# LARIA-IA

Tutor inteligente adaptativo. Monorepo:

| Carpeta | Contenido |
|---------|-----------|
| [`backend/`](backend/) | API FastAPI (DDD / hexagonal, MongoDB, OpenAI) |
| [`frontend/`](frontend/) | Cliente (rama `feature/frontend`) |

## Backend (rápido)

```bash
cd backend
cp .env.example .env   # SECRET_KEY + OPENAI_API_KEY
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

Con Docker (desde `backend/`):

```bash
docker compose up --build -d
```

Documentación: [`backend/docs/`](backend/docs/).

## Ramas

```
feature/backend   → develop
feature/frontend  → develop
develop           → main
```
