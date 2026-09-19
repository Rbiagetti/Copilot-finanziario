import { useAppStore } from "../../store/appStore";
import BrandMark from "./BrandMark";

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
        <div className="topbar-logo">
          <BrandMark size={26} />
        </div>
        <span className="topbar-brand">FINCOPILOT</span>
      </div>
      <div className="topbar-title">{TITLES[currentView] ?? ""}</div>
    </header>
  );
}
