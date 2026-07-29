import { useState } from "react";
import { Button } from "@/components/ui/button";
import { generateQuiz, submitQuizAttempt } from "@/lib/laria-api";
import {
  LariaApiError,
  type QuizAttemptResult,
  type QuizPublic,
} from "@/lib/laria-types";

type Props = {
  documentId: string;
  onCompleted?: () => void;
};

export function QuizPanel({ documentId, onCompleted }: Props) {
  const [quiz, setQuiz] = useState<QuizPublic | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<QuizAttemptResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [numQuestions, setNumQuestions] = useState(5);

  async function handleGenerate() {
    setError(null);
    setResult(null);
    setAnswers({});
    setLoading(true);
    try {
      const q = await generateQuiz(documentId, numQuestions);
      setQuiz(q);
    } catch (err) {
      setError(err instanceof LariaApiError ? err.detail : "No se pudo generar el quiz");
      setQuiz(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit() {
    if (!quiz) return;
    setError(null);
    setLoading(true);
    try {
      const res = await submitQuizAttempt(quiz.id, answers);
      setResult(res);
      onCompleted?.();
    } catch (err) {
      setError(err instanceof LariaApiError ? err.detail : "No se pudo enviar el intento");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4 animate-panel-fade">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-xs font-medium text-muted-foreground">Preguntas</span>
          <input
            type="number"
            min={1}
            max={20}
            value={numQuestions}
            onChange={(e) => setNumQuestions(Number(e.target.value) || 5)}
            className="w-20 rounded-md border border-border bg-card px-2 py-1.5 text-sm"
          />
        </label>
        <Button
          type="button"
          onClick={() => void handleGenerate()}
          disabled={loading}
          className="bg-ink hover:bg-ink/90"
        >
          {loading && !quiz ? "Generando…" : "Generar quiz adaptativo"}
        </Button>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {quiz && !result ? (
        <div className="space-y-4">
          {quiz.questions.map((q) => (
            <fieldset key={q.index} className="rounded-xl border border-border bg-card/70 p-3">
              <legend className="px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {q.difficulty} · pregunta {q.index + 1}
              </legend>
              <p className="mb-3 text-sm font-medium text-ink">{q.text}</p>
              <div className="space-y-2">
                {Object.entries(q.options).map(([key, label]) => (
                  <label
                    key={key}
                    className="flex cursor-pointer items-start gap-2 rounded-lg border border-transparent px-2 py-1.5 text-sm hover:bg-secondary/60 has-[:checked]:border-accent has-[:checked]:bg-secondary"
                  >
                    <input
                      type="radio"
                      name={`q-${q.index}`}
                      value={key}
                      checked={answers[String(q.index)] === key}
                      onChange={() =>
                        setAnswers((prev) => ({ ...prev, [String(q.index)]: key }))
                      }
                      className="mt-1"
                    />
                    <span>
                      <strong className="text-accent">{key}.</strong> {label}
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
          <Button
            type="button"
            className="bg-accent hover:bg-accent/90"
            disabled={loading || Object.keys(answers).length === 0}
            onClick={() => void handleSubmit()}
          >
            {loading ? "Calificando…" : "Enviar intento"}
          </Button>
        </div>
      ) : null}

      {result ? (
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="font-display text-2xl text-ink">
            {result.score}/{result.total_points}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Resultado guardado en tu perfil cognitivo (MongoDB).
          </p>
          <ul className="mt-4 space-y-2 text-sm">
            {result.questions.map((q) => (
              <li
                key={q.index}
                className={`rounded-lg px-3 py-2 ${
                  q.is_correct ? "bg-secondary/80" : "bg-destructive/10"
                }`}
              >
                <p className="font-medium">{q.text}</p>
                <p className="text-xs text-muted-foreground">
                  Elegiste {q.selected ?? "—"} · correcta {q.correct_answer}
                </p>
              </li>
            ))}
          </ul>
          <Button type="button" variant="secondary" className="mt-4" onClick={() => void handleGenerate()}>
            Nuevo quiz
          </Button>
        </div>
      ) : null}
    </div>
  );
}
