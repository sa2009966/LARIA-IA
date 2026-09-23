# ADR-012: El tutor lee texto; el alumno descarga su archivo

- **Estado:** Aceptado
- **Fecha:** 2026-09-18
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Origen:** `BACKEND_ENDPOINT_SPEC.md` (petición del cliente web para previsualizar material)

## Contexto

El cliente pidió un endpoint para previsualizar y descargar el material subido. Al mirar qué
podíamos servir apareció un bug peor que la falta del endpoint.

`DocumentService._persist_upload` hacía esto:

```python
blob_id = await self._blob_store.put(raw, content_type="text/plain; charset=utf-8")
doc = DocumentAggregate.upload(..., content=text if blob_id is None else "", ...)
```

Es decir: extraía el texto del archivo con `parse_file`, **lo tiraba**, guardaba el **binario** en el
blob de contenido y dejaba `content=""`. Y al leerlo para el motor:

```python
raw = await self._blob_store.get(blob_id)
return raw.decode("utf-8", errors="replace")
```

**Consecuencia:** para todo PDF, DOCX, XLSX y PPTX subido por `POST /documents/upload`, lo que
llegaba al análisis, al tutor y a la generación de quizzes era el binario decodificado como UTF-8 con
caracteres de reemplazo. Mojibake. Solo `.txt`, `.md` y código funcionaban, porque ahí los bytes
originales *son* el texto.

No era latente: el blob store está cableado también en modo memoria, así que ocurría en desarrollo y
en el despliegue público. Ningún test lo cubría —por eso sobrevivió al commit de soporte
multi-formato— y el síntoma es silencioso: el sistema responde, con seguridad, sobre basura.

## Decisión

**Son dos cosas distintas con dos ciclos de vida distintos, y se guardan por separado.**

| | Texto extraído | Archivo original |
|---|---|---|
| Para qué | análisis, tutor, quizzes, evidencia | previsualizar y descargar |
| Tamaño | pequeño (KB) | grande (MB) |
| Dónde | `content_blob_id`, junto a los datos | `original_blob_id`, almacén de objetos |
| Tipo | `text/plain; charset=utf-8` | el real (`application/pdf`, …) |

1. El blob de contenido guarda **texto**, siempre. Es lo que `get_content()` decodifica.
2. El agregado gana `original_blob_id`, `original_content_type` y `original_size`. El MIME lo decide
   `file_parser.content_type_for()`, que es el módulo que ya conoce los formatos.
3. **El original solo se guarda cuando existe**: subir texto por JSON (`POST /documents/`) no crea
   original, porque el texto ya lo es. Nada de duplicar almacenamiento sin motivo.
4. El original vive detrás del **mismo puerto** `DocumentBlobStore`, en un colaborador propio
   (`original_blob_store`). Por defecto es el mismo almacén que el texto; con `ORIGINAL_STORAGE=r2`
   pasa a **Cloudflare R2** sin que el dominio lo note. Ese es el pago de la arquitectura hexagonal:
   cambiar dónde viven los libros del estudiante es escribir un adaptador.
5. El borrado del original lo hace **el servicio**, no el repositorio: el repo solo sabe de su propio
   almacén, y el original puede estar en otro. Best-effort — un huérfano en el bucket no puede
   impedir que el estudiante borre su material.

### Por qué R2 y no Drive ni una base relacional

- **Relacional (Postgres/Lambda):** no resuelve el problema —Postgres es peor almacén de blobs que
  GridFS— y reescribir 14 repositorios Motor, GridFS y el versionado optimista costaría semanas para
  que el alumno reciba exactamente la misma tutoría.
- **Google Drive:** funciona y el puerto lo admite, pero una *service account* no tiene cuota propia
  (hace falta una Shared Drive o delegación de dominio), y Drive no está pensado como almacén de
  objetos: cuotas por minuto, latencia alta y servido por rangos poco fiable, que es justo lo que
  necesita un `<iframe>` con un PDF.
- **R2:** 10 GB gratis, API S3-compatible, sin coste de egreso. El cliente de boto3 es síncrono, así
  que cada llamada va a un hilo (`asyncio.to_thread`): un `put` de 20 MB no puede bloquear el event
  loop, que es el mismo error que ya se corrigió en el rate limiter.

### Límite de subida: 200 MiB → 25 MiB

Atlas M0 son **512 MB para todo**: perfiles, chats, evidencia, outbox y blobs. Un límite de 200 MiB
permitía que dos archivos llenaran el cluster y tumbaran la persistencia recién montada. 25 MiB cubre
un libro de texto escaneado; cuando los originales estén en R2 se puede subir con criterio.

## Consecuencias

- Los PDF vuelven a analizarse por su contenido. **Los documentos subidos antes de este cambio
  siguen guardando el binario en el blob de texto**, pero sí se recuperan: el archivo original está
  intacto, así que `scripts/migrate_document_blobs.py` lo lee, le extrae el texto con el mismo parser
  y reapunta los campos. Lo que no arregla es el `analysis_result` ya calculado sobre mojibake: eso
  exige `POST /documents/{id}/analyze?force_refresh=true`, que cuesta una llamada al modelo por
  documento y se decide aparte.
- `GET /documents/{id}/content` —lo que pedía el spec— ya tiene de dónde leer: queda pendiente de
  implementar, con tres correcciones al spec que se acordarán aparte (404 en vez de 403 por
  ownership, `<img src>` no puede llevar el token, y `Content-Disposition` necesita `expose_headers`
  en CORS).
- `boto3` entra como dependencia de runtime. Se importa de forma perezosa: sin `ORIGINAL_STORAGE=r2`
  no se carga.
- Arrancar con `ORIGINAL_STORAGE=r2` y variables a medias **falla el arranque**. Es deliberado: mejor
  no nacer que perder el archivo del alumno en el primer upload.

## Fuera de alcance

- **El endpoint de contenido** y la decisión sobre imágenes (adjunto vs OCR/visión).
- **Rehacer los análisis** de los documentos migrados (cuesta modelo; decisión de operación).
- **URLs firmadas** para servir el original directamente desde R2 sin pasar por el backend: es la
  forma eficiente de hacerlo, y también una decisión de seguridad (expiración, ámbito) que conviene
  tomar cuando el endpoint exista.
