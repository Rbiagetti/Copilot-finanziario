import { useMemo, useState } from "react";
import { Moon, Sun } from "lucide-react";

export default function SettingsPanel() {
  const initialDark = useMemo(() => localStorage.getItem("theme") !== "light", []);
  const [dark, setDark] = useState(initialDark);

  const toggleTheme = () => {
    const nextDark = !dark;
    const root = document.documentElement;
    root.classList.add("theme-transitioning");
    root.setAttribute("data-theme", nextDark ? "dark" : "light");
    localStorage.setItem("theme", nextDark ? "dark" : "light");
    setDark(nextDark);
    window.setTimeout(() => root.classList.remove("theme-transitioning"), 520);
  };

  return (
    <div className="settings-page">
      <h2>Impostazioni</h2>
      <div className="settings-card">
        <div className="settings-row">
          <div>
            <h3>Tema</h3>
            <p className="settings-copy">
              Scegli tra modalità scura e chiara con transizione fluida.
            </p>
          </div>
          <button className="theme-switch-btn" onClick={toggleTheme} type="button">
            {dark ? <Sun size={16} /> : <Moon size={16} />}
            <span>{dark ? "Modalità chiara" : "Modalità scura"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
