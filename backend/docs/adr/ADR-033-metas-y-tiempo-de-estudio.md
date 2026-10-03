# ADR-033: Metas y tiempo de estudio, contados por el servidor

- **Estado:** Aceptado · **Fecha:** 2026-10-02

## Decisión
- **Metas en el perfil, por evento** (`StudyGoalsChosenEvent`, invariante 1).
  Se leen y se cambian con `GET/PUT /learning/me/study-goals`:
  - `session_minutes`: 10, 20, 30, 45 o `null`;
  - `daily_goal_minutes`: 10, 15, 30, 45, 60 o `null`.
- **La sesión dimensiona la lección:**
  - con ≤10 min, explicaciones de 50-90 palabras;
  - con ≥30 min, de 150-250;
  - en otro caso, 80-180.
- **El tiempo lo cuenta el servidor**, no el navegador, para que valga entre
  dispositivos. `POST /learning/me/study-time {seconds, timezone}`, una vez por
  minuto mientras la clase está visible y hay actividad.
- **Cada aviso suma como mucho 60 s**, y nunca más que el tiempo real desde el
  aviso anterior (+5 s de margen). Dos pestañas avisando a la vez no cuentan
  doble; está probado con dos pestañas desfasadas 30 s durante 10 minutos.
- **El "hoy" es el de la zona horaria IANA del navegador.**
- **Racha:** días seguidos cumpliendo el objetivo, o estudiando algo si no hay
  objetivo. Hoy suma si ya se cumplió; si no, la racha de ayer sigue viva.
- **No es evidencia**, así que no va en el perfil: tiene su propia colección
  (`study_time`, por persona y día). Se borra con la cuenta.
