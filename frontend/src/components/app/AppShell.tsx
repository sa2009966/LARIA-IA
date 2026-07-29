import { useCallback, useEffect, useState, type ReactNode } from "react";
import { BookOpen, Brain, LogOut, MessageSquare, ClipboardList } from "lucide-react";
import { LariaMark } from "@/components/brand/LariaMark";
import { LoginForm, RegisterForm } from "@/components/auth/AuthForms";
import { DocumentList, UploadDocument } from "@/components/documents/Documents";
import { TutorChat } from "@/components/tutor/TutorChat";
import { QuizPanel } from "@/components/quiz/QuizPanel";
import { ProfilePanel } from "@/components/learning/ProfilePanel";
import { Button } from "@/components/ui/button";
import {
  clearSession,
  getUser,
  isAuthenticated,
  subscribeAuth,
} from "@/lib/auth-store";
import { analyzeDocument, listDocuments } from "@/lib/laria-api";
import {
  LariaApiError,
  type AnalysisResult,
  type DocumentItem,
} from "@/lib/laria-types";

type AuthView = "login" | "register";
type MainTab = "tutor" | "quiz" | "profile";

type Props = {
  initialAuthView?: AuthView;
};

export default function AppShell({ initialAuthView = "login" }: Props) {
  const [authed, setAuthed] = useState(isAuthenticated());
  const [authView, setAuthView] = useState<AuthView>(initialAuthView);
  const [userLabel, setUserLabel] = useState(getUser()?.username ?? "");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [selected, setSelected] = useState<DocumentItem | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [tab, setTab] = useState<MainTab>("tutor");
  const [profileKey, setProfileKey] = useState(0);
  const [mobileNav, setMobileNav] = useState(false);

  useEffect(() => {
    return subscribeAuth(() => {
      setAuthed(isAuthenticated());
      setUserLabel(getUser()?.username ?? "");
    });
  }, []);

  const refreshDocs = useCallback(async () => {
    setDocsLoading(true);
    try {
      const docs = await listDocuments();
      setDocuments(docs);
    } catch {
      setDocuments([]);
    } finally {
      setDocsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authed) void refreshDocs();
  }, [authed, refreshDocs]);

  async function runAnalyze(doc: DocumentItem, force = false) {
    setAnalysisLoading(true);
    setAnalysisError(null);
    try {
      const result = await analyzeDocument(doc.id, force);
      setAnalysis(result);
      setDocuments((prev) =>
        prev.map((d) => (d.id === doc.id ? { ...d, has_analysis: true } : d)),
      );
      setSelected((prev) =>
        prev && prev.id === doc.id ? { ...prev, has_analysis: true } : prev,
      );
    } catch (err) {
      setAnalysis(null);
      setAnalysisError(err instanceof LariaApiError ? err.detail : "Error al analizar");
    } finally {
      setAnalysisLoading(false);
    }
  }

  function handleSelect(doc: DocumentItem) {
    setSelected(doc);
    setAnalysis(null);
    setAnalysisError(null);
    setTab("tutor");
    setMobileNav(false);
    void runAnalyze(doc, false);
  }

  function handleUploaded(doc: DocumentItem) {
    setDocuments((prev) => [doc, ...prev]);
    handleSelect(doc);
  }

  function handleDeleted(id: string) {
    setDocuments((prev) => prev.filter((d) => d.id !== id));
    if (selected?.id === id) {
      setSelected(null);
      setAnalysis(null);
    }
  }

  function logout() {
    clearSession();
    setSelected(null);
    setDocuments([]);
    setAnalysis(null);
    setAuthView("login");
  }

  if (!authed) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4 py-10">
        <div className="w-full max-w-lg rounded-2xl border border-border bg-card/90 p-6 shadow-sm backdrop-blur sm:p-8">
          <LariaMark size="lg" subtitle className="mb-8 animate-brand-rise" />
          {authView === "login" ? (
            <LoginForm
              onSuccess={() => setAuthed(true)}
              onSwitchToRegister={() => setAuthView("register")}
            />
          ) : (
            <RegisterForm
              onSuccess={() => setAuthed(true)}
              onSwitchToLogin={() => setAuthView("login")}
            />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen min-h-0 flex-col overflow-hidden">
      <header className="flex items-center justify-between border-b border-border/80 bg-card/70 px-4 py-3 backdrop-blur">
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="rounded-md border border-border px-2 py-1 text-xs md:hidden"
            onClick={() => setMobileNav((v) => !v)}
          >
            Materiales
          </button>
          <LariaMark size="sm" />
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="hidden text-muted-foreground sm:inline">{userLabel}</span>
          <Button type="button" variant="ghost" size="sm" onClick={logout}>
            <LogOut className="size-4" />
            Salir
          </Button>
        </div>
      </header>

      <div className="relative flex min-h-0 flex-1">
        <aside
          className={`absolute inset-y-0 left-0 z-20 w-72 shrink-0 border-r border-border bg-card/95 backdrop-blur transition-transform md:static md:translate-x-0 ${
            mobileNav ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="flex h-full flex-col">
            <div className="border-b border-border p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Materiales
              </p>
              <UploadDocument onUploaded={handleUploaded} />
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              <DocumentList
                documents={documents}
                selectedId={selected?.id ?? null}
                onSelect={handleSelect}
                onDeleted={handleDeleted}
                loading={docsLoading}
              />
            </div>
          </div>
        </aside>

        {mobileNav ? (
          <button
            type="button"
            className="absolute inset-0 z-10 bg-ink/20 md:hidden"
            aria-label="Cerrar menú"
            onClick={() => setMobileNav(false)}
          />
        ) : null}

        <main className="flex min-h-0 min-w-0 flex-1 flex-col">
          {!selected ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center animate-panel-fade">
              <BookOpen className="size-10 text-accent" />
              <h2 className="font-display text-3xl text-ink">Elige un material</h2>
              <p className="max-w-md text-sm text-muted-foreground">
                LARIA analiza tu texto, responde con pedagogía adaptativa y actualiza tu
                perfil cognitivo en MongoDB — no es un chat genérico.
              </p>
            </div>
          ) : (
            <>
              <div className="border-b border-border bg-card/50 px-4 py-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="font-display text-2xl text-ink">{selected.filename}</h2>
                    <p className="text-sm text-muted-foreground">{selected.subject}</p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={analysisLoading}
                    onClick={() => void runAnalyze(selected, true)}
                  >
                    {analysisLoading ? "Analizando…" : "Reanalizar"}
                  </Button>
                </div>
                {analysisError ? (
                  <p className="mt-2 text-sm text-destructive">{analysisError}</p>
                ) : null}
                {analysis ? (
                  <div className="mt-3 grid gap-3 lg:grid-cols-2">
                    <div className="rounded-xl border border-border bg-card/80 p-3 text-sm">
                      <p className="text-xs font-semibold uppercase tracking-wide text-accent">
                        Resumen
                      </p>
                      <p className="mt-1 leading-relaxed text-ink">{analysis.summary}</p>
                    </div>
                    <div className="rounded-xl border border-border bg-card/80 p-3 text-sm">
                      <p className="text-xs font-semibold uppercase tracking-wide text-accent">
                        Conceptos clave
                      </p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {analysis.key_concepts.map((c) => (
                          <span
                            key={c}
                            className="rounded-md bg-secondary px-2 py-0.5 text-xs text-ink"
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="flex gap-1 border-b border-border px-2 pt-2">
                <TabButton
                  active={tab === "tutor"}
                  icon={<MessageSquare className="size-4" />}
                  label="Tutor"
                  onClick={() => setTab("tutor")}
                />
                <TabButton
                  active={tab === "quiz"}
                  icon={<ClipboardList className="size-4" />}
                  label="Quiz"
                  onClick={() => setTab("quiz")}
                />
                <TabButton
                  active={tab === "profile"}
                  icon={<Brain className="size-4" />}
                  label="Perfil"
                  onClick={() => {
                    setTab("profile");
                    setProfileKey((k) => k + 1);
                  }}
                />
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto p-4">
                {tab === "tutor" ? (
                  <div className="mx-auto flex h-full max-w-3xl flex-col">
                    <TutorChat
                      documentId={selected.id}
                      suggestedQuestions={analysis?.suggested_questions}
                    />
                  </div>
                ) : null}
                {tab === "quiz" ? (
                  <div className="mx-auto max-w-3xl">
                    <QuizPanel
                      documentId={selected.id}
                      onCompleted={() => setProfileKey((k) => k + 1)}
                    />
                  </div>
                ) : null}
                {tab === "profile" ? (
                  <div className="mx-auto max-w-3xl">
                    <ProfilePanel refreshKey={profileKey} />
                  </div>
                ) : null}
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function TabButton({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-t-lg px-3 py-2 text-sm transition ${
        active
          ? "bg-card text-ink shadow-[inset_0_-2px_0_0_var(--accent)]"
          : "text-muted-foreground hover:text-ink"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
