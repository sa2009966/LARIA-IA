import { clearSession, getToken } from "./auth-store";
import {
  LariaApiError,
  type AnalysisResult,
  type DocumentItem,
  type LearningHistory,
  type QuizAttemptResult,
  type QuizPublic,
  type QuestionResponse,
  type StudentProfile,
  type TokenResponse,
  type User,
} from "./laria-types";

function apiBase(): string {
  const raw = import.meta.env.PUBLIC_LARIA_API_URL as string | undefined;
  if (!raw || !raw.trim()) {
    throw new LariaApiError(
      0,
      "PUBLIC_LARIA_API_URL no configurada. Define la URL del backend en .env",
    );
  }
  return raw.replace(/\/$/, "");
}

function v1(path: string): string {
  return `${apiBase()}/api/v1${path}`;
}

async function parseDetail(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail
        .map((d: { msg?: string }) => d.msg)
        .filter(Boolean)
        .join("; ");
    }
    if (typeof data?.error === "string") return data.error;
    return res.statusText || "Error de API";
  } catch {
    return res.statusText || "Error de API";
  }
}

type RequestOptions = {
  method?: string;
  body?: BodyInit | null;
  auth?: boolean;
  headers?: Record<string, string>;
  form?: boolean;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body = null, auth = true, headers = {}, form = false } = options;
  const finalHeaders: Record<string, string> = { ...headers };

  if (auth) {
    const token = getToken();
    if (!token) {
      throw new LariaApiError(401, "Sesión no iniciada");
    }
    finalHeaders.Authorization = `Bearer ${token}`;
  }

  if (body && !form && !(body instanceof FormData)) {
    finalHeaders["Content-Type"] = finalHeaders["Content-Type"] ?? "application/json";
  }

  let res: Response;
  try {
    res = await fetch(v1(path), { method, headers: finalHeaders, body });
  } catch {
    throw new LariaApiError(
      0,
      "No se pudo conectar con el backend. Revisa PUBLIC_LARIA_API_URL y CORS.",
    );
  }

  if (res.status === 401 && auth) {
    clearSession();
    throw new LariaApiError(401, "Sesión expirada. Vuelve a iniciar sesión.");
  }

  if (res.status === 204) {
    return undefined as T;
  }

  if (!res.ok) {
    throw new LariaApiError(res.status, await parseDetail(res));
  }

  return (await res.json()) as T;
}

export async function registerUser(input: {
  username: string;
  email: string;
  password: string;
}): Promise<User> {
  return request<User>("/auth/register", {
    method: "POST",
    auth: false,
    body: JSON.stringify(input),
  });
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);
  return request<TokenResponse>("/auth/token", {
    method: "POST",
    auth: false,
    form: true,
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
}

export async function getMe(): Promise<User> {
  return request<User>("/users/me");
}

export async function listDocuments(): Promise<DocumentItem[]> {
  return request<DocumentItem[]>("/documents/");
}

export async function getDocument(id: string): Promise<DocumentItem> {
  return request<DocumentItem>(`/documents/${id}`);
}

export async function uploadDocument(input: {
  filename: string;
  content: string;
  subject: string;
}): Promise<DocumentItem> {
  return request<DocumentItem>("/documents/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function deleteDocument(id: string): Promise<void> {
  return request<void>(`/documents/${id}`, { method: "DELETE" });
}

export async function analyzeDocument(
  id: string,
  forceRefresh = false,
): Promise<AnalysisResult> {
  const q = forceRefresh ? "?force_refresh=true" : "";
  return request<AnalysisResult>(`/documents/${id}/analyze${q}`, { method: "POST" });
}

export async function askDocument(id: string, question: string): Promise<QuestionResponse> {
  return request<QuestionResponse>(`/documents/${id}/ask`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export async function generateQuiz(id: string, numQuestions = 5): Promise<QuizPublic> {
  return request<QuizPublic>(
    `/documents/${id}/quiz?num_questions=${encodeURIComponent(String(numQuestions))}`,
    { method: "POST" },
  );
}

export async function getQuiz(quizId: string): Promise<QuizPublic> {
  return request<QuizPublic>(`/quizzes/${quizId}`);
}

export async function submitQuizAttempt(
  quizId: string,
  answers: Record<string, string>,
): Promise<QuizAttemptResult> {
  return request<QuizAttemptResult>(`/quizzes/${quizId}/attempts`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

export async function getLearningHistory(): Promise<LearningHistory> {
  return request<LearningHistory>("/learning/me");
}

export async function getStudentProfile(): Promise<StudentProfile> {
  return request<StudentProfile>("/learning/me/profile");
}
