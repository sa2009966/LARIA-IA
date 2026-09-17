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
| [adr/ADR-004-adaptacion-por-senales.md](adr/ADR-004-adaptacion-por-senales.md) | ADR-4: señales, precedencia y familias de parámetros |
| [adr/ADR-005-grafo-prerrequisitos-curado.md](adr/ADR-005-grafo-prerrequisitos-curado.md) | ADR-5: grafo de prerrequisitos curado y persistido |
| [adr/ADR-006-oferta-vs-bloqueo.md](adr/ADR-006-oferta-vs-bloqueo.md) | ADR-6: oferta en vez de bloqueo |
| [adr/ADR-007-evidencia-ponderada-por-calidad.md](adr/ADR-007-evidencia-ponderada-por-calidad.md) | ADR-7: la evidencia se pesa por su calidad |
| [adr/ADR-008-progreso-derivado-no-declarado.md](adr/ADR-008-progreso-derivado-no-declarado.md) | ADR-8: el progreso se deriva de la evidencia, nadie lo declara |
| [adr/ADR-009-contabilidad-y-canal-positivo.md](adr/ADR-009-contabilidad-y-canal-positivo.md) | ADR-9: una observación por turno, y el logro se le dice al estudiante |

Swagger interactivo (solo con `ENABLE_DOCS=true`): `/docs`.

Diagrama interactivo (abrir en el navegador): [mongodb-er.html](mongodb-er.html).
