import { useEffect, useState } from "react";
import { Toaster } from "react-hot-toast";
import { useAppStore } from "./store/appStore";
import Sidebar from "./components/Layout/Sidebar";
import Dashboard from "./components/Dashboard/Dashboard";
import TransactionList from "./components/TransactionList/TransactionList";
import ChatInterface from "./components/ChatInterface/ChatInterface";
import BudgetPanel from "./components/BudgetPanel/BudgetPanel";
import LoginPage from "./components/Auth/LoginPage";
import { supabase } from "./lib/supabase";

function App() {
  const { currentView } = useAppStore();
  const [session, setSession] = useState<any>(undefined); // undefined = loading

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    return () => subscription.unsubscribe();
  }, []);

  // Dev locale senza VITE_SUPABASE_URL configurato → salta login
  const supabaseConfigured = !!import.meta.env.VITE_SUPABASE_URL;

  if (supabaseConfigured && session === undefined) {
    return <div className="loading">Caricamento...</div>;
  }

  if (supabaseConfigured && !session) {
    return (
      <LoginPage
        onLogin={() => supabase.auth.getSession().then(({ data }) => setSession(data.session))}
      />
    );
  }

  return (
    <div className="app">
      <Toaster
        position="top-right"
        toastOptions={{
          style: { background: "#1e1e2e", color: "#fff", border: "1px solid #333" },
        }}
      />
      <Sidebar />
      <main className="main-content">
        {currentView === "dashboard" && <Dashboard />}
        {currentView === "transactions" && <TransactionList />}
        {currentView === "chat" && <ChatInterface />}
        {currentView === "budget" && <BudgetPanel />}
      </main>
    </div>
  );
}

export default App;
