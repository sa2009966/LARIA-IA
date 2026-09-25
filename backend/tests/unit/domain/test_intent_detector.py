import pytest

from src.domain.services.intent_detector import IntentDetector, TutorIntent


class TestIntentDetector:

    def setup_method(self):
        self.detector = IntentDetector()

    def test_empty_is_none(self):
        r = self.detector.detect("   ")
        assert r.intent == TutorIntent.NONE
        assert r.confidence == 0.0

    def test_learn_explica(self):
        r = self.detector.detect("explica qué es un grafo")
        assert r.intent == TutorIntent.LEARN
        assert r.topic_hint == "grafos"

    def test_learn_quiero_aprender(self):
        r = self.detector.detect("quiero aprender álgebra")
        assert r.intent == TutorIntent.LEARN
        assert r.topic_hint == "álgebra"

    def test_learn_que_es(self):
        r = self.detector.detect("¿qué es una matriz?")
        assert r.intent == TutorIntent.LEARN
        assert r.topic_hint == "matrices"

    def test_quiz_consultar(self):
        r = self.detector.detect("hazme un quiz de polinomios")
        assert r.intent == TutorIntent.QUIZ
        assert r.topic_hint == "polinomios"

    def test_quiz_examen(self):
        r = self.detector.detect("ponme un examen rápido")
        assert r.intent == TutorIntent.QUIZ

    def test_hint_ayuda_tiene_prioridad(self):
        # "ayúdame a entender" → help, no learn
        r = self.detector.detect("ayúdame a entender grafos")
        assert r.intent == TutorIntent.HINT

    def test_hint_no_entiendo(self):
        r = self.detector.detect("no entiendo las derivadas")
        assert r.intent == TutorIntent.HINT
        assert r.topic_hint == "derivadas"

    def test_celebrate(self):
        r = self.detector.detect("sí, entendí, continuemos")
        assert r.intent == TutorIntent.CELEBRATE

    def test_general(self):
        r = self.detector.detect("buenos días, cómo estás")
        assert r.intent == TutorIntent.GENERAL

    def test_dijkstra_topic(self):
        r = self.detector.detect("explícame dijkstra por favor")
        assert r.intent == TutorIntent.LEARN
        assert r.topic_hint == "dijkstra"


class TestPedirAprenderUnTema:
    """La señal estrecha para ofrecer nivelación (ADR-017).

    `LEARN` salta con cualquier pregunta conceptual ("qué es", "define"), así que
    servía de disparador para ofrecer un diagnóstico a cada duda. Estos tests
    fijan la diferencia entre **pedir aprender un tema** y **preguntar un
    concepto**, y que el tema llegue como lo escribió el estudiante.
    """

    def setup_method(self):
        self.detector = IntentDetector()

    @pytest.mark.parametrize(
        "frase, tema",
        [
            ("quiero aprender programación", "programación"),
            ("Quiero aprender sobre la electrónica!", "electrónica"),
            ("quiero estudiar historia de México", "historia de México"),
            ("me enseñas astronomía?", "astronomía"),
            ("enséñame ecuaciones cuadráticas por favor", "ecuaciones cuadráticas"),
            ("¿me puedes enseñar química orgánica?", "química orgánica"),
        ],
    )
    def test_pedir_aprender_un_tema_ofrece_nivelacion(self, frase, tema):
        r = self.detector.detect(frase)

        assert r.intent == TutorIntent.LEARN
        assert r.suggest_placement is True
        # Con tildes y como lo escribió: es lo que se le va a mostrar.
        assert r.topic_hint == tema

    @pytest.mark.parametrize(
        "frase",
        ["¿qué es una variable?", "explícame las derivadas", "define matriz", "vamos a ver"],
    )
    def test_una_pregunta_conceptual_no_ofrece_nivelacion(self, frase):
        """Sigue siendo LEARN, pero una duda no es un punto de partida."""
        r = self.detector.detect(frase)

        assert r.intent == TutorIntent.LEARN
        assert r.suggest_placement is False

    def test_sin_tema_no_hay_nada_que_nivelar(self):
        assert self.detector.detect("quiero aprender").suggest_placement is False

    def test_el_principiante_tambien_recibe_la_oferta(self):
        """"Soy principiante" gana como HINT, pero es a quien más le sirve nivelarse."""
        r = self.detector.detect("soy principiante, quiero aprender álgebra")

        assert r.suggest_placement is True
        assert r.topic_hint == "álgebra"

    def test_ensenar_con_y_sin_tilde(self):
        """"enséñame" y "enseñas" no se reconocían: el patrón exigía `ense` sin tilde."""
        for frase in ("enséñame fracciones", "me enseñas fracciones", "enseñame fracciones"):
            assert self.detector.detect(frase).intent == TutorIntent.LEARN, frase
