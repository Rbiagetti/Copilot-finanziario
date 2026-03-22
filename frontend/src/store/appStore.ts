import { create } from "zustand";

type View = "dashboard" | "transactions" | "chat" | "budget";

interface AppState {
  currentView: View;
  setView: (view: View) => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentView: "dashboard",
  setView: (view) => set({ currentView: view }),
}));
