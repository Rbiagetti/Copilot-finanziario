import { create } from "zustand";

type View = "dashboard" | "transactions" | "chat" | "budget" | "settings";

interface AppState {
  currentView: View;
  autoStartVoice: boolean;
  setView: (view: View) => void;
  setAutoStartVoice: (val: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentView: "dashboard",
  autoStartVoice: false,
  setView: (view) => set({ currentView: view }),
  setAutoStartVoice: (val) => set({ autoStartVoice: val }),
}));
