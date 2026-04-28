import { create } from "zustand";
import type { ForecastData, Anomaly, FullHistoryTransaction } from "../api/client";

type View = "dashboard" | "transactions" | "chat" | "budget" | "settings";

interface DashboardCache {
  rawHistory: FullHistoryTransaction[];
  forecast: ForecastData | null;
  loadedAt: number | null;
}

interface AnomaliesCache {
  anomalies: Anomaly[];
  loadedAt: number | null;
}

interface AppState {
  currentView: View;
  autoStartVoice: boolean;
  dashboardFilter: { category?: string; dateFrom?: string; dateTo?: string; tags?: string };
  dashboardCache: DashboardCache;
  anomaliesCache: AnomaliesCache;
  setView: (view: View) => void;
  setAutoStartVoice: (val: boolean) => void;
  setDashboardFilter: (filter: Partial<AppState["dashboardFilter"]>) => void;
  setDashboardCache: (data: Omit<DashboardCache, "loadedAt">) => void;
  setAnomaliesCache: (anomalies: Anomaly[]) => void;
  invalidateDashboardCache: () => void;
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
  dashboardCache: {
    rawHistory: [],
    forecast: null,
    loadedAt: null,
  },
  anomaliesCache: {
    anomalies: [],
    loadedAt: null,
  },
  setView: (view) => {
    localStorage.setItem("currentView", view);
    set({ currentView: view });
  },
  setAutoStartVoice: (val) => set({ autoStartVoice: val }),
  setDashboardFilter: (filter) => set((state) => ({
    dashboardFilter: { ...state.dashboardFilter, ...filter }
  })),
  setDashboardCache: (data) => set({
    dashboardCache: { ...data, loadedAt: Date.now() }
  }),
  setAnomaliesCache: (anomalies) => set({
    anomaliesCache: { anomalies, loadedAt: Date.now() }
  }),
  invalidateDashboardCache: () => set((state) => ({
    dashboardCache: { ...state.dashboardCache, loadedAt: null }
  })),
}));
