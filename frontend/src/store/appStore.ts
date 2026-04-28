import { create } from "zustand";
import type { ForecastData, Anomaly, FullHistoryTransaction } from "../api/client";

type View = "dashboard" | "transactions" | "chat" | "budget" | "settings";

interface DashboardCache {
  rawHistory: FullHistoryTransaction[];
  forecast: ForecastData | null;
  loadedAt: number | null;
}

interface AnomalyState {
  data: Anomaly[];
  count: number;
  by_type: Record<string, number>;
  generated_at: string | null;
  has_new_transactions: boolean;
}

interface AppState {
  currentView: View;
  autoStartVoice: boolean;
  dashboardFilter: { category?: string; dateFrom?: string; dateTo?: string; tags?: string };
  dashboardCache: DashboardCache;
  anomalies: AnomalyState;
  setView: (view: View) => void;
  setAutoStartVoice: (val: boolean) => void;
  setDashboardFilter: (filter: Partial<AppState["dashboardFilter"]>) => void;
  setDashboardCache: (data: Omit<DashboardCache, "loadedAt">) => void;
  setAnomalies: (data: Anomaly[], generated_at: string) => void;
  markTransactionsAsNew: () => void;
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
  anomalies: {
    data: [],
    count: 0,
    by_type: {},
    generated_at: null,
    has_new_transactions: false,
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
  setAnomalies: (data, generated_at) => {
    // Count by detection_type
    const by_type: Record<string, number> = {};
    data.forEach((anomaly) => {
      const dt = anomaly.detection_type || "amount_spike";
      by_type[dt] = (by_type[dt] || 0) + 1;
    });

    set({
      anomalies: {
        data,
        count: data.length,
        by_type,
        generated_at,
        has_new_transactions: false, // reset when loading fresh anomalies
      },
    });
  },
  markTransactionsAsNew: () => set((state) => ({
    anomalies: { ...state.anomalies, has_new_transactions: true }
  })),
  invalidateDashboardCache: () => set((state) => ({
    dashboardCache: { ...state.dashboardCache, loadedAt: null }
  })),
}));
