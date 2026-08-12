# Deploy en Render — demo efímera (NO producción)

> **Etiqueta:** el blueprint de [`render.yaml`](../../render.yaml) es una **demo efímera**.
> Usa `APP_ENV=development`, `DB_PROVIDER=memory`, `EVENT_BUS_BACKEND=memory` y
> `ENABLE_DOCS=true`. Los datos **no persisten** entre reinicios ni sleep del plan free.
>
> **Producción real** = Docker Compose local/servidor propio con Mongo + Redis +
> `APP_ENV=production` (`ENABLE_DOCS=false`, `EVENT_BUS_BACKEND=outbox`,
> `RATE_LIMIT_BACKEND=redis`, `CACHE_BACKEND=redis`). Ver
> [`production-checklist.md`](./production-checklist.md).
>
> **Staging recomendado:** misma forma Compose/prod en un VPS de equipo (secrets distintos).
> No usar Render free como staging con datos reales.

## Qué hay en el repo

| Archivo | Rol |
|---------|-----|
| [`render.yaml`](../../render.yaml) | Blueprint **demo** (`LARIA_DEPLOY_TIER=demo`, memory, plan free; servicio `laria-backend`) |
| [`Dockerfile`](../Dockerfile) | Imagen; escucha `$PORT` (Render) o `8000` |

## Pasos (GitHub ya conectado)

1. Sube/pushea `feature/backend` con `render.yaml` en la raíz del repo.
2. En [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint**.
3. Elige el repo `sa2009966/LARIA-IA`, rama `feature/backend`, path `render.yaml`.
4. En variables pendientes, pega tu **`OPENAI_API_KEY`**.
5. (Recomendado) edita **`CORS_ORIGINS`** con tu front de Vercel, p. ej.  
   `["https://tu-app.vercel.app","http://localhost:4321"]`
6. **Apply** / Deploy. Espera el build (~3–8 min en free).
7. URL pública actual: `https://laria-ia.onrender.com` (el blueprint nombra el servicio `laria-backend`; el subdominio real lo muestra Render).
8. Prueba: `GET https://laria-ia.onrender.com/health` y `GET https://laria-ia.onrender.com/ready`
9. En el frontend (Vercel): `PUBLIC_LARIA_API_URL=https://laria-ia.onrender.com`

`feature/backend` tiene **auto-deploy**. Un `git push` a esa rama actualiza el demo público. El hook Cursor (`.cursor/hooks/`) pide confirmación; `.githooks/pre-push` exige pytest en verde y bloquea force-push. Instalar el hook git en cada clon:

```bash
ln -sfn ../../.githooks/pre-push .git/hooks/pre-push
```

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
