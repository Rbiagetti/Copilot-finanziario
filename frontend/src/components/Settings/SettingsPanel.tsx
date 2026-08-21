import { useEffect, useState } from "react";
import { LogOut, Link2, CheckCircle2 } from "lucide-react";
import toast from "react-hot-toast";
import MonthlyReport from "./MonthlyReport";
import { useAuthStore } from "../../store/authStore";
import { linkGoogleIdentity, getLinkedProviders } from "../../lib/supabase";

export default function SettingsPanel() {
  const [loggingOut, setLoggingOut] = useState(false);
  const [linking, setLinking] = useState(false);
  const [providers, setProviders] = useState<string[]>([]);
  const { logout } = useAuthStore();

  useEffect(() => {
    getLinkedProviders().then(setProviders);
  }, []);

  const isGoogleLinked = providers.includes("google");

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await logout(); // M-6: usa authStore.logout() — pulisce cache e chiama signOut
      toast.success("Disconnesso");
    } catch {
      toast.error("Errore durante il logout");
      setLoggingOut(false);
    }
  };

  const handleLinkGoogle = async () => {
    setLinking(true);
    try {
      const { error } = await linkGoogleIdentity();
      if (error) {
        toast.error("Errore durante il collegamento con Google");
        setLinking(false);
      }
      // In caso di successo il browser viene reindirizzato a Google, quindi
      // non serve gestire altro stato qui.
    } catch {
      toast.error("Errore durante il collegamento con Google");
      setLinking(false);
    }
  };

  return (
    <div className="settings-page animate-in">
      <h2>Impostazioni</h2>
      <div className="settings-card">
        <div className="settings-row">
          <div>
            <h3>Account</h3>
            <p className="settings-copy">Esci dal tuo account FinCopilot.</p>
          </div>
          <button className="btn-logout" onClick={handleLogout} type="button" disabled={loggingOut} aria-label="Disconnetti">
            <LogOut size={16} />
            <span>{loggingOut ? "Uscita..." : "Disconnetti"}</span>
          </button>
        </div>
        <div className="settings-row">
          <div>
            <h3>Accesso con Google</h3>
            <p className="settings-copy">
              {isGoogleLinked
                ? "Il tuo account Google è collegato: puoi accedere anche con Google."
                : "Collega il tuo account Google per accedere senza password."}
            </p>
          </div>
          {isGoogleLinked ? (
            <span className="settings-linked-badge" aria-label="Google collegato">
              <CheckCircle2 size={16} />
              <span>Collegato</span>
            </span>
          ) : (
            <button
              className="btn-logout"
              onClick={handleLinkGoogle}
              type="button"
              disabled={linking}
              aria-label="Collega Google"
            >
              <Link2 size={16} />
              <span>{linking ? "Attendere..." : "Collega Google"}</span>
            </button>
          )}
        </div>
      </div>

      <MonthlyReport />
    </div>
  );
}
