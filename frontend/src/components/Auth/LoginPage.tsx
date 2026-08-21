import { useState } from "react";
import { Wallet } from "lucide-react";
import { signIn, signUp, signInWithGoogle } from "../../lib/supabase";

export default function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [mode, setMode] = useState<"login" | "register">("login");

  const handleGoogleLogin = async () => {
    setError("");
    setInfo("");
    setGoogleLoading(true);
    const { error: err } = await signInWithGoogle();
    if (err) {
      setError("Errore durante l'accesso con Google.");
      setGoogleLoading(false);
    }
    // In caso di successo il browser viene reindirizzato a Google.
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setInfo("");
    setLoading(true);

    if (mode === "login") {
      const { error: err } = await signIn(email, password);
      setLoading(false);
      if (err) {
        if (err.status === 429) {
          setError("Troppe richieste. Per favore attendi qualche minuto prima di riprovare.");
        } else {
          setError(err.status === 400 ? "Credenziali errate." : "Errore durante l'accesso.");
        }
      } else {
        onLogin();
      }
    } else {
      const { error: err } = await signUp(email, password);
      setLoading(false);
      if (err) {
        if (err.status === 429) {
          setError("Limite di registrazioni raggiunto per ora. Attendi qualche minuto.");
        } else {
          setError(err.message);
        }
      } else {
        setInfo("Registrazione completata! Controlla la tua email per confermare l'account, poi accedi.");
        setMode("login");
      }
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <Wallet size={32} />
          <span>FinCopilot</span>
        </div>
        <p className="login-subtitle">Il tuo copilota finanziario AI</p>
        <button
          type="button"
          className="btn-google"
          onClick={handleGoogleLogin}
          disabled={googleLoading}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.9c1.7-1.57 2.7-3.87 2.7-6.62z" />
            <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.9-2.26c-.8.54-1.84.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.96v2.33A9 9 0 0 0 9 18z" />
            <path fill="#FBBC05" d="M3.95 10.7A5.4 5.4 0 0 1 3.66 9c0-.59.1-1.17.29-1.7V4.97H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.03l2.99-2.33z" />
            <path fill="#EA4335" d="M9 3.58c1.32 0 2.51.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.97l2.99 2.33C4.66 5.17 6.65 3.58 9 3.58z" />
          </svg>
          <span>{googleLoading ? "Attendere..." : "Accedi con Google"}</span>
        </button>
        <div className="login-divider"><span>oppure</span></div>
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="tua@email.com"
              required
              autoComplete="email"
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </div>
          {error && <p className="login-error">{error}</p>}
          {info && <p className="login-info">{info}</p>}
          <button className="btn-primary" type="submit" disabled={loading}>
            {loading
              ? mode === "login" ? "Accesso in corso..." : "Registrazione in corso..."
              : mode === "login" ? "Accedi" : "Registrati"}
          </button>
        </form>
        <p className="login-switch">
          {mode === "login" ? (
            <>Non hai un account?{" "}
              <button type="button" onClick={() => { setMode("register"); setError(""); setInfo(""); }}>
                Registrati
              </button>
            </>
          ) : (
            <>Hai già un account?{" "}
              <button type="button" onClick={() => { setMode("login"); setError(""); setInfo(""); }}>
                Accedi
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
