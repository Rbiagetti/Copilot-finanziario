import { useEffect, useState } from "react";
import { useAppStore } from "../../store/appStore";
import { LayoutDashboard, MessageCircle, Wallet, List, Sun, Moon } from "lucide-react";

const NAV_ITEMS = [
  { key: "dashboard" as const, label: "Dashboard", icon: LayoutDashboard },
  { key: "transactions" as const, label: "Transazioni", icon: List },
  { key: "chat" as const, label: "Chat AI", icon: MessageCircle },
  { key: "budget" as const, label: "Budget", icon: Wallet },
];

export default function Sidebar() {
  const { currentView, setView } = useAppStore();
  const [dark, setDark] = useState(() => localStorage.getItem("theme") !== "light");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  const toggleTheme = () => {
    const root = document.documentElement;
    root.classList.add("theme-transitioning");
    setDark((prev) => !prev);
    window.setTimeout(() => {
      root.classList.remove("theme-transitioning");
    }, 520);
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
      <div className="sidebar-bottom">
        <button className="nav-item theme-toggle" onClick={toggleTheme} title={dark ? "Modalità chiara" : "Modalità scura"}>
          {dark ? <Sun size={20} /> : <Moon size={20} />}
          <span>{dark ? "Chiara" : "Scura"}</span>
        </button>
      </div>
    </aside>
  );
}
