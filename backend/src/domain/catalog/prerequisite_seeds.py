"""Semillas curriculares del grafo de prerrequisitos (ADR-005).

Son **datos**, no lógica: el currículum del dominio piloto que se siembra en el
agregado `ConceptGraph` como aristas `CURATED`. Una vez sembrado, el grafo se
edita por curación, no editando este archivo.

## Qué cubre y por qué así

La columna vertebral es el **álgebra escolar**, que es la materia de la demo, y
de ella cuelgan las ramas de cálculo y física que ya existían. Tres criterios
gobiernan qué entra:

1. **Una arista es una afirmación pedagógica:** "sin X no se puede con Y". Si no
   se puede defender en voz alta ante un docente, no entra. No se siembra por
   completitud temática.
2. **Una sola raíz: `número entero`.** El grafo es un DAG con punto de entrada
   único, así que `root_causes()` siempre converge a una base concreta en vez de
   devolver varias raíces inconexas que compiten por el foco.
3. **Lo procedimental depende de la aritmética; lo conceptual, no.** `resolver
   ecuación` necesita `jerarquía de operaciones` porque ahí es donde el alumno
   falla de verdad; `variable` no necesita saber dividir para entenderse.

La razón de fondo para enriquecerlo: con 19 conceptos el `PrerequisiteGate` casi
nunca escalaba por encima de `INTEGRATE`, porque la evidencia del alumno rara vez
caía sobre un prerrequisito declarado. Un grafo somero hace invisible medio
motor.
"""
from __future__ import annotations

from src.domain.aggregates.concept_graph import ConceptGraph

#: concepto → prerrequisitos directos.
SEED_EDGES: dict[str, tuple[str, ...]] = {
    # --- Aritmética: la base sobre la que se apoya todo lo demás --------------
    # `operaciones` es además la etiqueta que `ConceptTagger` asigna a los ítems
    # de suma/resta/multiplicación. Antes no existía en el grafo, así que esa
    # evidencia no podía gatear nada: se medía y no servía para decidir.
    "operaciones": ("número entero",),
    "jerarquía de operaciones": ("operaciones",),
    "fracción": ("operaciones",),
    "potencia": ("operaciones",),
    "leyes de exponentes": ("potencia",),
    "raíz": ("potencia",),
    "razón": ("fracción",),
    "proporción": ("razón",),
    "porcentaje": ("proporción", "fracción"),
    "regla de tres": ("proporción",),

    # --- Lenguaje algebraico -------------------------------------------------
    "variable": ("número entero",),
    "constante": ("número entero",),
    "término algebraico": ("variable", "constante"),
    "coeficiente": ("término algebraico",),
    "expresión algebraica": ("variable", "término algebraico"),
    "términos semejantes": ("expresión algebraica", "coeficiente"),
    "monomio": ("término algebraico", "coeficiente"),
    "polinomio": ("monomio", "términos semejantes"),
    "propiedad distributiva": ("expresión algebraica", "operaciones"),
    "suma de polinomios": ("polinomio", "términos semejantes"),
    "multiplicación de polinomios": (
        "polinomio",
        "propiedad distributiva",
        "leyes de exponentes",
    ),
    "productos notables": ("multiplicación de polinomios",),
    "factorización": ("propiedad distributiva", "productos notables"),
    "fracción algebraica": ("factorización", "fracción"),

    # --- Ecuaciones ----------------------------------------------------------
    # `igualdad` y `propiedades de la igualdad` estaban implícitas y son
    # justamente lo que un alumno rompe al "pasar restando": merecen nodo propio
    # para poder señalarlas como hueco.
    "igualdad": ("operaciones",),
    "propiedades de la igualdad": ("igualdad",),
    "ecuación": ("variable", "expresión algebraica", "igualdad"),
    "resolver ecuación": (
        "ecuación",
        "propiedades de la igualdad",
        "jerarquía de operaciones",
    ),
    "verificación de soluciones": ("resolver ecuación",),
    "ecuaciones lineales": ("ecuación", "resolver ecuación"),
    "desigualdad": ("ecuación", "propiedades de la igualdad"),
    "ecuación cuadrática": ("ecuación", "factorización"),
    "fórmula general": ("ecuación cuadrática", "raíz"),
    "sistemas": ("ecuaciones lineales",),
    "sistemas de ecuaciones": ("ecuaciones lineales",),
    "método de sustitución": ("sistemas de ecuaciones", "resolver ecuación"),
    "método de igualación": ("sistemas de ecuaciones", "resolver ecuación"),
    "método de eliminación": ("sistemas de ecuaciones", "términos semejantes"),
    "matrices": ("sistemas", "ecuaciones lineales"),

    # --- Funciones y gráficas ------------------------------------------------
    "plano cartesiano": ("número entero",),
    "par ordenado": ("plano cartesiano",),
    "funciones": ("variable", "expresión algebraica", "par ordenado"),
    "gráfica de funciones": ("funciones", "plano cartesiano"),
    "función lineal": ("funciones", "ecuaciones lineales"),
    "pendiente": ("función lineal", "razón"),
    "función cuadrática": ("funciones", "ecuación cuadrática"),

    # --- Cálculo -------------------------------------------------------------
    "límite": ("funciones", "gráfica de funciones"),
    "derivadas": ("funciones", "límite"),
    "regla de la cadena": ("derivadas",),
    "integrales": ("derivadas", "funciones"),

    # --- Física --------------------------------------------------------------
    "vectores": ("plano cartesiano", "operaciones"),
    "mru": ("función lineal", "vectores"),
    "mruv": ("mru", "función cuadrática"),
    "cinemática": ("mru", "mruv"),
    "dinámica": ("cinemática", "vectores"),
    "leyes de newton": ("dinámica",),
}

