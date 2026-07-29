export type User = {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type DocumentItem = {
  id: string;
  owner_id: string;
  filename: string;
  subject: string;
  status: string;
  uploaded_at: string;
  has_analysis: boolean;
  error_message?: string | null;
};

export type AnalysisResult = {
  summary: string;
  key_concepts: string[];
  suggested_questions: string[];
};

export type QuestionResponse = {
  answer: string;
};

export type QuizQuestion = {
  index: number;
  text: string;
  options: Record<string, string>;
  difficulty: string;
};

export type QuizPublic = {
  id: string;
  document_id: string;
  questions: QuizQuestion[];
  total_points: number;
  created_at: string;
};

export type QuizAttemptResult = {
  attempt_id: string;
  quiz_id: string;
  document_id: string;
  score: number;
  total_points: number;
  questions: {
    index: number;
    text: string;
    selected: string | null;
    correct_answer: string;
    is_correct: boolean;
  }[];
  completed_at: string;
};

export type TutorInteraction = {
  id: string;
  document_id: string;
  question: string;
  answer: string;
  asked_at: string;
};

export type LearningRecommendation = {
  kind: string;
  message: string;
  document_id?: string | null;
  concept?: string | null;
  priority: number;
  suggested_minutes?: number | null;
};

export type LearningHistory = {
  attempts: {
    attempt_id: string;
    quiz_id: string;
    document_id: string;
    score: number;
    total_points: number;
    completed_at: string;
  }[];
  tutor_interactions: TutorInteraction[];
  recommendations: LearningRecommendation[];
};

export type ConceptMastery = {
  concept_key: string;
  attempts: number;
  mastery: number;
  last_score_ratio: number;
  effective_mastery: number;
  confidence: number;
  last_practiced_at?: string | null;
  subject?: string | null;
  help_requests: number;
  error_streak: number;
};

export type StudentProfile = {
  student_id: string;
  pace: string;
  total_attempts: number;
  frequent_errors: string[];
  updated_at: string;
  mastery_by_document: {
    document_id: string;
    attempts: number;
    mastery: number;
    last_score_ratio: number;
    struggle_signals: number;
  }[];
  mastery_by_concept: ConceptMastery[];
  total_struggle_signals: number;
  learning_velocity: number;
  pedagogical_memory?: {
    frequent_misconceptions: string[];
    successful_examples: string[];
    successful_analogies: string[];
    preferred_explanation_style: string;
    last_effective_strategies: string[];
  } | null;
};

export const SUBJECTS = [
  "Matemática",
  "Ciencias",
  "Física",
  "Química",
  "Biología",
  "Historia",
  "Geografía",
  "Lengua",
  "Literatura",
  "Filosofía",
  "Inglés",
  "Educación Física",
  "Artística",
] as const;

export class LariaApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "LariaApiError";
    this.status = status;
    this.detail = detail;
  }
}
