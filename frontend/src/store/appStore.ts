import { create } from "zustand";

type View = "dashboard" | "transactions" | "chat" | "budget" | "settings";

interface AppState {
  currentView: View;
  setView: (view: View) => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentView: "dashboard",
  setView: (view) => set({ currentView: view }),
}));
