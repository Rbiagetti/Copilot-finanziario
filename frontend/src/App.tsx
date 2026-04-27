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
import { useAuthStore } from "./store/authStore";

type View = "dashboard" | "transactions" | "chat" | "budget" | "settings";
const VALID_VIEWS: View[] = ["dashboard", "transactions", "chat", "budget", "settings"];

function App() {
  const { currentView, setView } = useAppStore();
  // Auth handling via authStore
  const {
    isLoading,
    isAuthenticated,
    logout,
  } = useAuthStore();

  // Keep theme sync as before
  useEffect(() => {
    document.documentElement.setAttribute(
      "data-theme",
      localStorage.getItem("theme") === "light" ? "light" : "dark",
    );
    // authStore.init is called in AppInitializer (or can be called here if not)
  }, []);

  // Removed previous session state; auth logic handled by authStore and AppInitializer
  // Session handling removed – auth state now comes from authStore (isAuthenticated)
  if (supabaseConfigured && !isAuthenticated) {
    return (
      <LoginPage
        onLogin={() => {
          // After successful login via Supabase, re‑initialize authStore to pick up token
          supabase.auth.getSession().then(() => {
            useAuthStore.getState().init();
          });
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
