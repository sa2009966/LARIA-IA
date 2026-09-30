"""Detector de intención del estudiante para el tutor.

Clasifica el mensaje de entrada en una intención de alto nivel que React
usará para seleccionar el componente de UI correcto (respuesta, quiz, hint,
celebración o aprendizaje). Determinista (regex/palabras clave) — no usa LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from src.domain.services.learning_signal_detector import LearningSignalDetector


class TutorIntent(str, Enum):
    LEARN = "learn"  # quiere aprender/explicar un tema
    QUIZ = "quiz"  # pide un cuestionario/examen/práctica
    HINT = "hint"  # pide ayuda/pista/está confundido
    CELEBRATE = "celebrate"  # respuesta afirmativa a un logro
    GENERAL = "general"  # conversación general sin intención pedagógica
    #: Pregunta sobre el propio tutor ("¿quién sos?", "¿qué podés hacer?"). No es
    #: una duda sobre el material: no pasa por el motor pedagógico ni deja
    #: evidencia, y con un libro vinculado no se responde con una clase.
    ABOUT = "about"
    #: Habla de CÓMO aprende: pide que se le pregunte o dice cómo prefiere que le
    #: expliquen (ADR-023). Tampoco es una duda del material.
    LEARNING_STYLE = "learning_style"
    NONE = "none"


@dataclass(frozen=True)
class Intention:
    intent: TutorIntent
    confidence: float  # 0..1
    topic_hint: str | None = None  # concepto detectado en la pregunta
    #: El estudiante pidió aprender un TEMA, no preguntó un concepto suelto. Es la
    #: señal para ofrecerle nivelación (ADR-017). Más estrecha que `LEARN`, que
    #: también salta con "qué es" o "define": ofrecer un diagnóstico a cada
    #: pregunta conceptual sería ruido.
    suggest_placement: bool = False
    #: El estudiante pidió un cuestionario o practicar. Es la señal para que el
    #: cliente abra un quiz interactivo —que se corrige en el servidor y deja
    #: evidencia— y para que el tutor NO lo escriba como texto en el chat.
    offer_quiz: bool = False
    #: Pidió que se le pregunte cómo le gusta aprender (ADR-023).
    ask_learning_style: bool = False
    #: Dijo cómo prefiere aprender: valor de `CognitiveStyle` (ADR-023).
    declared_style: str | None = None


_LEARN = re.compile(
    r"\b(?:qu[eé]\s+es|qu[eé]\s+son|qu[eé]\s+significa|expl[ií]ca(?:r|rme|me)?|"
    r"ens[eé][ñn]a(?:r|rme|me|s)?|d[eé]fin(?:e|ici[oó]n)?|concepto de|qu[ií]ero\s+aprender|"
    r"introdu[cç](?:e|ir)?|empecemos|por\s+d[oó]nde|ay[úu]dame\s+a\s+entender|"
    r"quiero\s+entender|vamos\s+a\s+ver)\b",
    re.IGNORECASE,
)
#: Pedir un cuestionario o practicar, y nada más. El patrón anterior saltaba con
#: una palabra suelta: "ponme un ejemplo", "la prueba de hipótesis" o "el test de
#: Turing" contaban como pedir un quiz, y "quiero practicar ecuaciones" no. Con
#: el quiz interactivo encima, "ponme un ejemplo" habría abierto un cuestionario
#: en vez de dar el ejemplo.
_QUIZ = re.compile(
    r"\b(?:"
    r"(?:hazme|hacerme|ponme|dame|genera(?:me)?|quiero|necesito|"
    r"puedes\s+(?:hacerme|darme|ponerme)|me\s+(?:haces|pones|das))\s+"
    r"(?:(?:un|una|unos|unas|alg[uú]n|alguna|algunos|algunas|otro|otra)\s+)?"
    r"(?:quiz(?:z|zes)?|cuestionarios?|ex[aá]menes|examen|test|prueba|evaluaci[oó]n|"
    r"ejercicios?|preguntas|problemas)"
    r"|(?:quiero|vamos\s+a|me\s+gustar[ií]a)\s+practicar|practiquemos"
    r"|eval[uú]ame|preg[uú]ntame|t[oó]mame\s+(?:un\s+|una\s+)?(?:examen|test|prueba)"
    r")\b(?P<resto>.*)$",
    re.IGNORECASE,
)
_PREPOSICION_TEMA = re.compile(
    r"^\s*(?:(?:de|sobre|acerca\s+de|en|con|del|de\s+la|de\s+los|de\s+las)\s+)?", re.IGNORECASE
)


def _cuestionario_pedido(texto: str) -> tuple[bool, str | None]:
    """¿Pidió un cuestionario? Y si nombró el tema, cuál, tal como lo escribió."""
    m = _QUIZ.search(texto)
    if not m:
        return False, None
    resto = re.split(r"[?.!¿¡\n]", m.group("resto"), maxsplit=1)[0]
    resto = _RELLENO.sub("", _PREPOSICION_TEMA.sub("", resto.strip(), count=1)).strip()
    resto = _CORTESIA.sub("", resto).strip(" ,;:")
    if not resto:
        return True, None
    return True, resto[:_MAX_TEMA].rsplit(" ", 1)[0] if len(resto) > _MAX_TEMA else resto
_CELEBRATE = re.compile(
    r"\b(entend[ií]|me\s+queda\s+claro|genial|excelente|s[ií]\s+s[eé]\b|"
    r"lo\s+logre|perfecto|bien|listo|continuemos|d[aá]le)\b",
    re.IGNORECASE,
)

#: Pedir aprender un tema, no preguntar un concepto. "¿Qué es una variable?" es
#: una duda; "quiero aprender álgebra" es un punto de partida. Solo lo segundo
#: justifica ofrecer una nivelación.
_WANTS_TO_LEARN = re.compile(
    r"\b(?:quiero\s+(?:aprender|estudiar|entender)|"
    # "ensé" con tilde: sin ella "enséñame" no se reconocía.
    r"(?:me\s+)?(?:puedes\s+)?ens[eé][ñn]a(?:s|r|rme|me)?|"
    r"empecemos\s+con|"
    r"por\s+d[oó]nde\s+empiezo\s+(?:con|en))\b\s*(?P<resto>.*)$",
    re.IGNORECASE,
)
#: Relleno entre el verbo y el tema: "quiero aprender SOBRE LA historia".
_RELLENO = re.compile(
    r"^(?:(?:sobre|acerca\s+de|de|a|el|la|los|las|lo|un|una|algo\s+de|"
    r"qu[eé]\s+es|c[oó]mo\s+funciona|un\s+poco\s+de)\s+)+",
    re.IGNORECASE,
)
#: "…por favor" no es parte del tema.
_CORTESIA = re.compile(r"[\s,]*(?:por\s+favor|porfa(?:vor)?|pls|please)\s*$", re.IGNORECASE)
#: Lo que viene después del tema y no es tema. Contra Render, "quiero aprender
#: electrónica para armar un robot seguidor de línea" guardaba el nivel bajo esa
#: frase entera, y "quiero aprender electrónica, empecemos" buscaba "electrónica,
#: empecemos": el nivel no se encontraba nunca y se volvía a ofrecer la nivelación.
#: - "para" + infinitivo es el propósito ("para armar…"); "matemáticas para
#:   ingeniería" no lleva infinitivo y se conserva. "porque…" es el motivo.
#: - Tras una coma o un "y" empieza otra cosa ("…, empecemos", "… y ya").
_PROPOSITO = re.compile(
    r"\s+para\s+(?:poder\s+)?\w+(?:ar|er|ir)(?:lo|la|los|las|me|te|se)?\b.*$"
    r"|\s+(?:porque|pues|ya\s+que)\b.*$"
    r"|\s*,.*$"
    r"|\s+y\s+(?:empecemos|empezamos|vamos|ya|luego|despu[eé]s)\b.*$",
    re.IGNORECASE,
)
_MAX_TEMA = 60


#: "Pregúntame cómo me gusta aprender". Va antes del cuestionario: "pregúntame"
#: también abre un quiz, y contra Render el tutor respondió "te prepararé un
#: cuestionario para que practiques cómo te gusta aprender".
_PIDE_ESTILO = re.compile(
    r"(?:pregúnta(?:me)?|preguntame|dime|ayúdame\s+a\s+(?:saber|elegir|descubrir)|"
    r"quiero\s+(?:saber|elegir|decirte)|cuál\s+es|c[oó]mo\s+s[eé])\b.{0,40}?"
    r"(?:c[oó]mo\s+(?:me\s+gusta|prefiero|aprendo)|m[aá]s\s+c[oó]modo|estilo\s+de\s+aprendizaje|"
    r"forma\s+de\s+aprender|manera\s+de\s+aprender)",
    re.IGNORECASE,
)

#: "Me siento más cómodo con esquemas", "aprendo mejor paso a paso". Tiene que
#: ser una declaración general sobre cómo aprende: "ponme un ejemplo" pide un
#: ejemplo en este turno y no es una preferencia para siempre.
_DECLARA_ESTILO = re.compile(
    r"(?:me\s+siento\s+m[aá]s\s+c[oó]modo|aprendo\s+mejor|me\s+va\s+mejor|"
    r"me\s+gusta(?:n)?\s+(?:m[aá]s\s+)?(?:aprender|que\s+me\s+expliques|las\s+explicaciones)|"
    r"prefiero\s+(?:aprender|que\s+me\s+(?:lo\s+)?(?:expliques|compares|muestres|ense[nñ]es)|"
    r"las\s+explicaciones|explicaciones))"
    r"(?P<resto>.*)$",
    re.IGNORECASE,
)

#: Palabra → estilo. Si nombra varios, gana el primero que dice.
_PALABRAS_ESTILO: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"esquema|dibujo|diagrama|visual|gr[aá]fico|imagen", re.I), "visual"),
    (re.compile(r"paso\s+a\s+paso|por\s+pasos", re.I), "step_by_step"),
    (re.compile(r"analog|ejemplo|compar|met[aá]fora", re.I), "analogy"),
    (re.compile(r"f[oó]rmula|demostraci|matem[aá]tic", re.I), "mathematical"),
    (re.compile(r"t[eé]cnic|riguros|formal", re.I), "technical"),
    (re.compile(r"sencill|simple|sin\s+tecnicismos|f[aá]cil", re.I), "simple"),
]


def _estilo_declarado(texto: str) -> str | None:
    m = _DECLARA_ESTILO.search(texto)
    if not m:
        return None
    # En toda la declaración, no solo después del verbo: en "prefiero que me lo
    # compares" el estilo está en el propio verbo.
    resto = m.group(0)
    hallados = [(p.search(resto), estilo) for p, estilo in _PALABRAS_ESTILO]
    hallados = [(h.start(), estilo) for h, estilo in hallados if h]
    return min(hallados)[1] if hallados else None


def _tema_pedido(texto: str) -> str | None:
    """El tema tal como lo escribió el estudiante, si pidió aprender uno.

    Conserva su forma —tildes, mayúsculas— porque es lo que se le va a mostrar.
    La canonización para buscar en el currículum la hace quien lo consuma.
    """
    m = _WANTS_TO_LEARN.search(texto)
    if not m:
        return None
    resto = re.split(r"[?.!¿¡\n]", m.group("resto"), maxsplit=1)[0]
    resto = _RELLENO.sub("", resto.strip()).strip(" ,;:")
    resto = _CORTESIA.sub("", resto).strip(" ,;:")
    resto = _PROPOSITO.sub("", resto).strip(" ,;:")
    if not resto:
        return None
    return resto[:_MAX_TEMA].rsplit(" ", 1)[0] if len(resto) > _MAX_TEMA else resto


#: Abreviaturas de chat. Se expanden SOLO para detectar la intención: al modelo le
#: llega lo que escribió el estudiante, tal cual. Sin esto "q es una variable" no
#: contaba como pregunta y "qn sos" no se entendía como "¿quién sos?".
#: "x" no se expande a "por": en esta plataforma es sobre todo una incógnita.
_ABREVIATURAS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:qn|qien|kien)\b", re.I), "quién"),
    (re.compile(r"\b(?:xq|pq|porq|pk)\b", re.I), "por qué"),
    (re.compile(r"\b(?:q|k|ke)\b", re.I), "qué"),
    (re.compile(r"\b(?:tmb|tb|tambn)\b", re.I), "también"),
    (re.compile(r"\b(?:dnd)\b", re.I), "dónde"),
    (re.compile(r"\b(?:cm|cmo)\b", re.I), "cómo"),
    (re.compile(r"\b(?:porfa|pls|plis)\b", re.I), "por favor"),
    (re.compile(r"\b(?:nd)\b", re.I), "nada"),
]


def _normalizar(texto: str) -> str:
    for patron, completa in _ABREVIATURAS:
        texto = patron.sub(completa, texto)
    return texto


#: Preguntas sobre el tutor mismo. Admiten hasta dos palabras de cola ("¿quién
#: sos vos?", "¿qué podés hacer por mí?") pero no más: "¿qué podés hacer con las
#: ecuaciones?" es una duda sobre ecuaciones, no sobre el tutor.
_ABOUT = re.compile(
    r"^\W*(?:hola\W+)?(?:"
    r"qui[eé]n\s+(?:sos|eres|es\s+laria)|qu[eé]\s+(?:sos|eres)|"
    r"c[oó]mo\s+te\s+llam(?:as|[aá]s)|"
    r"qu[eé]\s+(?:pod[eé]s|puedes|sab[eé]s|sabes)\s+hacer|"
    r"para\s+qu[eé]\s+(?:serv[ií]s|sirves|sirve\s+plenum)|qu[eé]\s+es\s+(?:laria|plenum)|"
    r"c[oó]mo\s+funcion(?:as|[aá]s|a\s+plenum)|"
    r"(?:sos|eres)\s+(?:un[ao]?\s+)?(?:bot|robot|ia|humano|persona|real|m[aá]quina)"
    r")\b\W*(?:\w+\W*){0,2}$",
    re.IGNORECASE,
)


# Conceptos frecuentes al pedir aprender (heurística ligera, reuso del detector)
_TOPIC_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bgrafos?\b", re.I), "grafos"),
    (re.compile(r"\bdfs\b|\bbfs\b", re.I), "recorrido de grafos"),
    (re.compile(r"\bdijkstra\b", re.I), "dijkstra"),
    (re.compile(r"\b[áa]lgebra\b", re.I), "álgebra"),
    (re.compile(r"\becuaci[oó]n(es)?\b", re.I), "ecuaciones"),
    (re.compile(r"\bpolinomios?\b", re.I), "polinomios"),
    (re.compile(r"\bmatrices?\b|\bmatriz\b", re.I), "matrices"),
    (re.compile(r"\bderivadas?\b", re.I), "derivadas"),
    (re.compile(r"\bintegrales?\b", re.I), "integrales"),
    (re.compile(r"\bl[ií]mites?\b", re.I), "límites"),
    (re.compile(r"\bprobabilidad", re.I), "probabilidad"),
    (re.compile(r"\bestad[ií]stica", re.I), "estadística"),
]


class IntentDetector:
    """Detecta intención pedagógica en el mensaje del estudiante."""

    def __init__(self) -> None:
        self._signal = LearningSignalDetector()

    def detect(self, message: str) -> Intention:
        text = _normalizar((message or "").strip())
        if not text:
            return Intention(TutorIntent.NONE, 0.0, None)

        # Primero: ¿pregunta por el tutor? Si no se separa aquí, con un libro
        # vinculado "qn sos" recibía una clase sobre el material.
        if _ABOUT.search(text):
            return Intention(TutorIntent.ABOUT, 0.9, None)

        # Luego: ¿habla de cómo aprende? Antes que el quiz ("pregúntame…").
        declarado = _estilo_declarado(text)
        if declarado:
            return Intention(TutorIntent.LEARNING_STYLE, 0.85, None, declared_style=declarado)
        if _PIDE_ESTILO.search(text):
            return Intention(TutorIntent.LEARNING_STYLE, 0.85, None, ask_learning_style=True)

        # El tema escrito por el estudiante manda sobre la lista fija: la lista
        # solo conoce doce conceptos, y "quiero aprender historia" no traía tema.
        pedido = _tema_pedido(text)
        topic = pedido or next(
            (label for pattern, label in _TOPIC_PATTERNS if pattern.search(text)),
            None,
        )
        ofrecer = pedido is not None
        pide_quiz, tema_quiz = _cuestionario_pedido(text)
        if pide_quiz:
            topic = tema_quiz or topic

        # Señal de ayuda/confusión tiene prioridad: pedir ayuda ≠ aprender.
        signal = self._signal.detect(text)
        if signal.kind.value in ("confusion", "help", "novice"):
            # "Soy principiante, quiero aprender X" es justo a quien más le
            # sirve nivelarse: la oferta sobrevive aunque la intención sea HINT.
            # Igual con "no entiendo, ponme ejercicios": practicar es lo que pide.
            return Intention(
                TutorIntent.HINT, signal.strength, topic, ofrecer and not pide_quiz, pide_quiz
            )

        if pide_quiz:
            return Intention(TutorIntent.QUIZ, 0.9, topic, offer_quiz=True)
        # Pedir aprender un tema es LEARN aunque la frase no encaje en _LEARN.
        if ofrecer or _LEARN.search(text):
            return Intention(TutorIntent.LEARN, 0.8, topic, ofrecer)
        if _CELEBRATE.search(text):
            return Intention(TutorIntent.CELEBRATE, 0.6, topic)
        return Intention(TutorIntent.GENERAL, 0.4, topic)
