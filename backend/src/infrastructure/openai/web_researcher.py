"""Temario investigado en internet con la búsqueda web de OpenAI (ADR-039).

Dos pasos:
1. gpt-4o con la herramienta `web_search` investiga y cita, en prosa.
2. Un modelo barato lo convierte en temario JSON, citando fuentes **por número**.

Las fuentes salen solo de lo que devolvió la búsqueda (citas `url_citation` y fuentes
consultadas), nunca del texto del modelo: al pedirle JSON directamente inventaba URLs.
Un número que no está en la lista se descarta.
"""
from __future__ import annotations

import json
import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from src.domain.ports.lesson_generator import Source, SyllabusItem
from src.domain.services.tutor_policy import TutorPolicy

logger = logging.getLogger("laria.research")

_URL = "https://api.openai.com/v1/responses"
#: La búsqueda tarda ~9-16 s; se corta antes de que el cliente se canse.
_TIMEOUT_S = 45.0
_MAX_FUENTES = 12


class ResearchFailed(Exception):
    """No hubo temario investigado (sin fuentes, respuesta rara o proveedor caído)."""


def clean_url(url: str) -> str:
    """Sin `utm_*` (la búsqueda añade `utm_source=openai`) ni fragmento."""
    partes = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(partes.query) if not k.startswith("utm_")])
    return urlunsplit((partes.scheme, partes.netloc, partes.path, query, ""))


def _texto(data: dict) -> tuple[str, list[dict]]:
    """Texto de la respuesta y sus anotaciones."""
    texto, anotaciones = "", []
    for item in data.get("output") or []:
        if item.get("type") != "message":
            continue
        for parte in item.get("content") or []:
            if parte.get("type") == "output_text":
                texto += parte.get("text", "")
                anotaciones += parte.get("annotations") or []
    return texto, anotaciones


#: Sitios de contenido subido por usuarios o foros: no son una fuente que mostrarle a
#: un estudiante como respaldo de una clase (en las pruebas aparecían Reddit y Scribd).
_NO_FUENTES = (
    "reddit.com", "scribd.com", "studocu.com", "quora.com", "brainly.", "facebook.com",
    "instagram.com", "tiktok.com", "twitter.com", "x.com", "pinterest.",
    "coursehero.com", "slideshare.net", "monografias.com", "rincondelvago.com",
)


def _aceptable(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    host = urlsplit(url).netloc.lower()
    host = host.removeprefix("www.")
    # "brainly." vale para cualquier dominio de país; el resto, el dominio exacto o un
    # subdominio ("x.com" no puede tumbar "dropbox.com").
    return not any(
        host.startswith(d) or f".{d}" in f".{host}" if d.endswith(".")
        else host == d or host.endswith("." + d)
        for d in _NO_FUENTES
    )


def _una_linea(texto: str) -> str:
    """Las ideas clave llegaban con saltos de línea en medio de una fórmula."""
    return " ".join(str(texto).split())


def verified_sources(data: dict) -> list[tuple[str, str]]:
    """(título, url) de lo que la búsqueda citó o consultó, sin repetir, citadas primero."""
    fuentes: dict[str, str] = {}
    _, anotaciones = _texto(data)
    for a in anotaciones:
        if a.get("type") == "url_citation" and _aceptable(a.get("url", "")):
            fuentes.setdefault(clean_url(a["url"]), _una_linea(a.get("title") or ""))
    for item in data.get("output") or []:
        if item.get("type") == "web_search_call":
            for s in (item.get("action") or {}).get("sources") or []:
                if _aceptable(s.get("url", "")):
                    fuentes.setdefault(clean_url(s["url"]), _una_linea(s.get("title") or ""))
    return [(titulo or urlsplit(url).netloc, url) for url, titulo in list(fuentes.items())[:_MAX_FUENTES]]


def items_from(data: dict, fuentes: list[tuple[str, str]]) -> list[SyllabusItem]:
    """El JSON del paso 2 → subtemas. Solo se aceptan números de fuente de la lista."""
    items = []
    for m in data.get("modules") or []:
        if not isinstance(m, dict) or not str(m.get("title", "")).strip():
            continue
        numeros = [n for n in (m.get("sources") or []) if isinstance(n, int) and 1 <= n <= len(fuentes)]
        items.append(
            SyllabusItem(
                title=_una_linea(m["title"]),
                prerequisites=tuple(str(p).strip() for p in (m.get("prerequisites") or []) if str(p).strip()),
                key_points=tuple(_una_linea(k)[:300] for k in (m.get("key_points") or [])[:5] if _una_linea(k)),
                sources=tuple(Source(*fuentes[n - 1]) for n in dict.fromkeys(numeros)),
            )
        )
    return items


class OpenAIWebResearcher:
    def __init__(
        self,
        api_key: str,
        research_model: str = "gpt-4o",
        structure_model: str = "gpt-4o-mini",
        http_client: httpx.AsyncClient | None = None,
        policy: TutorPolicy | None = None,
    ) -> None:
        self._api_key = api_key
        self._research_model = research_model
        self._structure_model = structure_model
        self._client = http_client
        self._policy = policy or TutorPolicy()

    async def _post(self, payload: dict) -> dict:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=_TIMEOUT_S)
        try:
            r = await self._client.post(
                _URL, headers={"Authorization": f"Bearer {self._api_key}"}, json=payload
            )
            if r.status_code >= 400:
                # El cuerpo del error dice qué parámetro rechazó (no lleva la clave).
                raise ResearchFailed(f"{r.status_code}: {r.text[:200]}")
            return r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ResearchFailed(type(exc).__name__) from exc

    async def research(
        self, topic_label: str, level: str, avoid: tuple[str, ...] = ()
    ) -> list[SyllabusItem]:
        p1 = self._policy.research_curriculum(topic_label, level, avoid)
        investigacion = await self._post({
            "model": self._research_model,
            "instructions": p1.system,
            "input": p1.user,
            "tools": [{"type": "web_search"}],
            # Sin obligarla, a veces respondía de memoria y sin una sola cita.
            "tool_choice": "required",
            "include": ["web_search_call.action.sources"],
        })
        texto, _ = _texto(investigacion)
        fuentes = verified_sources(investigacion)
        if not texto.strip() or not fuentes:
            raise ResearchFailed("sin fuentes")

        p2 = self._policy.structure_research(topic_label, level, texto, fuentes, avoid)
        estructura = await self._post({
            "model": self._structure_model,
            "instructions": p2.system,
            "input": p2.user,
            "text": {"format": {"type": "json_object"}},
        })
        crudo, _ = _texto(estructura)
        try:
            items = items_from(json.loads(crudo), fuentes)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ResearchFailed("json") from exc
        if not items:
            raise ResearchFailed("temario vacío")
        logger.info(
            "temario_investigado nivel=%s modulos=%d fuentes=%d", level, len(items), len(fuentes)
        )
        return items
