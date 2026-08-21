import { useEffect, lazy, Suspense, useState, Component } from "react";
import type { ReactNode, ErrorInfo } from "react";
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

// Suspense fallback con timer — dopo 8s mostra pulsante Ricarica (critico per PWA senza browser reload)
const LoadingFallback = () => {
  const [stuck, setStuck] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setStuck(true), 8000);
    return () => clearTimeout(t);
  }, []);
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", alignItems: "center", justifyContent: "center", gap: "1.25rem" }}>
      {!stuck ? (
        <div className="spin" style={{ width: 32, height: 32, border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%" }} />
      ) : (
        <>
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", textAlign: "center" }}>Il caricamento sta impiegando troppo.</p>
          <button
            className="btn-primary"
            style={{ padding: "0.6rem 1.5rem", width: "auto" }}
            onClick={() => window.location.reload()}
          >
            Ricarica pagina
          </button>
        </>
      )}
    </div>
  );
};

// ErrorBoundary globale — cattura crash di componenti (schermo bianco senza questo in PWA)
interface EBState { hasError: boolean; }
class ErrorBoundary extends Component<{ children: ReactNode }, EBState> {
  state: EBState = { hasError: false };
  static getDerivedStateFromError(): EBState { return { hasError: true }; }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ display: "flex", flexDirection: "column", height: "80vh", alignItems: "center", justifyContent: "center", gap: "1.25rem" }}>
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", textAlign: "center", maxWidth: 320 }}>
            Qualcosa è andato storto in questa sezione.
          </p>
          <button
            className="btn-primary"
            style={{ padding: "0.6rem 1.5rem", width: "auto" }}
            onClick={() => { this.setState({ hasError: false }); window.location.reload(); }}
          >
            Ricarica pagina
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

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
            fontFamily: "Inter, -apple-system, sans-serif",
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
          <Route path="/dashboard" element={<ErrorBoundary><Suspense fallback={<LoadingFallback />}><Dashboard /></Suspense></ErrorBoundary>} />
          <Route path="/transactions" element={<ErrorBoundary><Suspense fallback={<LoadingFallback />}><TransactionList /></Suspense></ErrorBoundary>} />
          <Route path="/chat" element={<ErrorBoundary><Suspense fallback={<LoadingFallback />}><ChatInterface /></Suspense></ErrorBoundary>} />
          <Route path="/budget" element={<ErrorBoundary><Suspense fallback={<LoadingFallback />}><BudgetPanel /></Suspense></ErrorBoundary>} />
          <Route path="/settings" element={<ErrorBoundary><Suspense fallback={<LoadingFallback />}><SettingsPanel /></Suspense></ErrorBoundary>} />
        </Route>

        {/* Catch-all: redirect to dashboard if logged in, otherwise login */}
        <Route path="*" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
      </Routes>
    </div>
  );
}

export default App;

