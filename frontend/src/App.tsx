import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { useAppStore } from "./store/appStore";
import Sidebar from "./components/Layout/Sidebar";
import TopBar from "./components/Layout/TopBar";
import Dashboard from "./components/Dashboard/Dashboard";
import TransactionList from "./components/TransactionList/TransactionList";
import ChatInterface from "./components/ChatInterface/ChatInterface";
import BudgetPanel from "./components/BudgetPanel/BudgetPanel";
import SettingsPanel from "./components/Settings/SettingsPanel";
import LoginPage from "./components/Auth/LoginPage";
import { supabase } from "./lib/supabase";

type View = "dashboard" | "transactions" | "chat" | "budget" | "settings";
const VALID_VIEWS: View[] = ["dashboard", "transactions", "chat", "budget", "settings"];

function App() {
  const { currentView, setView } = useAppStore();
  const [session, setSession] = useState<any>(undefined); // undefined = loading
  const navigate = useNavigate();
  const location = useLocation();

  // Sync URL → Zustand: on initial load and browser back/forward
  useEffect(() => {
    const segment = location.pathname.replace(/^\//, "") as View;
    const view = VALID_VIEWS.includes(segment) ? segment : "dashboard";
    if (view !== currentView) {
      setView(view);
    }
  }, [location.pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync Zustand → URL: when setView() is called from anywhere in the app
  useEffect(() => {
    const expected = `/${currentView}`;
    if (location.pathname !== expected) {
      navigate(expected, { replace: location.pathname === "/" });
    }
  }, [currentView]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    document.documentElement.setAttribute(
      "data-theme",
      localStorage.getItem("theme") === "light" ? "light" : "dark",
    );
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    return () => subscription.unsubscribe();
  }, []);

  // Dev locale senza VITE_SUPABASE_URL configurato → salta login
  const supabaseConfigured = !!import.meta.env.VITE_SUPABASE_URL;

  if (supabaseConfigured && session === undefined) {
    return (
      <div className="loading-screen" style={{ height: '100dvh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '1rem' }}>
        <div className="spin" style={{ width: '40px', height: '40px', border: '3px solid var(--accent)', borderTopColor: 'transparent', borderRadius: '50%' }}></div>
        <p style={{ color: 'var(--text-dim)', fontSize: '0.9rem' }}>Verifica sessione in corso...</p>
      </div>
    );
  }

  if (supabaseConfigured && !session) {
    return (
      <LoginPage
        onLogin={() => {
          supabase.auth.getSession().then(({ data }) => setSession(data.session));
        }}
      />
    );
  }

  return (
    <div className="app">
      <Toaster
        position="top-right"
        containerStyle={{
          top: "calc(env(safe-area-inset-top, 0px) + 12px)",
          right: "calc(env(safe-area-inset-right, 0px) + 12px)",
        }}
        toastOptions={{
          style: {
            background: "rgba(41,29,23,0.92)",
            color: "#f5ded5",
            border: "1px solid rgba(255,182,141,0.20)",
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
            borderRadius: "18px",
            fontFamily: "Plus Jakarta Sans, -apple-system, sans-serif",
          },
        }}
      />
      <Sidebar />
      <TopBar />
      <main className="main-content">
        {currentView === "dashboard" && <Dashboard />}
        {currentView === "transactions" && <TransactionList />}
        {currentView === "chat" && <ChatInterface />}
        {currentView === "budget" && <BudgetPanel />}
        {currentView === "settings" && <SettingsPanel />}
      </main>
    </div>
  );
}

export default App;
