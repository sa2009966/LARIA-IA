# Visualizar MongoDB de LARIA

En Compose de producción el puerto `27017` **no** se publica al host (seguridad). Para explorar la BD en local tienes tres opciones.

## Opción A — Extensión en Cursor (recomendada)

1. Instala la extensión oficial:
   - Marketplace: **MongoDB for VS Code** (`mongodb.mongodb-vscode`)
   - O desde la terminal (en tu usuario, no root):

```bash
cursor --install-extension mongodb.mongodb-vscode
```

2. Publica Mongo solo en desarrollo (override):

```bash
cd backend
docker compose -f docker-compose.yml -f docker-compose.dev-ports.yml up -d mongodb
```

3. En Cursor: panel **MongoDB** → **Add Connection** → URI:

```text
mongodb://USER:PASSWORD@localhost:27017/?authSource=admin
```

Usa `MONGO_USERNAME` / `MONGO_PASSWORD` de tu `.env`. Base: `laria_db`.

4. Explora colecciones: `users`, `documents`, `quizzes`, `quiz_attempts`, `tutor_interactions`, `tutor_sessions`, `student_profiles`, `event_outbox`.

El repo recomienda la extensión en `backend/.vscode/extensions.json`.

## Opción B — MongoDB Compass (GUI de escritorio)

1. Descarga: https://www.mongodb.com/products/tools/compass  
2. Misma URI que arriba (con override de puertos).  
3. Abre `laria_db` y revisa documentos.

## Opción C — mongosh dentro del contenedor (sin abrir puerto)

```bash
cd backend
docker compose exec mongodb mongosh -u "$MONGO_USERNAME" -p "$MONGO_PASSWORD" --authenticationDatabase admin laria_db
```

Ejemplos:

```javascript
show collections
db.users.find().limit(2)
db.documents.find({}, { content: 0 }).limit(2)
db.student_profiles.findOne()
```

## Diagrama de esquema (sin datos vivos)

- Markdown + Mermaid: [mongodb-schema.md](mongodb-schema.md)
- HTML interactivo: [mongodb-er.html](mongodb-er.html) (ábrelo en el navegador)
