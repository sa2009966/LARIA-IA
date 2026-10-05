# ADR-038: El tutorial de bienvenida se recuerda en la cuenta

- **Estado:** Aceptado · **Fecha:** 2026-10-05

## Contexto
- Quien entra por primera vez no sabe qué puede hacer LARIA: nivelación, clases por
  tramos, documentos, voz y metas.
- Si "ya lo vio" se guardara en el navegador (`localStorage`), el tutorial
  reaparecería en cada dispositivo nuevo y tras borrar los datos del navegador.

## Decisión
- `UserAggregate.onboarding_completed_at`: la fecha en que terminó o saltó el tutorial.
  Es idempotente: repetirlo no mueve la fecha.
- `GET /users/me` incluye `onboarding_completed` (bool). `POST /users/me/onboarding`
  lo marca y devuelve el usuario.
- **Cuentas anteriores a este ADR:** en Mongo, el documento sin la clave cuenta como
  visto (se toma `created_at`), porque esas personas ya conocen Plenum. Una cuenta
  nueva guarda `None` explícito y ve el tutorial.
- Es un dato de la cuenta, no del aprendizaje. No pasa por eventos ni por el perfil
  cognitivo (la invariante 1 no aplica), y se borra con la cuenta.
- El contenido y el diseño del tutorial son del frontend.

## Verificado
- `tests/api/test_tutorial_bienvenida.py`: cuenta nueva → `false` → POST → `true`
  en cualquier petición; sin sesión 401; y la compatibilidad de Mongo con cuentas antiguas.
