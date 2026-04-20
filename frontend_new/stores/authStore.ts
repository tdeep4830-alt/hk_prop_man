/**
 * authStore — JWT token + current user, persisted to localStorage.
 *
 * Uses _hasHydrated flag to avoid SSR/CSR hydration mismatch in Next.js
 * App Router. Components gate auth-dependent UI on this flag.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { UserResponse } from "@/types/api";

// ─── Types ────────────────────────────────────────────────────────────────────

interface AuthState {
  token:        string | null;
  user:         UserResponse | null;
  _hasHydrated: boolean;

  setToken:     (token: string) => void;
  setUser:      (user: UserResponse) => void;
  logout:       () => void;
  setHydrated:  () => void;
}

// ─── SSR-safe localStorage adapter ────────────────────────────────────────────

const safeLocalStorage = createJSONStorage(() => ({
  getItem:    (name: string) =>
    typeof window === "undefined" ? null : localStorage.getItem(name),
  setItem:    (name: string, value: string) => {
    if (typeof window !== "undefined") localStorage.setItem(name, value);
  },
  removeItem: (name: string) => {
    if (typeof window !== "undefined") localStorage.removeItem(name);
  },
}));

// ─── Store ────────────────────────────────────────────────────────────────────

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token:        null,
      user:         null,
      _hasHydrated: false,

      setToken: (token) => {
        set({ token });
        if (typeof window !== "undefined") {
          localStorage.setItem("propman_token", token);
        }
      },

      setUser: (user) => set({ user }),

      logout: () => {
        set({ token: null, user: null });
        if (typeof window !== "undefined") {
          localStorage.removeItem("propman_token");
        }
      },

      setHydrated: () => set({ _hasHydrated: true }),
    }),

    {
      name:    "propman-auth",
      storage: safeLocalStorage,

      // _hasHydrated is transient — never persist it
      partialize: (state) => ({ token: state.token, user: state.user }),

      onRehydrateStorage: () => (state, error) => {
        if (error) console.error("[authStore] rehydration failed:", error);
        state?.setHydrated();
      },
    },
  ),
);

// ─── Selectors ────────────────────────────────────────────────────────────────

export const selectIsHydrated      = (s: AuthState) => s._hasHydrated;
export const selectIsAuthenticated = (s: AuthState) =>
  s._hasHydrated && s.token !== null;
