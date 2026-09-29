#!/usr/bin/env python3
"""Limpia el `preferred_explanation_style` congelado de los perfiles antiguos.

Deuda #1 del plan de experiencia pedagógica. `PedagogicalMemory` tenía por
defecto `preferred_explanation_style="simple"`, así que **todos** los perfiles
escritos antes del ADR-006 llevan ese valor persistido aunque nadie observara
esa preferencia. `CognitiveStyleSelector` lo respeta antes que sus heurísticas,
de modo que esos estudiantes quedan congelados en estilo "simple" de por vida.

Cambiar el default del dataclass no migra documentos ya escritos: hay que
vaciar el campo, y eso es una acción deliberada sobre datos de producción.

    # ver a cuántos afecta, sin tocar nada (por defecto)
    python scripts/migrate_preferred_style.py

    # aplicarlo
    python scripts/migrate_preferred_style.py --apply

**Qué se pierde:** un estudiante cuyo estilo efectivo *sí* era "simple" también
queda sin preferencia. Es aceptable y deliberado: el estilo se vuelve a
aprender con la evidencia del ADR-006 (solo se escribe cuando funcionó), y es
preferible a un valor que nadie midió.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ejecutable directamente desde `backend/` sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CAMPO = "pedagogical_memory.preferred_explanation_style"
CONGELADO = "simple"


async def _ejecutar(aplicar: bool) -> int:
    from src.infrastructure.config import settings
    from src.infrastructure.mongodb.database import close_database, get_database

    if settings.DB_PROVIDER != "mongodb":
        print(
            f"DB_PROVIDER={settings.DB_PROVIDER!r}: no hay nada que migrar "
            "(los perfiles en memoria nacen sin preferencia).",
            file=sys.stderr,
        )
        return 1

    db = await get_database()
    try:
        total = await db.student_profiles.count_documents({})
        afectados = await db.student_profiles.count_documents({CAMPO: CONGELADO})
        print(f"Base: {settings.MONGODB_DB_NAME}")
        print(f"  perfiles totales            : {total}")
        print(f"  con estilo congelado 'simple': {afectados}")

        if afectados == 0:
            print("\nNada que hacer.")
            return 0

        if not aplicar:
            print(
                "\nSimulación. Vuelve a ejecutarlo con --apply para vaciar el campo "
                f"en esos {afectados} perfiles."
            )
            return 0

        resultado = await db.student_profiles.update_many(
            {CAMPO: CONGELADO}, {"$set": {CAMPO: ""}}
        )
        print(f"\nActualizados: {resultado.modified_count}")
        restantes = await db.student_profiles.count_documents({CAMPO: CONGELADO})
        if restantes:
            print(f"  ⚠ quedan {restantes} sin migrar; revisa permisos de escritura")
            return 1
        print("  El estilo vuelve a decidirse por evidencia.")
        return 0
    finally:
        await close_database()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="escribe los cambios (sin esto, solo simula)"
    )
    args = parser.parse_args()
    return asyncio.run(_ejecutar(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
