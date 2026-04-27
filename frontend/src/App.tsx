import { useEffect } from "react";
import { useNavigate, useLocation, Routes, Route, Navigate } from "react-router-dom";
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
import { useAuthStore } from "./store/authStore";

type View = "dashboard" | "transactions" | "chat" | "budget" | "settings";
const VALID_VIEWS: View[] = ["dashboard", "transactions", "chat", "budget", "settings"];


function App() {
  const { currentView, setView } = useAppStore();
  const { isAuthenticated } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const supabaseConfigured = !!import.meta.env.VITE_SUPABASE_URL;

  // Sync URL → Zustand: for authenticated users only
  useEffect(() => {
    if (!isAuthenticated) return;
    const segment = location.pathname.replace(/^\//, "") as View;
    const view = VALID_VIEWS.includes(segment) ? segment : "dashboard";
    if (view !== currentView) {
      setView(view);
    }
  }, [location.pathname, isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync Zustand → URL: for authenticated users only
  useEffect(() => {
    if (!isAuthenticated) return;
    const expected = `/${currentView}`;
    if (location.pathname !== expected) {
      navigate(expected, { replace: location.pathname === "/" });
    }
  }, [currentView, isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    document.documentElement.setAttribute(
      "data-theme",
      localStorage.getItem("theme") === "light" ? "light" : "dark",
    );
  }, []);

  if (!supabaseConfigured) {
    return <div>Supabase not configured. Check your .env file.</div>;
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
      
      <Routes>
        <Route 
          path="/login" 
          element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage onLogin={() => {}} />} 
        />
        
        <Route 
          path="/*" 
          element={
            !isAuthenticated ? (
              <Navigate to="/login" replace state={{ from: location }} />
            ) : (
              <>
                <Sidebar />
                <TopBar />
                <main className="main-content">
                  {currentView === "dashboard" && <Dashboard />}
                  {currentView === "transactions" && <TransactionList />}
                  {currentView === "chat" && <ChatInterface />}
                  {currentView === "budget" && <BudgetPanel />}
                  {currentView === "settings" && <SettingsPanel />}
                </main>
              </>
            )
          } 
        />
      </Routes>
    </div>
  );
}



export default App;
