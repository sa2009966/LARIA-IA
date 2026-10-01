"""Selecciona contexto acotado al foco conceptual (ahorro de tokens + pedagogía).

Con un libro entero, elegir bien es lo que convierte el documento en material
tutorizable (ADR-029). Antes se tomaban los párrafos que contenían el concepto
LITERAL o, si no había coincidencia, los tres primeros: con un libro, una duda
del capítulo 7 recibía como contexto la portada y el índice. Y como muchos PDF no
separan párrafos con línea en blanco, el "párrafo" solía ser el libro entero.

Ahora:
- el texto se trocea en fragmentos de tamaño manejable, haya o no párrafos;
- cada fragmento se puntúa por las palabras de la pregunta y del foco, pesadas
  por lo raras que son en el documento (una palabra que aparece en todas las
  páginas no distingue nada);
- se toman los mejores dentro del presupuesto, en el orden del documento;
- para un quiz sin foco, se reparten a lo largo de todo el documento.

Determinista y sin llamadas al modelo.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, OrderedDict

from src.domain.aggregates.document_aggregate import DocumentAggregate

#: Tamaño objetivo de un fragmento. Un párrafo más largo que el máximo se parte
#: por líneas y frases.
CHUNK_TARGET = 900
CHUNK_MAX = 1500

_STOP = frozenset(
    """a al algo ante antes como con contra cual cuando de del desde donde dos el ella
    ellos en entre era es esa ese eso esta este esto fue ha hay la las le lo los mas me
    mi muy no nos o otra otro para pero por porque que quien se sea ser si sin sobre son
    su sus tambien te tiene tu un una uno unos y ya yo explicame explica que como cual
    puedes podrias quiero saber entender dime ayuda""".split()
)


def _fold(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _terms(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9ñ]{3,}", _fold(text)) if t not in _STOP]


def _chunks(content: str) -> list[str]:
    """Fragmentos de ~CHUNK_TARGET caracteres, respetando párrafos cuando existen."""
    piezas = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    if not piezas and content.strip():
        piezas = [content.strip()]
    salida: list[str] = []
    for pieza in piezas:
        if len(pieza) <= CHUNK_MAX:
            salida.append(pieza)
            continue
        actual = ""
        for parte in re.split(r"(?<=[.!?])\s+|\n", pieza):
            parte = parte.strip()
            if not parte:
                continue
            if actual and len(actual) + len(parte) + 1 > CHUNK_TARGET:
                salida.append(actual)
                actual = ""
            actual = f"{actual} {parte}".strip()
            while len(actual) > CHUNK_MAX:  # una "frase" enorme sin puntos
                salida.append(actual[:CHUNK_TARGET])
                actual = actual[CHUNK_TARGET:]
        if actual:
            salida.append(actual)
    return salida


class _Indice:
    """Fragmentos y frecuencias de un documento (se reutiliza entre peticiones)."""

    def __init__(self, content: str) -> None:
        self.chunks = _chunks(content)
        self.tf = [Counter(_terms(c)) for c in self.chunks]
        df: Counter = Counter()
        for tf in self.tf:
            df.update(tf.keys())
        n = max(1, len(self.chunks))
        self.idf = {t: math.log(1 + n / f) for t, f in df.items()}


_CACHE: "OrderedDict[tuple, _Indice]" = OrderedDict()
_CACHE_MAX = 32


def _indice(document: DocumentAggregate) -> _Indice:
    content = document.content or ""
    clave = (str(getattr(document, "id", "")), len(content), hash(content[:2000]))
    idx = _CACHE.get(clave)
    if idx is None:
        idx = _Indice(content)
        _CACHE[clave] = idx
        if len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    else:
        _CACHE.move_to_end(clave)
    return idx


class ContextSelector:
    """Recorta el documento a summary/conceptos + los fragmentos que importan."""

    def select(
        self,
        document: DocumentAggregate,
        focus_concepts: tuple[str, ...] = (),
        max_chars: int = 2500,
        *,
        query: str = "",
        spread: bool = False,
    ) -> str:
        parts: list[str] = []
        if document.has_analysis() and document.analysis_result is not None:
            ar = document.analysis_result
            if ar.summary:
                parts.append(f"Resumen: {ar.summary}")
            if ar.key_concepts:
                parts.append("Conceptos clave: " + ", ".join(ar.key_concepts[:12]))
        focus = tuple(c.strip().lower() for c in focus_concepts if c and c.strip())
        if focus:
            parts.append("Foco de esta sesión: " + ", ".join(focus))

        cabecera = "\n\n".join(parts)
        presupuesto = max(0, max_chars - len(cabecera) - 2)
        cuerpo = self._body(document, focus, query, presupuesto, spread)
        assembled = "\n\n".join(p for p in (cabecera, cuerpo) if p)
        if len(assembled) > max_chars:
            return assembled[: max_chars - 20].rstrip() + "\n…[contexto acotado]"
        return assembled

    def _body(
        self, document: DocumentAggregate, focus: tuple[str, ...], query: str, presupuesto: int, spread: bool
    ) -> str:
        idx = _indice(document)
        if not idx.chunks or presupuesto <= 0:
            return ""
        # El foco pesa el doble que las palabras sueltas de la pregunta: es lo
        # que el motor decidió que se trabaja en este turno.
        pesos: Counter = Counter()
        for t in _terms(query):
            pesos[t] += 1.0
        for c in focus:
            for t in _terms(c):
                pesos[t] += 2.0
        puntos = [
            (sum(w * idx.idf.get(t, 0.0) * (1 + math.log(tf[t])) for t, w in pesos.items() if tf.get(t)), i)
            for i, tf in enumerate(idx.tf)
        ]
        elegidos = [i for score, i in sorted(puntos, key=lambda x: (-x[0], x[1])) if score > 0]
        if not elegidos:
            if spread:
                # Quiz sin foco: muestras repartidas por todo el documento, no
                # solo las primeras páginas.
                paso = max(1, len(idx.chunks) // 12)
                elegidos = list(range(0, len(idx.chunks), paso))
            else:
                elegidos = list(range(min(3, len(idx.chunks))))
        tomados: list[int] = []
        usados = 0
        for i in elegidos:
            largo = len(idx.chunks[i]) + 2
            if usados + largo > presupuesto:
                if not tomados:  # al menos un fragmento, recortado
                    tomados.append(i)
                continue
            tomados.append(i)
            usados += largo
        return "\n\n".join(idx.chunks[i] for i in sorted(tomados))
