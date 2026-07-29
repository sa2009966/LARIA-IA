import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { uploadDocument, deleteDocument } from "@/lib/laria-api";
import { LariaApiError, SUBJECTS, type DocumentItem } from "@/lib/laria-types";
import { FileText, Trash2, Sparkles } from "lucide-react";

type ListProps = {
  documents: DocumentItem[];
  selectedId: string | null;
  onSelect: (doc: DocumentItem) => void;
  onDeleted: (id: string) => void;
  loading?: boolean;
};

export function DocumentList({ documents, selectedId, onSelect, onDeleted, loading }: ListProps) {
  const [busyId, setBusyId] = useState<string | null>(null);

  async function handleDelete(id: string) {
    setBusyId(id);
    try {
      await deleteDocument(id);
      onDeleted(id);
    } catch {
      /* parent can toast via reload */
    } finally {
      setBusyId(null);
    }
  }

  if (loading) {
    return <p className="px-3 py-6 text-sm text-muted-foreground">Cargando materiales…</p>;
  }

  if (!documents.length) {
    return (
      <p className="px-3 py-6 text-sm text-muted-foreground">
        Aún no tienes materiales. Sube un texto para empezar a estudiar con LARIA.
      </p>
    );
  }

  return (
    <ul className="space-y-1 p-2">
      {documents.map((doc) => {
        const active = doc.id === selectedId;
        return (
          <li key={doc.id}>
            <div
              className={`group flex items-start gap-2 rounded-lg px-2 py-2 transition-colors ${
                active ? "bg-secondary" : "hover:bg-secondary/60"
              }`}
            >
              <button
                type="button"
                className="min-w-0 flex-1 text-left"
                onClick={() => onSelect(doc)}
              >
                <div className="flex items-center gap-2">
                  <FileText className="size-4 shrink-0 text-accent" />
                  <span className="truncate text-sm font-medium text-ink">{doc.filename}</span>
                </div>
                <div className="mt-1 flex flex-wrap gap-2 pl-6 text-xs text-muted-foreground">
                  <span>{doc.subject}</span>
                  {doc.has_analysis ? (
                    <span className="inline-flex items-center gap-1 text-accent">
                      <Sparkles className="size-3" /> analizado
                    </span>
                  ) : (
                    <span>sin analizar</span>
                  )}
                </div>
              </button>
              <button
                type="button"
                aria-label="Eliminar"
                disabled={busyId === doc.id}
                onClick={() => handleDelete(doc.id)}
                className="rounded p-1 text-muted-foreground opacity-0 transition group-hover:opacity-100 hover:text-destructive"
              >
                <Trash2 className="size-4" />
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

type UploadProps = {
  onUploaded: (doc: DocumentItem) => void;
};

export function UploadDocument({ onUploaded }: UploadProps) {
  const [filename, setFilename] = useState("");
  const [subject, setSubject] = useState<string>(SUBJECTS[0]);
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const doc = await uploadDocument({
        filename: filename.trim() || "material.txt",
        subject,
        content: content.trim(),
      });
      onUploaded(doc);
      setFilename("");
      setContent("");
      setOpen(false);
    } catch (err) {
      setError(err instanceof LariaApiError ? err.detail : "Error al subir");
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <Button
        type="button"
        variant="secondary"
        className="w-full"
        onClick={() => setOpen(true)}
      >
        Subir material
      </Button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-xl border border-border bg-card/80 p-3 animate-panel-fade">
      <label className="block space-y-1 text-xs font-medium">
        Nombre del archivo
        <input
          value={filename}
          onChange={(e) => setFilename(e.target.value)}
          placeholder="algebra-desigualdades.txt"
          className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
      </label>
      <label className="block space-y-1 text-xs font-medium">
        Materia
        <select
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
        >
          {SUBJECTS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      <label className="block space-y-1 text-xs font-medium">
        Contenido (texto)
        <textarea
          required
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={6}
          placeholder="Pega aquí el material de estudio…"
          className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
      </label>
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
      <div className="flex gap-2">
        <Button type="submit" size="sm" className="flex-1 bg-accent hover:bg-accent/90" disabled={loading}>
          {loading ? "Subiendo…" : "Guardar"}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}
