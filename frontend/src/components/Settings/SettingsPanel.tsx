import { useState } from "react";
import { LogOut } from "lucide-react";
import toast from "react-hot-toast";
import MonthlyReport from "./MonthlyReport";
import { useAuthStore } from "../../store/authStore";

export default function SettingsPanel() {
  const [loggingOut, setLoggingOut] = useState(false);
  const { logout } = useAuthStore();

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
      </div>

      <MonthlyReport />
    </div>
  );
}
