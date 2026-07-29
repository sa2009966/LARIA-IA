# Documentación del backend LARIA

Índice de la documentación técnica del servicio API.

| Documento | Descripción |
|-----------|-------------|
| [backend.md](backend.md) | Overview del servicio, stack, arranque, ramas, checklist pre-merge |
| [architecture.md](architecture.md) | Arquitectura hexagonal / DDD, capas y flujos |
| [endpoints.md](endpoints.md) | Catálogo REST `/api/v1` |
| [mongodb-schema.md](mongodb-schema.md) | Colecciones MongoDB, campos, índices y diagramas ER |
| [mongodb-viewer.md](mongodb-viewer.md) | Cómo visualizar la BD (extensión Cursor / Compass / mongosh) |
| [gantt-compliance.md](gantt-compliance.md) | Evaluación backend vs diagrama de Gantt del proyecto |
| [deploy-render.md](deploy-render.md) | Despliegue en Render (Blueprint + variables) |
| [adr/ADR-001-openai-hexagonal-tutor.md](adr/ADR-001-openai-hexagonal-tutor.md) | ADR-1: decisiones fundacionales |
| [adr/ADR-002-embodiment-adapter.md](adr/ADR-002-embodiment-adapter.md) | ADR-2: embodiment opcional |
| [adr/ADR-003-mastery-forgetting-prereqs.md](adr/ADR-003-mastery-forgetting-prereqs.md) | ADR-3: mastery multi-señal, olvido y prerrequisitos |

Swagger interactivo (solo con `ENABLE_DOCS=true`): `/docs`.

Diagrama interactivo (abrir en el navegador): [mongodb-er.html](mongodb-er.html).
