#!/usr/bin/env python3
"""Recupera los documentos subidos antes del ADR-012.

Esos documentos guardan el **binario** en el blob de contenido y `content=""`,
así que su análisis se hizo sobre el archivo decodificado como UTF-8: mojibake.
Pero el archivo original sigue ahí, intacto, así que la recuperación es posible:

  1. lee el blob (el binario original),
  2. le extrae el texto con el mismo parser del upload,
  3. guarda ese texto como blob de contenido,
  4. y apunta `original_blob_id` al blob que ya existía, con su tipo real.

Lo que NO arregla: el `analysis_result` ya calculado sobre basura. Queda como
estaba; para rehacerlo basta `POST /documents/{id}/analyze?force_refresh=true`
(cuesta una llamada al modelo por documento, así que se decide aparte).

    python scripts/migrate_document_blobs.py              # simula
    python scripts/migrate_document_blobs.py --apply      # escribe
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def _ejecutar(aplicar: bool) -> int:
    from src.application.file_parser import content_type_for, parse_file
    from src.infrastructure.config import settings
    from src.infrastructure.mongodb.database import close_database, get_database
    from src.infrastructure.mongodb.gridfs_document_blob_store import (
        GridFSDocumentBlobStore,
    )

    if settings.DB_PROVIDER != "mongodb":
        print(
            f"DB_PROVIDER={settings.DB_PROVIDER!r}: no hay nada persistido que migrar.",
            file=sys.stderr,
        )
        return 1

    db = await get_database()
    store = GridFSDocumentBlobStore()
    try:
        total = await db.documents.count_documents({})
        candidatos = db.documents.find(
            {
                "content_blob_id": {"$ne": None},
                # Ya migrados (o subidos después del arreglo) tienen original.
                "$or": [{"original_blob_id": None}, {"original_blob_id": {"$exists": False}}],
            },
            projection={"_id": 1, "filename": 1, "content_blob_id": 1},
        )

        migrados = 0
        ya_texto = 0
        fallidos: list[tuple[str, str]] = []
        revisados = 0

        async for doc in candidatos:
            revisados += 1
            doc_id = doc["_id"]
            filename = doc.get("filename") or "material.txt"
            blob_id = str(doc["content_blob_id"])
            try:
                raw = await store.get(blob_id)
            except KeyError:
                fallidos.append((doc_id, "el blob no existe"))
                continue

            try:
                texto = parse_file(filename, raw)
            except Exception as exc:  # noqa: BLE001
                # Lo más probable: ya es texto plano guardado con nombre .pdf
                # (un documento migrado a mano), o un archivo corrupto.
                fallidos.append((doc_id, f"no se pudo extraer texto: {type(exc).__name__}"))
                continue

            if not texto.strip():
                fallidos.append((doc_id, "la extracción quedó vacía"))
                continue

            # Si el blob YA era el texto, `parse_file` lo devuelve igual: no hay
            # nada que arreglar, solo etiquetar el original.
            era_texto = raw.decode("utf-8", errors="ignore").strip() == texto.strip()
            if era_texto:
                ya_texto += 1

            if not aplicar:
                continue

            nuevo_blob = await store.put(
                texto.encode("utf-8"),
                filename=filename,
                content_type="text/plain; charset=utf-8",
            )
            await db.documents.update_one(
                {"_id": doc_id},
                {
                    "$set": {
                        "content_blob_id": nuevo_blob,
                        "original_blob_id": blob_id,
                        "original_content_type": content_type_for(filename),
                        "original_size": len(raw),
                    }
                },
            )
            migrados += 1

        print(f"Base {settings.MONGODB_DB_NAME}: {total} documento(s), {revisados} a revisar")
        print(f"  ya eran texto (solo se etiqueta el original): {ya_texto}")
        print(f"  con binario que ahora sí se convierte a texto: {revisados - ya_texto - len(fallidos)}")
        if fallidos:
            print(f"  sin migrar: {len(fallidos)}")
            for doc_id, motivo in fallidos[:10]:
                print(f"    · {doc_id}: {motivo}")
        if aplicar:
            print(f"\nActualizados: {migrados}")
            print(
                "  El análisis viejo sigue basado en el texto anterior: rehazlo con\n"
                "  POST /documents/{id}/analyze?force_refresh=true cuando quieras."
            )
        elif revisados:
            print("\nSimulación. Repite con --apply para escribir.")
        else:
            print("\nNada que migrar.")
        return 0
    finally:
        await close_database()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="escribe los cambios")
    args = parser.parse_args()
    return asyncio.run(_ejecutar(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
