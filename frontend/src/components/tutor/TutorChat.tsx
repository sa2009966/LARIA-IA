import { useEffect, useRef, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import { Button } from "@/components/ui/button";
import { askDocument, getLearningHistory } from "@/lib/laria-api";
import { LariaApiError, type TutorInteraction } from "@/lib/laria-types";
import { Send } from "lucide-react";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type Props = {
  documentId: string;
  suggestedQuestions?: string[];
};

export function TutorChat({ documentId, suggestedQuestions = [] }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const history = await getLearningHistory();
        if (cancelled) return;
        const forDoc = history.tutor_interactions
          .filter((i: TutorInteraction) => i.document_id === documentId)
          .sort((a, b) => new Date(a.asked_at).getTime() - new Date(b.asked_at).getTime());
        const rebuilt: Message[] = [];
        for (const item of forDoc) {
          rebuilt.push({ id: `${item.id}-q`, role: "user", content: item.question });
          rebuilt.push({ id: `${item.id}-a`, role: "assistant", content: item.answer });
        }
        setMessages(rebuilt);
      } catch {
        if (!cancelled) setMessages([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(question: string) {
    const q = question.trim();
    if (!q || loading) return;
    setError(null);
    setInput("");
    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: q };
    setMessages((m) => [...m, userMsg]);
    setLoading(true);
    try {
      const res = await askDocument(documentId, q);
      setMessages((m) => [
        ...m,
        { id: crypto.randomUUID(), role: "assistant", content: res.answer },
      ]);
    } catch (err) {
      const detail = err instanceof LariaApiError ? err.detail : "Error al preguntar";
      setError(detail);
      setMessages((m) => [
        ...m,
        { id: crypto.randomUUID(), role: "assistant", content: `No pude responder: ${detail}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void send(input);
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-1 py-2">
        {!messages.length && !loading ? (
          <div className="rounded-xl border border-dashed border-border bg-card/50 p-4 text-sm text-muted-foreground">
            Pregunta sobre este material. LARIA adapta la explicación a tu perfil cognitivo
            (modo, dificultad y foco conceptual los decide el motor pedagógico en el backend).
          </div>
        ) : null}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`max-w-[92%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${
              m.role === "user"
                ? "ml-auto bg-ink text-primary-foreground"
                : "mr-auto border border-border bg-card text-foreground"
            }`}
          >
            {m.role === "assistant" ? (
              <div className="prose prose-sm max-w-none prose-headings:font-display prose-p:my-2">
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{m.content}</ReactMarkdown>
              </div>
            ) : (
              m.content
            )}
          </div>
        ))}
        {loading ? (
          <p className="text-xs text-muted-foreground animate-pulse">LARIA está pensando…</p>
        ) : null}
        <div ref={bottomRef} />
      </div>

      {suggestedQuestions.length ? (
        <div className="flex flex-wrap gap-2 border-t border-border/70 py-2">
          {suggestedQuestions.slice(0, 4).map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => void send(q)}
              className="rounded-full border border-border bg-secondary/70 px-3 py-1 text-xs text-ink transition hover:bg-secondary"
            >
              {q}
            </button>
          ))}
        </div>
      ) : null}

      {error ? <p className="pb-1 text-xs text-destructive">{error}</p> : null}

      <form onSubmit={handleSubmit} className="flex gap-2 border-t border-border pt-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pregunta sobre el material…"
          className="min-w-0 flex-1 rounded-xl border border-border bg-card px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          disabled={loading}
        />
        <Button type="submit" size="icon" className="bg-accent hover:bg-accent/90" disabled={loading || !input.trim()}>
          <Send className="size-4" />
        </Button>
      </form>
    </div>
  );
}
