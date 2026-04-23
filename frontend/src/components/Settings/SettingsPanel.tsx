import { signOut } from "../../lib/supabase";
import { LogOut } from "lucide-react";

export default function SettingsPanel() {
  const handleLogout = async () => {
    await signOut();
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
          <button className="theme-switch-btn" onClick={handleLogout} type="button">
            <LogOut size={16} />
            <span>Disconnetti</span>
          </button>
        </div>
      </div>
    </div>
  );
}
