import { useState } from "react";
import { Wallet } from "lucide-react";
import { signIn, signUp } from "../../lib/supabase";

export default function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"login" | "register">("login");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setInfo("");
    setLoading(true);

    if (mode === "login") {
      const { error: err } = await signIn(email, password);
      setLoading(false);
      if (err) {
        setError("Email o password non corretti.");
      } else {
        onLogin();
      }
    } else {
      const { error: err } = await signUp(email, password);
      setLoading(false);
      if (err) {
        setError(err.message);
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
