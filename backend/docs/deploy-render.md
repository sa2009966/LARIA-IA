# Deploy en Render — backend LARIA

## Qué hay en el repo

| Archivo | Rol |
|---------|-----|
| [`render.yaml`](../../render.yaml) | Blueprint (Web Service Docker, plan free) |
| [`Dockerfile`](../Dockerfile) | Imagen; escucha `$PORT` (Render) o `8000` |

## Pasos (GitHub ya conectado)

1. Sube/pushea `feature/backend` con `render.yaml` en la raíz del repo.
2. En [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint**.
3. Elige el repo `sa2009966/LARIA-IA`, rama `feature/backend`, path `render.yaml`.
4. En variables pendientes, pega tu **`OPENAI_API_KEY`**.
5. (Recomendado) edita **`CORS_ORIGINS`** con tu front de Vercel, p. ej.  
   `["https://tu-app.vercel.app","http://localhost:4321"]`
6. **Apply** / Deploy. Espera el build (~3–8 min en free).
7. URL del servicio: `https://laria-backend.onrender.com` (el subdominio exacto lo muestra Render).
8. Prueba: `GET https://<tu-servicio>.onrender.com/health`
9. En el frontend (Vercel / otra PC): `PUBLIC_API_URL=https://<tu-servicio>.onrender.com`

## Notas

- Plan **free** se duerme sin tráfico; el primer request puede tardar ~1 min.
- **Persistencia en Render:** el Web Service en la nube **no puede** usar el Mongo Docker de tu laptop (`localhost`). Este proyecto **no usa MongoDB Atlas**. En Render la demo sigue con `DB_PROVIDER=memory` (datos no persisten entre reinicios) hasta que exista un Mongo **alcanzable desde Render** (host propio / túnel / otro proveedor). Desarrollo local: Docker Compose + `DB_PROVIDER=mongodb` + GridFS.
- Uploads grandes (hasta 200 MiB vía GridFS) requieren Mongo; en `memory` el blob queda solo en proceso.
- No subas `.env` ni keys a git; solo variables en el dashboard de Render.

## Deploy automático vía API (opcional)

Si tienes una API Key de Render (`rnd_...`):

```bash
cd ~/Descargas/Laria_ia/LARIA-IA
export RENDER_API_KEY='rnd_...'   # Account Settings → API Keys
./backend/scripts/deploy-render-api.sh
```

El script lee `OPENAI_API_KEY` de `backend/.env` (gitignored), genera `SECRET_KEY`, crea/actualiza `laria-backend` y dispara el deploy. **No imprime secretos.**


Root Directory: `backend`  
Dockerfile Path: `./Dockerfile` (con root `backend`) o `backend/Dockerfile` desde la raíz del repo  
Start / Docker Command: `sh -c 'uvicorn src.main:app --host 0.0.0.0 --port $PORT'`  
Health Check Path: `/health`  
Branch: `feature/backend`
