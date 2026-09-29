"""Textos legales: términos, privacidad y cookies (ADR-019).

Los escribe el backend, no el cliente, porque describen lo que el backend hace
con los datos: qué guarda, dónde, cuánto tiempo y cómo se borra. Si los
escribiera el frontend podrían contradecir al sistema sin que nadie lo notara.
El cliente solo los pinta.

Los datos que el código no puede saber —responsable, contacto, país, edad mínima—
van marcados `[[COMPLETAR: …]]`. El endpoint los enumera en `pendiente` y pone
`completo: false` hasta que no quede ninguno: publicar un texto legal con huecos
es peor que no publicarlo.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/legal", tags=["Legal"])

_DIR = Path(__file__).resolve().parents[2] / "legal"
_SLUGS = ("terminos", "privacidad", "cookies")
_PENDIENTE = re.compile(r"\[\[COMPLETAR:\s*([^\]]+?)\s*\]\]")
_VERSION = re.compile(r"\*\*Versi[oó]n\s+(\d{4}-\d{2}-\d{2})\.\*\*")


class LegalSummary(BaseModel):
    slug: str
    title: str
    version: str


class LegalDocument(LegalSummary):
    #: El texto en Markdown, para pintarlo tal cual.
    markdown: str
    #: Huecos sin rellenar. Mientras haya alguno, el texto no está listo.
    pendiente: list[str]
    completo: bool


def _cargar(slug: str) -> LegalDocument:
    texto = (_DIR / f"{slug}.md").read_text(encoding="utf-8")
    titulo = next((l[2:].strip() for l in texto.splitlines() if l.startswith("# ")), slug)
    version = _VERSION.search(texto)
    pendiente = list(dict.fromkeys(_PENDIENTE.findall(texto)))
    return LegalDocument(
        slug=slug,
        title=titulo,
        version=version.group(1) if version else "",
        markdown=texto,
        pendiente=pendiente,
        completo=not pendiente,
    )


@router.get("", response_model=list[LegalSummary], summary="Textos legales disponibles")
async def list_legal():
    return [LegalSummary(**_cargar(s).model_dump(include={"slug", "title", "version"})) for s in _SLUGS]


@router.get(
    "/{slug}",
    response_model=LegalDocument,
    summary="Un texto legal",
    description=(
        "`terminos`, `privacidad` o `cookies`. Público: no requiere sesión, porque "
        "hay que poder leerlo **antes** de registrarse.\\n\\n"
        "Si `completo` es `false`, el texto tiene huecos sin rellenar (listados en "
        "`pendiente`) y no debería mostrarse como definitivo."
    ),
)
async def get_legal(slug: str):
    if slug not in _SLUGS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Texto legal no encontrado")
    return _cargar(slug)
