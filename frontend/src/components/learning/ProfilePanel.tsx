import { useEffect, useState } from "react";
import { getLearningHistory, getStudentProfile } from "@/lib/laria-api";
import {
  LariaApiError,
  type LearningHistory,
  type StudentProfile,
} from "@/lib/laria-types";

type Props = {
  refreshKey?: number;
};

export function ProfilePanel({ refreshKey = 0 }: Props) {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [history, setHistory] = useState<LearningHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [p, h] = await Promise.all([getStudentProfile(), getLearningHistory()]);
        if (cancelled) return;
        setProfile(p);
        setHistory(h);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof LariaApiError ? err.detail : "No se pudo cargar el perfil");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  if (loading) {
    return <p className="text-sm text-muted-foreground animate-pulse">Cargando perfil cognitivo…</p>;
  }

  if (error) {
    return <p className="text-sm text-destructive">{error}</p>;
  }

  if (!profile || !history) return null;

  const concepts = [...profile.mastery_by_concept].sort(
    (a, b) => a.effective_mastery - b.effective_mastery,
  );

  return (
    <div className="space-y-6 animate-panel-fade">
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Ritmo" value={profile.pace} />
        <Stat label="Intentos" value={String(profile.total_attempts)} />
        <Stat
          label="Señales de struggle"
          value={String(profile.total_struggle_signals)}
        />
      </div>

      {history.recommendations.length ? (
        <section>
          <h3 className="font-display text-xl text-ink">Recomendaciones</h3>
          <ul className="mt-3 space-y-2">
            {history.recommendations.map((r, i) => (
              <li
                key={`${r.kind}-${i}`}
                className="rounded-xl border border-border bg-card/80 px-3 py-2 text-sm"
              >
                <span className="text-xs font-semibold uppercase tracking-wide text-accent">
                  {r.kind}
                </span>
                <p className="mt-1 text-ink">{r.message}</p>
                {r.suggested_minutes ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    ~{r.suggested_minutes} min sugeridos
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section>
        <h3 className="font-display text-xl text-ink">Mastery por concepto</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Mastery efectivo incluye curva del olvido (backend).
        </p>
        {!concepts.length ? (
          <p className="mt-3 text-sm text-muted-foreground">
            Aún no hay evidencia. Pregunta al tutor o completa un quiz.
          </p>
        ) : (
          <ul className="mt-3 space-y-3">
            {concepts.slice(0, 12).map((c) => {
              const pct = Math.round(Math.max(0, Math.min(1, c.effective_mastery)) * 100);
              return (
                <li key={c.concept_key}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="font-medium text-ink">{c.concept_key}</span>
                    <span className="text-muted-foreground">{pct}%</span>
                  </div>
                  <div className="mastery-bar h-2 overflow-hidden rounded-full bg-muted">
                    <span
                      className="block h-full rounded-full bg-accent"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {profile.pedagogical_memory ? (
        <section className="rounded-xl border border-border bg-card/70 p-4 text-sm">
          <h3 className="font-display text-lg text-ink">Memoria pedagógica</h3>
          <p className="mt-2 text-muted-foreground">
            Estilo preferido:{" "}
            <strong className="text-ink">
              {profile.pedagogical_memory.preferred_explanation_style}
            </strong>
          </p>
          {profile.pedagogical_memory.frequent_misconceptions.length ? (
            <p className="mt-2">
              Misconceptions:{" "}
              {profile.pedagogical_memory.frequent_misconceptions.join(", ")}
            </p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-card/80 px-3 py-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 font-display text-2xl text-ink">{value}</p>
    </div>
  );
}
