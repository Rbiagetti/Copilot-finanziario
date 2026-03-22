import { useAppStore } from "../../store/appStore";
import { LayoutDashboard, PlusCircle, MessageCircle, Wallet, List } from "lucide-react";

const NAV_ITEMS = [
  { key: "dashboard" as const, label: "Dashboard", icon: LayoutDashboard },
  { key: "transactions" as const, label: "Transazioni", icon: List },
  { key: "chat" as const, label: "Chat AI", icon: MessageCircle },
  { key: "budget" as const, label: "Budget", icon: Wallet },
];

export default function Sidebar() {
  const { currentView, setView } = useAppStore();

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
    </aside>
  );
}
