import type { User } from "./laria-types";

type AuthListener = () => void;

type AuthState = {
  token: string | null;
  user: User | null;
};

/** Session only in process memory — never browser Web Storage APIs. */
let state: AuthState = { token: null, user: null };
const listeners = new Set<AuthListener>();

export function getToken(): string | null {
  return state.token;
}

export function getUser(): User | null {
  return state.user;
}

export function isAuthenticated(): boolean {
  return Boolean(state.token);
}

export function setSession(token: string, user: User | null = null): void {
  state = { token, user };
  listeners.forEach((l) => l());
}

export function setUser(user: User): void {
  state = { ...state, user };
  listeners.forEach((l) => l());
}

export function clearSession(): void {
  state = { token: null, user: null };
  listeners.forEach((l) => l());
}

export function subscribeAuth(listener: AuthListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getAuthSnapshot(): AuthState {
  return state;
}