#: Alias → clave canónica del grafo.
#:
#: Las claves se pliegan (minúsculas, sin tildes) al construir el grafo, así que
#: se escriben una sola vez y con su ortografía natural: `ConceptGraph` acepta
#: tanto "límites" como "limites". Aquí entra el vocabulario con el que el
#: estudiante y los documentos nombran las cosas, que casi nunca es el nombre
#: canónico.
SEED_ALIASES: dict[str, str] = {
    # Aritmética
    "números enteros": "número entero",
    "enteros": "número entero",
    "entero": "número entero",
    "números": "número entero",
    "suma": "operaciones",
    "resta": "operaciones",
    "multiplicación": "operaciones",
    "división": "operaciones",
    "operaciones básicas": "operaciones",
    "operaciones aritméticas": "operaciones",
    "aritmética": "operaciones",
    "orden de operaciones": "jerarquía de operaciones",
    "fracciones": "fracción",
    "potencias": "potencia",
    "exponentes": "leyes de exponentes",
    "exponente": "leyes de exponentes",
    "raíces": "raíz",
    "radicales": "raíz",
    "raíz cuadrada": "raíz",
    "proporciones": "proporción",
    "porcentajes": "porcentaje",
    # Lenguaje algebraico
    "álgebra": "variable",
    "variables": "variable",
    "constantes": "constante",
    "término": "término algebraico",
    "términos algebraicos": "término algebraico",
    "coeficientes": "coeficiente",
    "expresión": "expresión algebraica",
    "expresiones algebraicas": "expresión algebraica",
    "términos": "términos semejantes",
    "reducción de términos": "términos semejantes",
    "monomios": "monomio",
    "polinomios": "polinomio",
    "distributiva": "propiedad distributiva",
    "factorizar": "factorización",
    "fracciones algebraicas": "fracción algebraica",
    # Ecuaciones
    "despejar": "resolver ecuación",
    "despeje": "resolver ecuación",
    "resolución de ecuaciones": "resolver ecuación",
    "resolver ecuaciones": "resolver ecuación",
    "solución de ecuaciones": "resolver ecuación",
    "comprobación": "verificación de soluciones",
    "verificación": "verificación de soluciones",
    "verificación de resultados": "verificación de soluciones",
    "ecuaciones": "ecuaciones lineales",
    "ecuaciones de primer grado": "ecuaciones lineales",
    "cuadrática": "ecuación cuadrática",
    "ecuaciones cuadráticas": "ecuación cuadrática",
    "ecuaciones de segundo grado": "ecuación cuadrática",
    "fórmula cuadrática": "fórmula general",
    "desigualdades": "desigualdad",
    "inecuación": "desigualdad",
    "inecuaciones": "desigualdad",
    "sistema": "sistemas",
    "sistemas lineales": "sistemas de ecuaciones",
    "sustitución": "método de sustitución",
    "igualación": "método de igualación",
    "eliminación": "método de eliminación",
    "reducción": "método de eliminación",
    "matriz": "matrices",
    # Funciones y gráficas
    "función": "funciones",
    "plano coordenado": "plano cartesiano",
    "coordenadas": "plano cartesiano",
    "pares ordenados": "par ordenado",
    "gráfica": "gráfica de funciones",
    "gráficas": "gráfica de funciones",
    "graficar": "gráfica de funciones",
    "recta": "función lineal",
    "funciones lineales": "función lineal",
    "parábola": "función cuadrática",
    "funciones cuadráticas": "función cuadrática",
    # Cálculo
    "límites": "límite",
    "derivada": "derivadas",
    "integral": "integrales",
    # Física
    "vector": "vectores",
    "movimiento rectilíneo uniforme": "mru",
    "movimiento uniformemente acelerado": "mruv",
    "aceleración": "mruv",
    "newton": "leyes de newton",
}


def build_seeded_graph(graph_id: str = "default") -> ConceptGraph:
    """Grafo con el currículum piloto ya curado."""
    graph = ConceptGraph(graph_id=graph_id, aliases=dict(SEED_ALIASES))
    for concept, prerequisites in SEED_EDGES.items():
        for prerequisite in prerequisites:
            graph.curate(concept, prerequisite)
    return graph
