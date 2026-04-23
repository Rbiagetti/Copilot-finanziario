import { useEffect, useState } from "react";
import { Toaster } from "react-hot-toast";
import { useAppStore } from "./store/appStore";
import Sidebar from "./components/Layout/Sidebar";
import Dashboard from "./components/Dashboard/Dashboard";
import TransactionList from "./components/TransactionList/TransactionList";
import ChatInterface from "./components/ChatInterface/ChatInterface";
import BudgetPanel from "./components/BudgetPanel/BudgetPanel";
import SettingsPanel from "./components/Settings/SettingsPanel";
import LoginPage from "./components/Auth/LoginPage";
import { supabase } from "./lib/supabase";

function App() {
  const { currentView } = useAppStore();
  const [session, setSession] = useState<any>(undefined); // undefined = loading

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
      <div className="loading-screen" style={{ height: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '1rem' }}>
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
