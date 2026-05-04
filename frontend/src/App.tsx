import { useEffect, lazy, Suspense } from "react";
import { useNavigate, useLocation, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { useAppStore } from "./store/appStore";
import Sidebar from "./components/Layout/Sidebar";
import TopBar from "./components/Layout/TopBar";
import LoginPage from "./components/Auth/LoginPage";
import { useAuthStore } from "./store/authStore";

// Code splitting for performance
const Dashboard = lazy(() => import("./components/Dashboard/Dashboard"));
const TransactionList = lazy(() => import("./components/TransactionList/TransactionList"));
const ChatInterface = lazy(() => import("./components/ChatInterface/ChatInterface"));
const BudgetPanel = lazy(() => import("./components/BudgetPanel/BudgetPanel"));
const SettingsPanel = lazy(() => import("./components/Settings/SettingsPanel"));

const LoadingFallback = () => (
  <div style={{ display: "flex", flexDirection: "column", height: "100vh", alignItems: "center", justifyContent: "center" }}>
    <div className="spin" style={{ width: 32, height: 32, border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%" }} />
  </div>
);

type View = "dashboard" | "transactions" | "chat" | "budget" | "settings";

function AppLayout() {
  const { isAuthenticated } = useAuthStore();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return (
    <>
      <Sidebar />
      <TopBar />
      <main className="main-content">
        <Outlet />
      </main>
    </>
  );
}

function App() {
  const { setView } = useAppStore();
  const { isAuthenticated } = useAuthStore();
  const location = useLocation();

  const supabaseConfigured = !!import.meta.env.VITE_SUPABASE_URL;

  // Sync URL → Zustand: still useful for some global state but no longer drives the render switch
  useEffect(() => {
    if (!isAuthenticated) return;
    const segment = location.pathname.replace(/^\//, "") as View;
    const validViews: View[] = ["dashboard", "transactions", "chat", "budget", "settings"];
    if (validViews.includes(segment)) {
      setView(segment);
    }
  }, [location.pathname, isAuthenticated, setView]);

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
          element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <LoginPage onLogin={() => {}} />} 
        />
        
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Suspense fallback={<LoadingFallback />}><Dashboard /></Suspense>} />
          <Route path="/transactions" element={<Suspense fallback={<LoadingFallback />}><TransactionList /></Suspense>} />
          <Route path="/chat" element={<Suspense fallback={<LoadingFallback />}><ChatInterface /></Suspense>} />
          <Route path="/budget" element={<Suspense fallback={<LoadingFallback />}><BudgetPanel /></Suspense>} />
          <Route path="/settings" element={<Suspense fallback={<LoadingFallback />}><SettingsPanel /></Suspense>} />
        </Route>

        {/* Catch-all: redirect to dashboard if logged in, otherwise login */}
        <Route path="*" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
      </Routes>
    </div>
  );
}

export default App;

