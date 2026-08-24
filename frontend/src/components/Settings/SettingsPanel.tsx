import { useEffect, useState } from "react";
import { LogOut, CheckCircle2 } from "lucide-react";
import toast from "react-hot-toast";
import MonthlyReport from "./MonthlyReport";
import AiImporter from "./AiImporter";
import CategoryManager from "./CategoryManager";
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
        <div className="settings-row settings-row-google">
          <div className="settings-row-label">
            <span className="settings-google-badge" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 18 18">
                <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.9c1.7-1.57 2.7-3.87 2.7-6.62z" />
                <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.9-2.26c-.8.54-1.84.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.96v2.33A9 9 0 0 0 9 18z" />
                <path fill="#FBBC05" d="M3.95 10.7A5.4 5.4 0 0 1 3.66 9c0-.59.1-1.17.29-1.7V4.97H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.03l2.99-2.33z" />
                <path fill="#EA4335" d="M9 3.58c1.32 0 2.51.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.97l2.99 2.33C4.66 5.17 6.65 3.58 9 3.58z" />
              </svg>
            </span>
            <div>
              <h3>Accesso con Google</h3>
              <p className="settings-copy">
                {isGoogleLinked
                  ? "Account Google collegato: puoi accedere anche senza password."
                  : "Collega il tuo account Google per accedere anche senza password."}
              </p>
            </div>
          </div>
          {isGoogleLinked ? (
            <span className="settings-linked-badge" aria-label="Google collegato">
              <CheckCircle2 size={15} />
              <span>Collegato</span>
            </span>
          ) : (
            <button
              className="btn-link-google"
              onClick={handleLinkGoogle}
              type="button"
              disabled={linking}
              aria-label="Collega Google"
            >
              <span>{linking ? "Attendere..." : "Collega"}</span>
            </button>
          )}
        </div>
      </div>

      <CategoryManager />
      <AiImporter />
      <MonthlyReport />
    </div>
  );
}
