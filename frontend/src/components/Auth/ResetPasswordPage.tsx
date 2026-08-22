import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Wallet, KeyRound } from "lucide-react";
import toast from "react-hot-toast";
import { supabase, updatePassword } from "../../lib/supabase";

/** Pagina raggiunta cliccando il link ricevuto via email dopo "Password dimenticata?".
 * Supabase crea automaticamente una sessione di recupero temporanea leggendo il token
 * nell'URL (gestito dal client SDK, detectSessionInUrl di default) — qui aspettiamo solo
 * che sia pronta prima di mostrare il form. */
export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [invalidLink, setInvalidLink] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;
    // Il token nell'URL viene processato in modo asincrono dal client Supabase al load;
    // un breve check con retry evita un falso "link non valido" mentre è ancora in corso.
    const check = async (attempt = 0) => {
      const { data } = await supabase.auth.getSession();
      if (!mounted) return;
      if (data.session) {
        setReady(true);
      } else if (attempt < 5) {
        setTimeout(() => check(attempt + 1), 400);
      } else {
        setInvalidLink(true);
      }
    };
    check();
    return () => { mounted = false; };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 6) {
      setError("La password deve avere almeno 6 caratteri.");
      return;
    }
    if (password !== confirm) {
      setError("Le due password non coincidono.");
      return;
    }
    setLoading(true);
    const { error: err } = await updatePassword(password);
    setLoading(false);
    if (err) {
      setError("Errore durante l'aggiornamento della password. Riprova o richiedi un nuovo link.");
    } else {
      toast.success("Password aggiornata!");
      navigate("/dashboard", { replace: true });
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <Wallet size={32} />
          <span>FinCopilot</span>
        </div>
        <p className="login-subtitle">Imposta una nuova password</p>

        {invalidLink && (
          <>
            <p className="login-error">
              Questo link non è valido o è scaduto. Richiedi una nuova email dalla pagina di accesso.
            </p>
            <button className="btn-primary" type="button" onClick={() => navigate("/login", { replace: true })}>
              Torna al login
            </button>
          </>
        )}

        {!invalidLink && !ready && (
          <p className="settings-copy" style={{ textAlign: "center" }}>Verifica del link in corso...</p>
        )}

        {ready && !invalidLink && (
          <form onSubmit={handleSubmit} className="login-form">
            <div className="form-group">
              <label><KeyRound size={13} style={{ verticalAlign: -2, marginRight: 4 }} />Nuova password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="new-password"
              />
            </div>
            <div className="form-group">
              <label>Conferma password</label>
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="new-password"
              />
            </div>
            {error && <p className="login-error">{error}</p>}
            <button className="btn-primary" type="submit" disabled={loading}>
              {loading ? "Aggiornamento..." : "Aggiorna password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
