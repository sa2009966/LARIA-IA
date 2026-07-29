import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { login, getMe, registerUser } from "@/lib/laria-api";
import { setSession } from "@/lib/auth-store";
import { LariaApiError } from "@/lib/laria-types";

type Props = {
  onSuccess: () => void;
  onSwitchToRegister: () => void;
};

export function LoginForm({ onSuccess, onSwitchToRegister }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const token = await login(email.trim(), password);
      setSession(token.access_token);
      const user = await getMe();
      setSession(token.access_token, user);
      onSuccess();
    } catch (err) {
      setError(err instanceof LariaApiError ? err.detail : "No se pudo iniciar sesión");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mx-auto w-full max-w-md space-y-4 animate-panel-fade">
      <div>
        <h2 className="font-display text-3xl text-ink">Entrar</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Continúa con tu cuenta de estudiante LARIA.
        </p>
      </div>
      <label className="block space-y-1.5 text-sm">
        <span className="font-medium">Email</span>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-lg border border-border bg-card px-3 py-2 outline-none ring-ring focus:ring-2"
          autoComplete="email"
        />
      </label>
      <label className="block space-y-1.5 text-sm">
        <span className="font-medium">Contraseña</span>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded-lg border border-border bg-card px-3 py-2 outline-none ring-ring focus:ring-2"
          autoComplete="current-password"
        />
      </label>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <Button type="submit" className="w-full bg-ink hover:bg-ink/90" disabled={loading}>
        {loading ? "Entrando…" : "Entrar"}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        ¿Sin cuenta?{" "}
        <button type="button" className="text-accent underline-offset-2 hover:underline" onClick={onSwitchToRegister}>
          Regístrate
        </button>
      </p>
    </form>
  );
}

type RegisterProps = {
  onSuccess: () => void;
  onSwitchToLogin: () => void;
};

export function RegisterForm({ onSuccess, onSwitchToLogin }: RegisterProps) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 12) {
      setError("La contraseña debe tener al menos 12 caracteres.");
      return;
    }
    if (!/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/\d/.test(password)) {
      setError("Usa mayúsculas, minúsculas y al menos un dígito.");
      return;
    }
    setLoading(true);
    try {
      await registerUser({ username: username.trim(), email: email.trim(), password });
      const token = await login(email.trim(), password);
      setSession(token.access_token);
      const user = await getMe();
      setSession(token.access_token, user);
      onSuccess();
    } catch (err) {
      setError(err instanceof LariaApiError ? err.detail : "No se pudo registrar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mx-auto w-full max-w-md space-y-4 animate-panel-fade">
      <div>
        <h2 className="font-display text-3xl text-ink">Crear cuenta</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Contraseña: mínimo 12 caracteres, mayúscula, minúscula y dígito.
        </p>
      </div>
      <label className="block space-y-1.5 text-sm">
        <span className="font-medium">Usuario</span>
        <input
          required
          minLength={2}
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="w-full rounded-lg border border-border bg-card px-3 py-2 outline-none ring-ring focus:ring-2"
          autoComplete="username"
        />
      </label>
      <label className="block space-y-1.5 text-sm">
        <span className="font-medium">Email</span>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-lg border border-border bg-card px-3 py-2 outline-none ring-ring focus:ring-2"
          autoComplete="email"
        />
      </label>
      <label className="block space-y-1.5 text-sm">
        <span className="font-medium">Contraseña</span>
        <input
          type="password"
          required
          minLength={12}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded-lg border border-border bg-card px-3 py-2 outline-none ring-ring focus:ring-2"
          autoComplete="new-password"
        />
      </label>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <Button type="submit" className="w-full bg-accent text-accent-foreground hover:bg-accent/90" disabled={loading}>
        {loading ? "Creando…" : "Registrarme"}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        ¿Ya tienes cuenta?{" "}
        <button type="button" className="text-accent underline-offset-2 hover:underline" onClick={onSwitchToLogin}>
          Entrar
        </button>
      </p>
    </form>
  );
}
