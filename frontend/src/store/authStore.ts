// src/store/authStore.ts
import { create } from "zustand";
import { supabase } from "../lib/supabase";
import type { Session } from "@supabase/supabase-js";
import { useAppStore } from "./appStore";

interface AuthState {
  session: Session | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  init: () => Promise<void>;
  setSession: (session: Session | null) => void;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  session: null,
  isLoading: true,
  isAuthenticated: false,

  init: async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      set({ 
        session, 
        isAuthenticated: !!session, 
        isLoading: false 
      });

      // Listen for auth changes (login, logout, token refresh)
      supabase.auth.onAuthStateChange((event, session) => {
        if (event === "SIGNED_OUT") {
          // Pulisce tutta la cache dati al logout — evita che utente B veda dati di utente A
          useAppStore.getState().reset();
        }
        set({
          session,
          isAuthenticated: !!session,
          isLoading: false
        });
      });
    } catch (error) {
      console.error("Auth initialization error:", error);
      set({ isLoading: false, isAuthenticated: false });
    }
  },

  setSession: (session) => {
    set({ session, isAuthenticated: !!session });
  },

  logout: async () => {
    await supabase.auth.signOut();
    set({ session: null, isAuthenticated: false });
  },
}));

