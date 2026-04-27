import { useEffect } from "react";
import { useAuthStore } from "./store/authStore";

export default function AppInitializer({ children }: { children: React.ReactNode }) {
  const { init, isLoading } = useAuthStore();

  useEffect(() => {
    init();
  }, [init]);

  if (isLoading) {
    return (
      <div className="loading-screen" style={{ 
        height: '100dvh', 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center', 
        gap: '1rem',
        background: 'var(--bg-app, #0f0a08)',
        color: 'var(--text-main, #f5ded5)'
      }}>
        <div className="spin" style={{ 
          width: '40px', 
          height: '40px', 
          border: '3px solid var(--accent, #ffb68d)', 
          borderTopColor: 'transparent', 
          borderRadius: '50%',
          animation: 'spin 1s linear infinite'
        }}></div>
        <style>{`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
        <p style={{ color: 'var(--text-dim, #a39089)', fontSize: '0.9rem' }}>Inizializzazione in corso...</p>
      </div>
    );
  }

  return <>{children}</>;
}
