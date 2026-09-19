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
          <div className="logo-dots"><i /><i /><i /></div>
        </div>
        <span className="topbar-brand">FINCOPILOT</span>
      </div>
      <div className="topbar-title">{TITLES[currentView] ?? ""}</div>
    </header>
  );
}
