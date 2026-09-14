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
