import { create } from "zustand";
import type { ForecastData, Anomaly, FullHistoryTransaction } from "../api/client";
import { getCategoryNames } from "../api/client";

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
  loading: boolean;
  refreshing: boolean;
}

// Fallback iniziale = solo le standard, finché non arriva la risposta reale dal backend
// (standard + personalizzate attive) — evita che i menu risultino vuoti durante il primo
// caricamento.
const STANDARD_CATEGORIES_FALLBACK = [
  "cibo", "trasporti", "casa", "salute", "svago",
  "abbigliamento", "lavoro", "abbonamenti", "formazione", "altro",
];

interface AppState {
  currentView: View;
  autoStartVoice: boolean;
  dashboardFilter: { category?: string; dateFrom?: string; dateTo?: string; tags?: string };
  dashboardCache: DashboardCache;
  anomalies: AnomalyState;
  categories: string[];
  categoriesLoaded: boolean;
  setView: (view: View) => void;
  setAutoStartVoice: (val: boolean) => void;
  setDashboardFilter: (filter: Partial<AppState["dashboardFilter"]>) => void;
  setDashboardCache: (data: Omit<DashboardCache, "loadedAt">) => void;
  setAnomalies: (response: { anomalies: Anomaly[]; count: number; by_type: Record<string, number>; generated_at: string | null }) => void;
  setAnomaliesLoading: (val: boolean) => void;
  setAnomaliesRefreshing: (val: boolean) => void;
  markTransactionsAsNew: () => void;
  invalidateDashboardCache: () => void;
  loadCategories: () => Promise<void>;
  refreshCategories: () => Promise<void>;
  reset: () => void;
}

const getInitialView = (): View => {
  const saved = localStorage.getItem("currentView") as View;
  const validViews: View[] = ["dashboard", "transactions", "chat", "budget", "settings"];
  return validViews.includes(saved) ? (saved === "chat" ? "dashboard" : saved) : "dashboard";
};

export const useAppStore = create<AppState>((set, get) => ({
  currentView: getInitialView(),
  autoStartVoice: false,
  dashboardFilter: {},
  dashboardCache: {
    rawHistory: [],
    forecast: null,
    loadedAt: null,
  },
  categories: STANDARD_CATEGORIES_FALLBACK,
  categoriesLoaded: false,
  anomalies: {
    data: [],
    count: 0,
    by_type: {},
    generated_at: null,
    has_new_transactions: false,
    loading: false,
    refreshing: false,
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
  setAnomalies: (response) => {
    set({
      anomalies: {
        data: response.anomalies,
        count: response.count,
        by_type: response.by_type,
        generated_at: response.generated_at,
        has_new_transactions: false,
        loading: false,
        refreshing: false,
      },
    });
  },
  setAnomaliesLoading: (val) => set((state) => ({
    anomalies: { ...state.anomalies, loading: val }
  })),
  setAnomaliesRefreshing: (val) => set((state) => ({
    anomalies: { ...state.anomalies, refreshing: val }
  })),
  markTransactionsAsNew: () => set((state) => ({
    anomalies: { ...state.anomalies, has_new_transactions: true }
  })),
  invalidateDashboardCache: () => set((state) => ({
    dashboardCache: { ...state.dashboardCache, loadedAt: null }
  })),
  // Caricata pigra al primo utilizzo (chiamata da ogni pagina che ne ha bisogno) e
  // ricaricata esplicitamente dopo aggiungi/elimina in Impostazioni — niente TTL, le
  // categorie cambiano raramente durante una sessione.
  loadCategories: async () => {
    if (get().categoriesLoaded) return;
    try {
      const { data } = await getCategoryNames();
      set({ categories: data.categories, categoriesLoaded: true });
    } catch {
      // mantiene il fallback standard già in stato — nessun crash, solo niente personalizzate
    }
  },
  // Forza il refetch (usata da Impostazioni dopo aggiungi/elimina una categoria
  // personalizzata) invece del semplice loadCategories che salta se già caricate una volta.
  refreshCategories: async () => {
    try {
      const { data } = await getCategoryNames();
      set({ categories: data.categories, categoriesLoaded: true });
    } catch {
      // ignora: la UI di Settings mostra comunque un toast d'errore sull'azione che l'ha causato
    }
  },
  reset: () => set({
    dashboardCache: { rawHistory: [], forecast: null, loadedAt: null },
    dashboardFilter: {},
    categories: STANDARD_CATEGORIES_FALLBACK,
    categoriesLoaded: false,
    anomalies: {
      data: [],
      count: 0,
      by_type: {},
      generated_at: null,
      has_new_transactions: false,
      loading: false,
      refreshing: false,
    },
  }),
}));
