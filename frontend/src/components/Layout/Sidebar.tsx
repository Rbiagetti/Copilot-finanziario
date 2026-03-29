import { useAppStore } from "../../store/appStore";
import { LayoutDashboard, MessageCircle, Wallet, List, Settings, Mic } from "lucide-react";

const NAV_ITEMS = [
  { key: "dashboard" as const, label: "Dashboard", icon: LayoutDashboard },
  { key: "transactions" as const, label: "Transazioni", icon: List },
  { key: "chat" as const, label: "Chat AI", icon: MessageCircle },
  { key: "budget" as const, label: "Budget", icon: Wallet },
  { key: "settings" as const, label: "Impostazioni", icon: Settings },
];

export default function Sidebar() {
  const { currentView, setView, setAutoStartVoice } = useAppStore();

  const startVoiceTransaction = () => {
    setView("transactions");
    setAutoStartVoice(true);
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
        
        {/* Pulsante Inserimento Rapido Vocale */}
        <button
          className="nav-item btn-sidebar-voice"
          onClick={startVoiceTransaction}
          style={{ 
            marginTop: '1rem', 
            background: 'linear-gradient(135deg, rgba(244, 63, 94, 0.1), rgba(244, 63, 94, 0.05))',
            borderColor: 'rgba(244, 63, 94, 0.25)',
            color: 'var(--danger)'
          }}
        >
          <Mic size={20} />
          <span style={{fontWeight: 600}}>Voce Rapida</span>
        </button>
      </nav>
    </aside>
  );
}
