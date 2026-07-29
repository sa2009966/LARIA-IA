# LARIA-IA

Tutor inteligente adaptativo. Monorepo:

| Carpeta | Contenido |
|---------|-----------|
| `backend/` | API FastAPI (rama `feature/backend`) |
| [`frontend/`](frontend/) | Cliente Astro + React (esta rama) |

## Frontend

```bash
cd frontend
cp .env.example .env
pnpm install && pnpm dev
```

Ver [`frontend/README.md`](frontend/README.md).

## Ramas

```
feature/backend   → develop
feature/frontend  → develop
develop           → main
```
