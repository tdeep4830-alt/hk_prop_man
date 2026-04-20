"use client";

import { useState, useEffect } from "react";
import { useRouter }           from "next/navigation";
import Link                    from "next/link";

import { useAuthStore, selectIsAuthenticated, selectIsHydrated } from "@/stores/authStore";
import { authApi } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();

  const isHydrated      = useAuthStore(selectIsHydrated);
  const isAuthenticated = useAuthStore(selectIsAuthenticated);
  const setToken        = useAuthStore((s) => s.setToken);
  const setUser         = useAuthStore((s) => s.setUser);

  // Already logged in → go to chat
  useEffect(() => {
    if (isHydrated && isAuthenticated) router.replace("/chat");
  }, [isHydrated, isAuthenticated, router]);

  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState<string | null>(null);
  const [loading,  setLoading]  = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const { access_token } = await authApi.login({ email, password });
      setToken(access_token);
      const user = await authApi.me();
      setUser(user);
      router.push("/chat");
    } catch (err: unknown) {
      const msg = (err as { detail?: string })?.detail ?? "登入失敗，請檢查電郵或密碼。";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  if (!isHydrated) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-50">
        <div className="w-5 h-5 rounded-full border-2 border-zinc-300 border-t-zinc-900 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 flex flex-col items-center justify-center px-4">

      {/* Logo */}
      <Link href="/" className="mb-8 text-sm font-bold tracking-tight text-zinc-900 hover:opacity-70 transition-opacity">
        PropMan AI
      </Link>

      <div className="w-full max-w-sm bg-white border border-zinc-200 rounded-2xl p-8 shadow-sm">

        <h1 className="text-xl font-bold text-zinc-900 mb-1">登入</h1>
        <p className="text-sm text-zinc-500 mb-6">
          歡迎回來，請輸入您的帳戶資料。
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">

          <div className="flex flex-col gap-1.5">
            <label htmlFor="email" className="text-xs font-medium text-zinc-700">
              電郵地址
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2.5 text-sm
                         text-zinc-900 placeholder:text-zinc-400
                         focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:border-transparent
                         transition"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="password" className="text-xs font-medium text-zinc-700">
              密碼
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2.5 text-sm
                         text-zinc-900 placeholder:text-zinc-400
                         focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:border-transparent
                         transition"
            />
          </div>

          {error && (
            <p className="text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-zinc-900 text-white rounded-xl py-2.5 text-sm font-medium
                       hover:bg-zinc-700 active:bg-zinc-800 transition-colors
                       disabled:opacity-50 disabled:cursor-not-allowed mt-1"
          >
            {loading ? "登入中…" : "登入"}
          </button>
        </form>

        <p className="text-center text-xs text-zinc-500 mt-6">
          還未有帳戶？{" "}
          <Link href="/register" className="text-zinc-900 font-medium hover:underline">
            免費註冊
          </Link>
        </p>
      </div>
    </div>
  );
}
