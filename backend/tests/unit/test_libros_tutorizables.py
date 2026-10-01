"""Libros como material tutorizable (ADR-029): análisis por secciones y contexto que encuentra el capítulo.

Antes: un libro grande fallaba al analizarse (más de 128k tokens) y, aun
analizado, el tutor recibía como contexto el principio del libro, porque solo
buscaba coincidencias literales y muchos PDF no separan párrafos.
"""
from uuid import uuid4

import pytest

from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.ports.ia_analyst import IAAnalysisError
from src.domain.services.context_selector import ContextSelector, _chunks
from src.infrastructure.ia import base_chat_analyst as mod
from src.infrastructure.ia.base_chat_analyst import BaseChatAnalyst, split_sections

CAPITULOS = {
    1: "La célula es la unidad básica de la vida; tiene membrana, citoplasma y núcleo.",
    7: "La fotosíntesis ocurre en los cloroplastos y convierte la luz en energía química.",
    12: "Las leyes de Mendel explican la herencia: segregación y transmisión independiente.",
}


def _libro(lineas_por_capitulo=60):
    """Un libro como lo entrega un PDF: líneas sueltas, sin líneas en blanco."""
    lineas = []
    for cap in range(1, 15):
        base = CAPITULOS.get(max(k for k in CAPITULOS if k <= cap))
        lineas += [f"Capítulo {cap}, línea {i}. {base}" for i in range(lineas_por_capitulo)]
    return "\n".join(lineas)


def _doc(texto):
    return DocumentAggregate.upload(owner_id=uuid4(), filename="libro.pdf", content=texto, subject="Biología")


# --- Contexto ----------------------------------------------------------------------------


def test_un_pdf_sin_lineas_en_blanco_se_trocea():
    trozos = _chunks(_libro())

    assert len(trozos) > 20 and max(len(t) for t in trozos) <= 1500


def test_la_pregunta_trae_el_capitulo_que_la_responde_y_no_el_principio():
    ctx = ContextSelector().select(_doc(_libro()), (), max_chars=3000, query="¿Qué dicen las leyes de Mendel?")

    assert "Mendel" in ctx
    assert "Capítulo 1," not in ctx, "antes salían las primeras páginas"


def test_el_foco_del_motor_tambien_busca_en_todo_el_libro():
    ctx = ContextSelector().select(_doc(_libro()), ("fotosíntesis",), max_chars=3000)

    assert "cloroplastos" in ctx


def test_un_quiz_sin_foco_reparte_el_contexto_por_todo_el_libro():
    ctx = ContextSelector().select(_doc(_libro()), (), max_chars=8000, spread=True)

    capitulos = {c for c in range(1, 15) if f"Capítulo {c}," in ctx}
    assert len(capitulos) >= 8, f"solo cubre {sorted(capitulos)}"


def test_las_palabras_que_estan_en_todas_partes_no_deciden():
    """"Capítulo" aparece en cada línea: no debe pesar como "Mendel"."""
    ctx = ContextSelector().select(_doc(_libro()), (), max_chars=1500, query="capítulo de Mendel")

    assert "Mendel" in ctx


# --- Análisis por secciones -------------------------------------------------------------


def test_las_secciones_cortan_en_saltos_de_linea_y_no_pasan_de_16():
    secciones = split_sections(("x" * 99 + "\n") * 60_000)  # 6M caracteres

    assert len(secciones) <= 16
    assert all(s.endswith("x") for s in secciones), "corta en salto de línea, no a mitad"


class AnalistaFalso(BaseChatAnalyst):
    def __init__(self, falla_en=()):
        from src.domain.services.tutor_policy import TutorPolicy

        self._policy = TutorPolicy()
        self.model = "gpt-4o-mini"
        self.llamadas = []
        self._falla_en = set(falla_en)

    async def _chat_json(self, system, user, *, model):
        self.llamadas.append(user[:30])
        if user.startswith("Sección"):
            n = int(user.split()[1])
            if n in self._falla_en:
                raise IAAnalysisError("roto")
            return {"summary": f"Resumen sección {n}.", "key_concepts": ["célula", f"tema {n}"]}
        return {"summary": "Libro de biología.", "key_concepts": ["célula"], "suggested_questions": ["¿?"]}


@pytest.mark.asyncio
async def test_un_documento_grande_se_analiza_por_secciones_y_se_sintetiza(monkeypatch):
    monkeypatch.setattr(mod, "ANALYSIS_DIRECT_CHARS", 1000)
    monkeypatch.setattr(mod, "SECTION_MIN_CHARS", 30_000)
    a = AnalistaFalso()

    r = await a.analyze_with_model(_doc(_libro()), "gpt-4o-mini")

    secciones = [x for x in a.llamadas if x.startswith("Sección")]
    assert len(secciones) >= 2 and len(a.llamadas) == len(secciones) + 1, "N secciones + 1 síntesis"
    assert r.summary == "Libro de biología." and r.key_concepts == ["célula"]


@pytest.mark.asyncio
async def test_una_seccion_que_falla_no_tumba_el_analisis(monkeypatch):
    monkeypatch.setattr(mod, "ANALYSIS_DIRECT_CHARS", 1000)
    monkeypatch.setattr(mod, "SECTION_MIN_CHARS", 30_000)

    r = await AnalistaFalso(falla_en={1}).analyze_with_model(_doc(_libro()), "gpt-4o-mini")

    assert r.summary == "Libro de biología."


@pytest.mark.asyncio
async def test_un_documento_normal_se_sigue_analizando_de_una_vez():
    a = AnalistaFalso()

    async def directo(system, user, *, model):
        a.llamadas.append("directo")
        return {"summary": "corto", "key_concepts": [], "suggested_questions": []}

    a._chat_json = directo
    await a.analyze_with_model(_doc("Un apunte corto sobre la célula."), "gpt-4o-mini")

    assert a.llamadas == ["directo"]


def test_los_conceptos_de_un_libro_cubren_todas_las_secciones():
    """Contra el modelo real, la lista quedó sesgada al capítulo 1 y el motor
    trataba un libro de biología como si solo hablara de la célula."""
    from src.infrastructure.ia.base_chat_analyst import cover_sections, round_robin_concepts

    por_seccion = [["célula", "membrana", "núcleo"], ["fotosíntesis", "cloroplasto"], ["Mendel", "herencia"]]

    assert round_robin_concepts(por_seccion)[:3] == ["célula", "fotosíntesis", "Mendel"]
    sesgado = ["célula", "membrana", "núcleo"]  # lo que eligió el modelo
    assert cover_sections(sesgado, por_seccion) == ["célula", "membrana", "núcleo", "fotosíntesis", "Mendel"]
