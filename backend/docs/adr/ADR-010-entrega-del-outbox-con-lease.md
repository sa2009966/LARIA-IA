# ADR-010: El outbox entrega una vez por intento — reclamación con lease

- **Estado:** Aceptado
- **Fecha:** 2026-09-18
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Depende de:** [ADR-004](ADR-004-adaptacion-por-senales.md) (único escritor del perfil)
- **Implementa:** fase 3 de [`4_PLAN_CORRECCION.md`](../4_PLAN_CORRECCION.md)

## Contexto

`APP_ENV=production` exige `EVENT_BUS_BACKEND=outbox`. Antes de encenderlo había que mirar cómo
entregaba de verdad:

```python
cursor = db.event_outbox.find({"processed_at": None}).sort("created_at", 1).limit(limit)
async for row in cursor:
    ...procesar...
    await db.event_outbox.update_one({"_id": row["_id"]}, {"$set": {"processed_at": now}})
```

Se leen los pendientes y se marcan **después** de procesarlos. En la ventana entre la lectura y la
marca, cualquier otro proceso que lea la misma colección se lleva los mismos eventos. Eso pasa en
dos situaciones nada exóticas: dos réplicas, y el solapamiento de un rolling deploy. El resultado
son interacciones duplicadas y contadores inflados.

`StudentProfile.applied_event_ids` amortigua el daño —el segundo intento no vuelve a aplicar la
evidencia—, pero es una red de seguridad, no un mecanismo de entrega: el `TutorInteraction` del
intento de quiz se guarda antes de esa comprobación.

## Decisión

**Reclamación atómica con lease.** El worker no lee: toma.

```python
find_one_and_update(
    {"processed_at": None,
     "$or": [{"claimed_at": None}, {"claimed_at": {"$exists": False}},
             {"claimed_at": {"$lt": ahora - lease}}]},
    {"$set": {"claimed_at": ahora}},
    sort=[("created_at", 1)],
    return_document=AFTER,
)
```

1. **Un evento, un dueño.** `find_one_and_update` es atómico en Mongo: dos réplicas no pueden
   llevarse la misma fila.
2. **El lease (60 s) evita que un evento quede atrapado.** Si el proceso muere a mitad del handler,
   la reclamación caduca y otro worker lo retoma. La entrega es *at-least-once*, y la idempotencia
   por `event_id` del perfil es lo que la vuelve segura.
3. **El fallo del handler NO suelta la reclamación.** Se registra `last_error` y se incrementa
   `attempts`; el reintento espera a que caduque el lease. Soltarla en el acto hacía que el mismo
   evento se reintentara en bucle dentro del propio lote y lo quemara entero con un solo fallo.
4. **Índice que lo sostiene:** `(processed_at, claimed_at, created_at)`.
5. **Backoff en `with_concurrency_retry`:** exponencial con jitter, acotado a 0.5 s. Tres reintentos
   inmediatos contra un conflicto de versión son tres colisiones más, porque los escritores rivales
   vuelven a chocar en el mismo instante (W12 de la auditoría).

## Lo que esto cambia sobre W2 (y por qué no se reescribe el dedup)

El plan pedía sustituir el techo de 256 `applied_event_ids` por un TTL. Al implementar la
reclamación, la premisa de W2 dejó de sostenerse y **se decide no hacerlo**:

- El escenario del que hablaba la auditoría —"tras un restart el outbox re-procesa todo"— ya no
  existe: una fila con `processed_at` no se vuelve a leer nunca. La re-entrega solo ocurre por
  caducidad de lease, es decir dentro de ~60 s del intento original.
- El tope descarta siempre lo **más antiguo**, así que los eventos de esa ventana están siempre
  presentes. Con 256 entradas por estudiante, la red de seguridad cubre de sobra el único caso de
  re-entrega que queda.
- Cambiar el campo a entradas con fecha exige migrar documentos ya escritos para cerrar un riesgo
  que la decisión 1 acaba de eliminar. El coste no se paga solo.

Queda anotado como decisión, no como olvido: si algún día se re-entregan eventos masivamente (una
reindexación, un replay manual), hay que volver aquí antes de hacerlo.

## Consecuencias

- Con dos réplicas, cada evento se proyecta una vez. Blindado en
  `test_dos_workers_no_se_llevan_el_mismo_evento` y `test_una_reclamacion_caducada_la_retoma_otro_worker`.
- Un handler que tarde más que el lease provoca un segundo intento en paralelo; la evidencia no se
  duplica (dedup + versionado optimista), pero conviene que `lease_seconds` sea mayor que el handler
  más lento. 60 s es holgado para el projector actual.
- `attempts` y `last_error` pasan a ser observables útiles: un evento con `attempts` alto es un
  handler que falla siempre, no un pico de carga.
- Las filas viejas ya escritas no tienen `claimed_at`; el filtro las acepta con `$exists: false`.

## Fuera de alcance

- **Cola de fallidos (DLQ)** tras N intentos: hoy un evento que siempre falla se reintenta cada
  lease indefinidamente. Con `attempts` ya se puede detectar; falta decidir qué hacer con él.
- **Varios workers por réplica**: el lease lo soporta, pero nadie lo necesita todavía.
