import { Wallet } from "lucide-react";
import { useAppStore } from "../../store/appStore";

const TITLES: Record<string, string> = {
  dashboard: "Dashboard",
  transactions: "Transazioni",
  chat: "Chat AI",
  budget: "Budget",
  settings: "Impostazioni",
};

export default function TopBar() {
  const { currentView } = useAppStore();
  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="topbar-logo" aria-hidden="true">
          <Wallet size={18} />
        </div>
        <span className="topbar-brand">FinCopilot</span>
      </div>
      <div className="topbar-title">{TITLES[currentView] ?? ""}</div>
    </header>
  );
}
