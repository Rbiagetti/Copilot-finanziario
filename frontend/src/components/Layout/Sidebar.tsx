import { useState } from "react";
import { useAppStore } from "../../store/appStore";
import { LayoutDashboard, MessageCircle, Wallet, List, Settings, LogOut } from "lucide-react";
import { signOut } from "../../lib/supabase";
import toast from "react-hot-toast";

const NAV_ITEMS = [
  { key: "dashboard" as const, label: "Dashboard", icon: LayoutDashboard },
  { key: "transactions" as const, label: "Transazioni", icon: List },
  { key: "chat" as const, label: "Chat AI", icon: MessageCircle },
  { key: "budget" as const, label: "Budget", icon: Wallet },
  { key: "settings" as const, label: "Impostazioni", icon: Settings },
];

export default function Sidebar() {
  const { currentView, setView } = useAppStore();
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await signOut();
      toast.success("Disconnesso");
    } catch {
      toast.error("Errore durante il logout");
      setLoggingOut(false);
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <Wallet size={28} />
        <span>FinCopilot</span>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            className={`nav-item ${currentView === key ? "active" : ""}`}
            onClick={() => setView(key)}
          >
            <Icon size={20} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer desktop-only" style={{ marginTop: "auto", padding: "1rem" }}>
        <button
          className="nav-item"
          onClick={handleLogout}
          disabled={loggingOut}
          aria-label="Disconnetti"
          style={{ width: "100%", justifyContent: "flex-start", color: "var(--text-dim)" }}
        >
          <LogOut size={20} />
          <span>{loggingOut ? "Uscita..." : "Disconnetti"}</span>
        </button>
      </div>
    </aside>
  );
}
