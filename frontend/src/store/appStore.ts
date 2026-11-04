import { create } from "zustand";
import type { ForecastData, FullHistoryTransaction } from "../api/client";
import { getCategoryNames } from "../api/client";

export type View = "dashboard" | "transactions" | "chat" | "budget" | "wealth" | "settings";

export const VALID_VIEWS: View[] = [
  "dashboard", "transactions", "chat", "budget", "wealth", "settings",
];

const VIEW_STORAGE_KEY = "currentView";

interface DashboardCache {
  rawHistory: FullHistoryTransaction[];
  forecast: ForecastData | null;
  loadedAt: number | null;
}

// Fallback iniziale = solo le standard, finché non arriva la risposta reale dal backend
// (standard + personalizzate attive) — evita che i menu risultino vuoti durante il primo
// caricamento.
const STANDARD_CATEGORIES_FALLBACK = [
  "cibo", "trasporti", "casa", "salute", "svago",
  "abbigliamento", "lavoro", "abbonamenti", "formazione",
  "intrattenimento", "altro",
];

interface AppState {
  currentView: View;
  autoStartVoice: boolean;
  dashboardFilter: { category?: string; dateFrom?: string; dateTo?: string; tags?: string };
  dashboardCache: DashboardCache;
  categories: string[];
  categoriesLoaded: boolean;
  setView: (view: View) => void;
  setAutoStartVoice: (val: boolean) => void;
  setDashboardFilter: (filter: Partial<AppState["dashboardFilter"]>) => void;
  setDashboardCache: (data: Omit<DashboardCache, "loadedAt">) => void;
  invalidateDashboardCache: () => void;
  loadCategories: () => Promise<void>;
  refreshCategories: () => Promise<void>;
  reset: () => void;
}

// Ultima sezione visitata. Serve al redirect iniziale, soprattutto quando la PWA
// viene riaperta dalla home: iOS ricarica start_url (o un URL vecchio) e senza
// questo si tornerebbe sempre sulla dashboard invece dell'ultima schermata.
export const getLastView = (): View => {
  try {
    const saved = localStorage.getItem(VIEW_STORAGE_KEY) as View | null;
    return saved && VALID_VIEWS.includes(saved) ? saved : "dashboard";
  } catch {
    // localStorage non disponibile (es. Safari in modalità privata)
    return "dashboard";
  }
};

export const useAppStore = create<AppState>((set, get) => ({
  currentView: getLastView(),
  autoStartVoice: false,
  dashboardFilter: {},
  dashboardCache: {
    rawHistory: [],
    forecast: null,
    loadedAt: null,
  },
  categories: STANDARD_CATEGORIES_FALLBACK,
  categoriesLoaded: false,
  setView: (view) => {
    try {
      localStorage.setItem(VIEW_STORAGE_KEY, view);
    } catch {
      // ignora: la view resta corretta in memoria per questa sessione
    }
    set({ currentView: view });
  },
  setAutoStartVoice: (val) => set({ autoStartVoice: val }),
  setDashboardFilter: (filter) => set((state) => ({
    dashboardFilter: { ...state.dashboardFilter, ...filter }
  })),
  setDashboardCache: (data) => set({
    dashboardCache: { ...data, loadedAt: Date.now() }
  }),
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
  }),
}));
