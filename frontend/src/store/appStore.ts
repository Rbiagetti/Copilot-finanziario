import { create } from "zustand";

type View = "dashboard" | "transactions" | "chat" | "budget" | "settings";

interface AppState {
  currentView: View;
  autoStartVoice: boolean;
  dashboardFilter: { category?: string; dateFrom?: string; dateTo?: string; tags?: string };
  setView: (view: View) => void;
  setAutoStartVoice: (val: boolean) => void;
  setDashboardFilter: (filter: Partial<AppState["dashboardFilter"]>) => void;
}

const getInitialView = (): View => {
  const saved = localStorage.getItem("currentView") as View;
  const validViews: View[] = ["dashboard", "transactions", "chat", "budget", "settings"];
  return validViews.includes(saved) ? (saved === "chat" ? "dashboard" : saved) : "dashboard";
};

export const useAppStore = create<AppState>((set) => ({
  currentView: getInitialView(),
  autoStartVoice: false,
  dashboardFilter: {},
  setView: (view) => {
    localStorage.setItem("currentView", view);
    set({ currentView: view });
  },
  setAutoStartVoice: (val) => set({ autoStartVoice: val }),
  setDashboardFilter: (filter) => set((state) => ({ 
    dashboardFilter: { ...state.dashboardFilter, ...filter } 
  })),
}));
