// src/store/authStore.ts
import { create } from "zustand";

interface AuthState {
  token: string | null;
  user: { id: string; email: string } | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  init: () => Promise<void>;
  logout: () => void;
}

/** safe read from localStorage */
const readToken = (): string | null => {
  try {
    return localStorage.getItem("authToken");
  } catch {
    return null;
  }
};

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  isLoading: true,
  isAuthenticated: false,

  init: async () => {
    const stored = readToken();
    if (!stored) {
      set({ isLoading: false, isAuthenticated: false, token: null, user: null });
      return;
    }
    try {
      const resp = await fetch("/api/auth/verify", {
        method: "POST",
        headers: { Authorization: `Bearer ${stored}` },
      });
      if (!resp.ok) throw new Error("invalid token");
      const data = await resp.json(); // { token, user }
      localStorage.setItem("authToken", data.token);
      set({
        token: data.token,
        user: data.user,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (e) {
      // silent logout on any error (expired, network, etc.)
      get().logout();
      set({ isLoading: false, isAuthenticated: false });
    }
  },

  logout: () => {
    localStorage.removeItem("authToken");
    set({ token: null, user: null, isAuthenticated: false });
  },
}))
