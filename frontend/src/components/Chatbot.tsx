"use client";

import {
  type ChangeEvent,
  type ClipboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import ThemeToggle from "@/components/ThemeToggle";
import {
  ChatContainerContent,
  ChatContainerRoot,
  ChatContainerScrollAnchor,
} from "@/components/prompt-kit/chat-container";
import { Message, MessageAction, MessageActions, MessageContent } from "@/components/prompt-kit/message";
import {
  PromptInput,
  PromptInputAction,
  PromptInputActions,
  PromptInputTextarea,
} from "@/components/prompt-kit/prompt-input";
import { ScrollButton } from "@/components/prompt-kit/scroll-button";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  ArrowUp,
  Check,
  Copy,
  Image,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Boxes,
  Cpu,
  Plus,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";

type Role = "user" | "assistant";

type Attachment = {
  id: string;
  name: string;
  type: string;
  size: number;
  preview: string;
};

type ConversationMessage = {
  id: string;
  role: Role;
  name: string;
  avatarFallback: string;
  avatarUrl?: string;
  content: string;
  markdown?: boolean;
  attachments?: Attachment[];
  reaction?: "upvote" | "downvote" | null;
};

type MessageTemplate = Omit<ConversationMessage, "id" | "attachments" | "reaction">;

type HistoryConversation = {
  id: string;
  title: string;
  preview: string;
  timestamp: string;
};

type HistoryGroup = {
  label: string;
  conversations: HistoryConversation[];
};

type ProviderOption = {
  id: string;
  label: string;
  models: { id: string; label: string }[];
};

const providers: ProviderOption[] = [
  {
    id: "openai",
    label: "OpenAI",
    models: [
      { id: "gpt-4o", label: "GPT-4o" },
      { id: "gpt-4o-mini", label: "GPT-4o mini" },
      { id: "o3-mini", label: "O3 mini" },
    ],
  },
  {
    id: "anthropic",
    label: "Anthropic",
    models: [
      { id: "claude-3.7-sonnet", label: "Claude 3.7 Sonnet" },
      { id: "claude-3.5-haiku", label: "Claude 3.5 Haiku" },
    ],
  },
  {
    id: "google",
    label: "Google Gemini",
    models: [
      { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
      { id: "gemini-1.5-pro", label: "Gemini 1.5 Pro" },
    ],
  },
  {
    id: "groq",
    label: "Groq",
    models: [
      { id: "llama-3.1-70b", label: "Llama 3.1 70B" },
      { id: "mixtral-8x7b", label: "Mixtral 8x7B" },
    ],
  },
];

const historySeed: HistoryGroup[] = [
  {
    label: "Hoy",
    conversations: [
      {
        id: "today-1",
        title: "Preparación de lanzamiento",
        preview: "Borrador de anuncio y lista de verificación QA para beta.",
        timestamp: "Hace 2h",
      },
      {
        id: "today-2",
        title: "Encuesta de onboarding",
        preview: "Preguntas para capturar fricción y señales de éxito en la primera semana.",
        timestamp: "Hace 4h",
      },
      {
        id: "today-3",
        title: "Notas de crítica de diseño",
        preview: "Hilos de feedback resumidos y agrupados por prioridad/responsable.",
        timestamp: "Hace 6h",
      },
    ],
  },
  {
    label: "Esta semana",
    conversations: [
      {
        id: "week-1",
        title: "Ideas de triaje de soporte",
        preview: "Macros generados para los principales problemas de la semana.",
        timestamp: "Hace 3 días",
      },
      {
        id: "week-2",
        title: "Documento de experimento de crecimiento",
        preview: "Hipótesis, métricas de control y cadencia de implementación.",
        timestamp: "Hace 5 días",
      },
    ],
  },
];

function createId() {
  return Math.random().toString(36).slice(2, 10);
}

const STORAGE_PREFIX = "chatbot:";

function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function saveJson(key: string, value: unknown) {
  try {
    localStorage.setItem(STORAGE_PREFIX + key, JSON.stringify(value));
  } catch { /* ignore quota errors */ }
}

const messageTemplates: MessageTemplate[] = [
  {
    role: "assistant",
    name: "Nova",
    avatarFallback: "NO",
    content:
      "¡Hola! Soy Nova, un asistente impulsado por prompt-kit. Pregúntame sobre tus ideas de producto, preguntas técnicas o tareas de investigación y trazaré un plan que puedes conectar a tu modelo favorito.",
  },
  {
    role: "user",
    name: "Tú",
    avatarFallback: "TÚ",
    content: "Creemos un esquema de entrevista de usuario que explore la motivación y los problemas del flujo de trabajo.",
  },
  {
    role: "assistant",
    name: "Nova",
    avatarFallback: "NO",
    markdown: true,
    content: [
      "Claro — aquí tienes un esquema estructurado que puedes usar:",
      "",
      "### Esquema de Entrevista",
      "1. **Calentamiento** — \"¿Puedes contarme sobre tu rol y responsabilidades diarias?\"",
      "2. **Motivación** — \"¿Qué te hizo empezar a usar [producto/flujo de trabajo]?\"",
      "3. **Proceso actual** — \"Guíame a través de tu último intento paso a paso.\"",
      "4. **Puntos débiles** — \"¿Dónde se siente lento, confuso o frágil?\"",
      "5. **Resultados deseados** — \"Si esto fuera sencillo, ¿qué desbloquearía para ti?\"",
      "",
      "¡Feliz de personalizar esto si compartes la audiencia o el caso de uso!",
    ].join("\n"),
  },
];

function createInitialMessages(): ConversationMessage[] {
  return messageTemplates.map((template) => ({
    ...template,
    id: createId(),
    attachments: template.role === "user" ? [] : undefined,
    reaction: null,
  }));
}

function updateConversationInGroups(
  groups: HistoryGroup[],
  conversationId: string,
  updater: (existing: HistoryConversation) => HistoryConversation,
): HistoryGroup[] {
  const next = cloneHistoryGroups(groups);
  for (const section of next) {
    const index = section.conversations.findIndex((c) => c.id === conversationId);
    if (index !== -1) {
      const existing = section.conversations[index];
      section.conversations[index] = updater(existing);
      break;
    }
  }
  return next;
}

function createPlaceholderConversation(title: string, preview: string): ConversationMessage[] {
  return [
    {
      id: createId(),
      role: "assistant",
      name: "Nova",
      avatarFallback: "NO",
      markdown: true,
      reaction: null,
      content: [
        `Esta es una vista provisional para **${title}**.`,
        "",
        preview,
        "",
        "Carga mensajes reales aquí persistiendo las conversaciones y restaurándolas cuando el usuario abre el hilo.",
      ].join("\n"),
    },
  ];
}

function cloneHistoryGroups(groups: HistoryGroup[]): HistoryGroup[] {
  return groups.map((section) => ({
    label: section.label,
    conversations: section.conversations.map((conversation) => ({ ...conversation })),
  }));
}

function buildInitialConversationMap(groups: HistoryGroup[]): Record<string, ConversationMessage[]> {
  const map: Record<string, ConversationMessage[]> = {};
  const primaryId = groups[0]?.conversations[0]?.id;

  groups.forEach((section) => {
    section.conversations.forEach((conversation) => {
      if (conversation.id === primaryId) {
        map[conversation.id] = createInitialMessages();
      } else {
        map[conversation.id] = createPlaceholderConversation(conversation.title, conversation.preview);
      }
    });
  });

  return map;
}

function findConversationTitle(groups: HistoryGroup[], conversationId: string): string {
  for (const section of groups) {
    const conversation = section.conversations.find((entry) => entry.id === conversationId);
    if (conversation) {
      return conversation.title;
    }
  }
  return "Chat sin título";
}

function truncateText(text: string, limit = 80): string {
  if (text.length <= limit) return text;
  return `${text.slice(0, limit)}…`;
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function promoteConversation(
  groups: HistoryGroup[],
  conversationId: string,
  updater: (existing: HistoryConversation | null) => HistoryConversation,
): HistoryGroup[] {
  const next = cloneHistoryGroups(groups);
  let existing: HistoryConversation | null = null;

  for (const section of next) {
    const index = section.conversations.findIndex((conversation) => conversation.id === conversationId);
    if (index !== -1) {
      existing = section.conversations.splice(index, 1)[0];
      break;
    }
  }

  const updated = updater(existing);

  if (next.length === 0) {
    next.push({ label: "Today", conversations: [] });
  }

  next[0].conversations = [
    updated,
    ...next[0].conversations.filter((conversation) => conversation.id !== updated.id),
  ];

  return next;
}

function Chatbot() {
  const [historyGroups, setHistoryGroups] = useState<HistoryGroup[]>(() => {
    const stored = loadJson<HistoryGroup[] | null>("history", null);
    return stored ?? cloneHistoryGroups(historySeed);
  });
  const [conversations, setConversations] = useState<Record<string, ConversationMessage[]>>(() => {
    const stored = loadJson<Record<string, ConversationMessage[]> | null>("conversations", null);
    return stored ?? buildInitialConversationMap(historySeed);
  });
  const [activeConversationId, setActiveConversationId] = useState(() => {
    const stored = loadJson<string | null>("activeId", null);
    return stored ?? historySeed[0]?.conversations[0]?.id ?? createId();
  });
  const [chatCounter, setChatCounter] = useState(() => {
    const stored = loadJson<number | null>("counter", null);
    return stored ?? historySeed.reduce((total, section) => total + section.conversations.length, 0) + 1;
  });
  const [composerAttachments, setComposerAttachments] = useState<Attachment[]>([]);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedProviderId, setSelectedProviderId] = useState(providers[0].id);
  const [selectedModelId, setSelectedModelId] = useState(providers[0].models[0].id);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isProviderMenuOpen, setIsProviderMenuOpen] = useState(false);
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);

  const activeConversationTitle = useMemo(
    () => findConversationTitle(historyGroups, activeConversationId),
    [historyGroups, activeConversationId],
  );

  const activeProvider =
    providers.find((provider) => provider.id === selectedProviderId) ?? providers[0];
  const activeModel =
    activeProvider.models.find((model) => model.id === selectedModelId) ?? activeProvider.models[0];

  const messages = useMemo(
    () => conversations[activeConversationId] ?? [],
    [conversations, activeConversationId],
  );

  const hasPendingInput = input.trim().length > 0 || composerAttachments.length > 0;
  const streamingContentRef = useRef("");
  const lastStreamUpdateRef = useRef(0);

  useEffect(() => {
    saveJson("history", historyGroups);
  }, [historyGroups]);

  useEffect(() => {
    saveJson("conversations", conversations);
  }, [conversations]);

  useEffect(() => {
    saveJson("activeId", activeConversationId);
  }, [activeConversationId]);

  useEffect(() => {
    saveJson("counter", chatCounter);
  }, [chatCounter]);

  useEffect(() => {
    const provider =
      providers.find((item) => item.id === selectedProviderId) ?? providers[0];
    setSelectedModelId((current) =>
      provider.models.some((model) => model.id === current) ? current : provider.models[0].id,
    );
  }, [selectedProviderId]);

  const updateConversationMessages = (
    conversationId: string,
    updater: (current: ConversationMessage[]) => ConversationMessage[],
  ) => {
    setConversations((previous) => {
      const current = previous[conversationId] ?? [];
      const updated = updater(current);
      return { ...previous, [conversationId]: updated };
    });
  };

  const refreshHistoryPreview = (conversationId: string, preview: string, title?: string) => {
    setHistoryGroups((previous) =>
      updateConversationInGroups(previous, conversationId, (existing) => ({
        id: existing.id,
        title: title ?? existing.title,
        preview: truncateText(preview),
        timestamp: "Just now",
      })),
    );
  };

  const addAttachmentFromFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result !== "string") return;
      setComposerAttachments((previous) => [
        ...previous,
        {
          id: createId(),
          name: file.name || `pasted-image-${previous.length + 1}.png`,
          type: file.type,
          size: file.size,
          preview: reader.result,
        },
      ]);
    };
    reader.readAsDataURL(file);
  };

  const handlePasteImages = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = Array.from(event.clipboardData?.files ?? []).filter((file) =>
      file.type.startsWith("image/"),
    );
    if (files.length === 0) return;

    event.preventDefault();
    files.forEach(addAttachmentFromFile);
  };

  const handleImageUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []).filter((file) =>
      file.type.startsWith("image/"),
    );
    if (files.length === 0) return;

    files.forEach(addAttachmentFromFile);
    event.target.value = "";
  };

  const handleRemoveAttachment = (attachmentId: string) => {
    setComposerAttachments((previous) =>
      previous.filter((attachment) => attachment.id !== attachmentId),
    );
  };

  const handleCopy = async (message: ConversationMessage) => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopiedMessageId(message.id);
      window.setTimeout(() => {
        setCopiedMessageId((current) => (current === message.id ? null : current));
      }, 2000);
    } catch {
      setCopiedMessageId(null);
    }
  };

  const toggleReaction = (messageId: string, reaction: "upvote" | "downvote") => {
    const conversationId = activeConversationId;
    updateConversationMessages(conversationId, (current) =>
      current.map((message) =>
        message.id === messageId
          ? {
              ...message,
              reaction: message.reaction === reaction ? null : reaction,
            }
          : message,
      ),
    );
  };

  const handleSubmit = async () => {
    if (!hasPendingInput || isGenerating) return;

    const conversationId = activeConversationId;
    const conversationTitle = activeConversationTitle.startsWith("Chat sin título") && input.trim()
      ? truncateText(input.trim(), 40)
      : activeConversationTitle;
    const prompt = input.trim();
    const attachments = composerAttachments.map((attachment) => ({ ...attachment }));
    const attachmentsSummary =
      attachments.length > 0
        ? `Compartió ${attachments.length} archivo${attachments.length > 1 ? "s" : ""}`
        : undefined;

    const userContent =
      prompt || attachmentsSummary || "Envió un mensaje";

    const userMessage: ConversationMessage = {
      id: createId(),
      role: "user",
      name: "Tú",
      avatarFallback: "YO",
      content: userContent,
      attachments: attachments.length ? attachments : undefined,
      reaction: null,
    };

    const assistantId = createId();
    const assistantMessage: ConversationMessage = {
      id: assistantId,
      role: "assistant",
      name: "Nova",
      avatarFallback: "NO",
      markdown: true,
      reaction: null,
      content: "",
    };

    const currentMessages = conversations[conversationId] ?? [];
    const apiMessages = [
      ...currentMessages.map((m) => ({ role: m.role, content: m.content })),
      { role: "user" as const, content: userContent },
    ];

    updateConversationMessages(conversationId, (current) => [...current, userMessage]);
    refreshHistoryPreview(
      conversationId,
      prompt || attachmentsSummary || "Envió un mensaje",
      conversationTitle,
    );

    setComposerAttachments([]);
    setInput("");
    setCopiedMessageId(null);
    setIsGenerating(true);
    streamingContentRef.current = "";
    lastStreamUpdateRef.current = 0;

    updateConversationMessages(conversationId, (current) => [...current, assistantMessage]);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: apiMessages,
          provider: selectedProviderId,
          model: selectedModelId,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ error: "Error desconocido" }));
        updateConversationMessages(conversationId, (current) =>
          current.map((m) =>
            m.id === assistantId ? { ...m, content: `**Error:** ${errData.error}` } : m,
          ),
        );
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        updateConversationMessages(conversationId, (current) =>
          current.map((m) =>
            m.id === assistantId ? { ...m, content: "**Error:** No se pudo leer la respuesta" } : m,
          ),
        );
        return;
      }

      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        streamingContentRef.current += decoder.decode(value, { stream: true });
        const now = Date.now();
        if (now - lastStreamUpdateRef.current > 50) {
          lastStreamUpdateRef.current = now;
          updateConversationMessages(conversationId, (current) =>
            current.map((m) =>
              m.id === assistantId ? { ...m, content: streamingContentRef.current } : m,
            ),
          );
        }
      }

      updateConversationMessages(conversationId, (current) =>
        current.map((m) =>
          m.id === assistantId ? { ...m, content: streamingContentRef.current } : m,
        ),
      );

      refreshHistoryPreview(conversationId, streamingContentRef.current, conversationTitle);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Error de conexión";
      updateConversationMessages(conversationId, (current) =>
        current.map((m) =>
          m.id === assistantId
            ? { ...m, content: `**Error de conexión:** ${errorMsg}` }
            : m,
        ),
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleNewChat = () => {
    const conversationId = createId();
    const conversationTitle = `Chat sin título ${chatCounter}`;

    setChatCounter((count) => count + 1);
    setConversations((previous) => ({
      ...previous,
      [conversationId]: [],
    }));
    setActiveConversationId(conversationId);
    setComposerAttachments([]);
    setInput("");
    setCopiedMessageId(null);
    setIsGenerating(false);
    setIsSidebarOpen(false);

    setHistoryGroups((previous) => {
      const next = cloneHistoryGroups(previous);
      if (next.length === 0) {
        next.push({ label: "Today", conversations: [] });
      }
      next[0].conversations = [
        {
          id: conversationId,
          title: conversationTitle,
          preview: "Saluda a Nova para comenzar.",
          timestamp: "Just now",
        },
        ...next[0].conversations,
      ];
      return next;
    });
  };

  const handleSelectConversation = (conversation: HistoryConversation) => {
    setActiveConversationId(conversation.id);
    setIsSidebarOpen(false);
    setComposerAttachments([]);
    setInput("");
    setCopiedMessageId(null);
    setIsGenerating(false);

    setConversations((previous) => {
      if (previous[conversation.id]) {
        return previous;
      }

      return {
        ...previous,
        [conversation.id]: createPlaceholderConversation(
          conversation.title,
          conversation.preview,
        ),
      };
    });

    setHistoryGroups((previous) =>
      updateConversationInGroups(previous, conversation.id, (existing) => existing ?? { ...conversation }),
    );
  };

  const activeHistoryGroups = historyGroups;

  return (
    <div className="relative flex h-full overflow-hidden bg-background text-foreground">
      <div
        className={cn(
          "fixed inset-0 z-20 bg-black/40 backdrop-blur-sm lg:hidden transition-opacity duration-300",
          isSidebarOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none",
        )}
        onClick={() => setIsSidebarOpen(false)}
        aria-hidden="true"
      />

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 flex w-72 flex-col border-r border-border bg-card shadow-xl transition-transform duration-300 ease-in-out",
          isSidebarOpen ? "translate-x-0" : "-translate-x-full",
          "lg:static lg:h-full lg:shadow-none",
          isSidebarCollapsed ? "lg:hidden" : "lg:flex lg:translate-x-0",
        )}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-4">
          <div>
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
                Historial
              </p>
              <p className="text-sm font-medium text-foreground">Chats recientes</p>
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle className="lg:hidden" />
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setIsSidebarOpen(false)}
              aria-label="Cerrar historial"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <div className="border-b border-border px-4 pb-4 pt-3">
          <Button variant="outline" size="sm" className="w-full" onClick={handleNewChat}>
            <Plus className="h-4 w-4" />
            <span className="ml-2">Nuevo chat</span>
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto pb-6">
          {activeHistoryGroups.map((section) => (
            <div key={section.label} className="px-4 pt-6">
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
                {section.label}
              </p>
              <div className="mt-3 space-y-2">
                {section.conversations.map((conversation) => {
                  const isActive = conversation.id === activeConversationId;
                  return (
                    <button
                      key={conversation.id}
                      type="button"
                      className={cn(
                        "w-full rounded-xl border border-transparent bg-transparent px-3 py-2 text-left transition hover:border-border hover:bg-accent/40",
                        isActive && "border-border bg-accent/40",
                      )}
                      onClick={() => handleSelectConversation(conversation)}
                    >
                      <div className="flex items-center justify-between text-sm font-medium text-foreground">
                        <span className="truncate">{conversation.title}</span>
                        <span className="ml-2 shrink-0 text-xs text-muted-foreground">
                          {conversation.timestamp}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {conversation.preview}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </aside>

      <main className="flex h-full flex-1 flex-col overflow-hidden">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-4 sm:px-8">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                onClick={() => setIsSidebarOpen(true)}
                aria-label="Abrir historial"
              >
                <Menu className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="hidden lg:inline-flex"
                onClick={() => setIsSidebarCollapsed((v) => !v)}
                aria-label={isSidebarCollapsed ? "Mostrar panel" : "Ocultar panel"}
              >
                {isSidebarCollapsed ? (
                  <PanelLeftOpen className="h-4 w-4" />
                ) : (
                  <PanelLeftClose className="h-4 w-4" />
                )}
              </Button>
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
                Nova
              </p>
              <h1 className="truncate text-lg font-semibold text-foreground sm:text-xl">
                {activeConversationTitle}
              </h1>
              <p className="text-xs text-muted-foreground">
                {activeProvider.label} · {activeModel.label}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ThemeToggle className="hidden lg:inline-flex" />
          </div>
        </header>

        <div className="flex flex-1 flex-col overflow-hidden px-4 pb-6 pt-4 sm:px-8">
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <ChatContainerRoot className="relative flex min-h-0 flex-1 flex-col rounded-2xl border border-border bg-card/80 p-4 shadow-sm backdrop-blur-sm sm:p-6">
              <ChatContainerContent className="flex w-full flex-col gap-6">
                {messages.map((message, index) => {
                  const isUser = message.role === "user";
                  const isLatestAssistant = !isUser && index === messages.length - 1;

                  return (
                    <Message
                      key={message.id}
                      className={cn(isUser ? "justify-end" : "justify-start")}
                      aria-live="polite"
                    >
                      <div className={cn("flex max-w-[38rem] flex-col gap-2", isUser ? "items-end" : "items-start")}>
                        <span className="text-xs font-semibold uppercase tracking-[0.28em] text-muted-foreground">
                          {message.name}
                        </span>
                        <div className="group flex w-full flex-col gap-2">
                          <MessageContent
                            markdown={message.markdown}
                            className={cn(
                              "rounded-3xl px-5 py-3 text-sm leading-6 shadow-sm transition-colors text-left",
                              isUser
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted text-foreground prose-headings:mt-0 prose-headings:font-semibold prose-p:mt-2",
                            )}
                          >
                            {message.content}
                          </MessageContent>

                          {message.attachments && message.attachments.length > 0 ? (
                            <div className="mt-2 grid gap-3 sm:grid-cols-2">
                              {message.attachments.map((attachment) => (
                                <figure
                                  key={attachment.id}
                                  className="overflow-hidden rounded-xl border border-border bg-background/40"
                                >
                                  <img
                                    src={attachment.preview}
                                    alt={attachment.name}
                                    className="h-32 w-full object-cover"
                                  />
                                  <figcaption className="flex items-center justify-between truncate px-3 py-2 text-xs text-muted-foreground">
                                    <span className="truncate">{attachment.name}</span>
                                    <span className="shrink-0 pl-2">
                                      {formatFileSize(attachment.size)}
                                    </span>
                                  </figcaption>
                                </figure>
                              ))}
                            </div>
                          ) : null}

                          {!isUser ? (
                            <MessageActions
                              className={cn(
                                "-ml-1.5 flex gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100",
                                isLatestAssistant && "opacity-100",
                              )}
                            >
                              <MessageAction
                                tooltip={copiedMessageId === message.id ? "Copiado" : "Copiar mensaje"}
                                delayDuration={100}
                              >
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className={cn(
                                    "rounded-full",
                                    copiedMessageId === message.id && "bg-emerald-500/10 text-emerald-400",
                                  )}
                                  onClick={(event) => {
                                    event.preventDefault();
                                    event.stopPropagation();
                                    handleCopy(message);
                                  }}
                                  aria-label={copiedMessageId === message.id ? "Mensaje copiado" : "Copiar mensaje"}
                                >
                                  {copiedMessageId === message.id ? (
                                    <Check className="h-4 w-4" />
                                  ) : (
                                    <Copy className="h-4 w-4" />
                                  )}
                                </Button>
                              </MessageAction>
                              <MessageAction
                                tooltip={
                                  message.reaction === "upvote" ? "Quitar like" : "Marcar como útil"
                                }
                                delayDuration={100}
                              >
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className={cn(
                                    "rounded-full",
                                    message.reaction === "upvote" && "bg-primary/10 text-primary",
                                  )}
                                  onClick={(event) => {
                                    event.preventDefault();
                                    event.stopPropagation();
                                    toggleReaction(message.id, "upvote");
                                  }}
                                  aria-pressed={message.reaction === "upvote"}
                                  aria-label="Marcar como útil"
                                >
                                  <ThumbsUp className="h-4 w-4" />
                                </Button>
                              </MessageAction>
                              <MessageAction
                                tooltip={
                                  message.reaction === "downvote" ? "Quitar dislike" : "Marcar como no útil"
                                }
                                delayDuration={100}
                              >
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className={cn(
                                    "rounded-full",
                                    message.reaction === "downvote" && "bg-destructive/10 text-destructive",
                                  )}
                                  onClick={(event) => {
                                    event.preventDefault();
                                    event.stopPropagation();
                                    toggleReaction(message.id, "downvote");
                                  }}
                                  aria-pressed={message.reaction === "downvote"}
                                  aria-label="Marcar como no útil"
                                >
                                  <ThumbsDown className="h-4 w-4" />
                                </Button>
                              </MessageAction>
                            </MessageActions>
                          ) : null}
                        </div>
                      </div>
                    </Message>
                  );
                })}
                <ChatContainerScrollAnchor />
              </ChatContainerContent>

              <div className="pointer-events-none absolute bottom-4 right-4">
                <ScrollButton className="pointer-events-auto shadow-md" />
              </div>
            </ChatContainerRoot>
          </div>

          <PromptInput
            value={input}
            onValueChange={setInput}
            onSubmit={handleSubmit}
            isLoading={isGenerating}
            className="mt-6 mb-4 border-border/90 bg-card/80 backdrop-blur"
            disabled={isGenerating}
          >
            <div className="flex flex-col gap-3">
              {composerAttachments.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
                    Archivos adjuntos
                  </p>
                  <div className="flex flex-wrap gap-3">
                    {composerAttachments.map((attachment) => (
                      <div
                        key={attachment.id}
                        className="relative h-24 w-24 overflow-hidden rounded-xl border border-border bg-muted/40"
                      >
                        <img
                          src={attachment.preview}
                          alt={attachment.name}
                          className="h-full w-full object-cover"
                        />
                        <button
                          type="button"
                          className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-black/70 text-white transition hover:bg-black"
                          onClick={(event) => {
                            event.preventDefault();
                            event.stopPropagation();
                            handleRemoveAttachment(attachment.id);
                          }}
                          aria-label={`Eliminar ${attachment.name}`}
                        >
                          <X className="h-3 w-3" />
                        </button>
                        <div className="absolute inset-x-0 bottom-0 bg-black/60 px-2 py-1 text-[10px] text-white">
                          <span className="block truncate">{attachment.name}</span>
                          <span className="opacity-70">{formatFileSize(attachment.size)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <PromptInputTextarea
                aria-label="Mensaje"
                placeholder="Mensaje"
                onPaste={handlePasteImages}
              />

              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <PromptInputAction tooltip="Pegar o subir una imagen" side="top">
                    <Button asChild variant="ghost" size="icon" className="rounded-full">
                      <label className="flex cursor-pointer items-center justify-center">
                        <Image className="h-5 w-5" />
                        <span className="sr-only">Adjuntar imagen</span>
                        <input
                          type="file"
                          accept="image/*"
                          multiple
                          className="sr-only"
                          onChange={handleImageUpload}
                        />
                      </label>
                    </Button>
                  </PromptInputAction>

                  <div className="relative">
                    <PromptInputAction tooltip="Seleccionar proveedor" side="top">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="rounded-full"
                        aria-haspopup="listbox"
                        aria-expanded={isProviderMenuOpen}
                        onClick={() => {
                          setIsProviderMenuOpen((v) => !v);
                          setIsModelMenuOpen(false);
                        }}
                      >
                        <Boxes className="h-5 w-5" />
                      </Button>
                    </PromptInputAction>
                    {isProviderMenuOpen ? (
                      <div className="absolute bottom-10 left-0 z-10 w-44 rounded-lg border border-border bg-card p-1 shadow-md">
                        {providers.map((provider) => (
                          <button
                            key={provider.id}
                            type="button"
                            className={cn(
                              "flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-accent/60",
                              selectedProviderId === provider.id && "bg-accent/40",
                            )}
                            role="option"
                            aria-selected={selectedProviderId === provider.id}
                            onClick={() => {
                              setSelectedProviderId(provider.id);
                              setIsProviderMenuOpen(false);
                            }}
                          >
                            <span className="truncate">{provider.label}</span>
                            {selectedProviderId === provider.id ? <Check className="h-4 w-4" /> : null}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div className="relative">
                    <PromptInputAction tooltip="Seleccionar modelo" side="top">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="rounded-full"
                        aria-haspopup="listbox"
                        aria-expanded={isModelMenuOpen}
                        onClick={() => {
                          setIsModelMenuOpen((v) => !v);
                          setIsProviderMenuOpen(false);
                        }}
                      >
                        <Cpu className="h-5 w-5" />
                      </Button>
                    </PromptInputAction>
                    {isModelMenuOpen ? (
                      <div className="absolute bottom-10 left-0 z-10 w-44 rounded-lg border border-border bg-card p-1 shadow-md">
                        {activeProvider.models.map((model) => (
                          <button
                            key={model.id}
                            type="button"
                            className={cn(
                              "flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-accent/60",
                              selectedModelId === model.id && "bg-accent/40",
                            )}
                            role="option"
                            aria-selected={selectedModelId === model.id}
                            onClick={() => {
                              setSelectedModelId(model.id);
                              setIsModelMenuOpen(false);
                            }}
                          >
                            <span className="truncate">{model.label}</span>
                            {selectedModelId === model.id ? <Check className="h-4 w-4" /> : null}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
                <PromptInputActions>
                  <PromptInputAction tooltip="Enviar mensaje" delayDuration={100}>
                    <Button
                      type="button"
                      size="icon"
                      className="rounded-full"
                      onClick={handleSubmit}
                      disabled={!hasPendingInput || isGenerating}
                    >
                      <ArrowUp className="h-4 w-4" />
                    </Button>
                  </PromptInputAction>
                </PromptInputActions>
              </div>
            </div>
          </PromptInput>
        </div>
      </main>
    </div>
  );
}

export default Chatbot;
