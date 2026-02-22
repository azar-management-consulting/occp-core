"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Redirect if already authenticated
  if (isAuthenticated) {
    router.replace("/");
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;

    setLoading(true);
    setError(null);

    try {
      await login(username, password);
      router.replace("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-sm space-y-8">
        {/* Logo & Title */}
        <div className="text-center space-y-3">
          <Image
            src="/logo.png"
            alt="OCCP"
            width={64}
            height={64}
            className="mx-auto rounded-xl"
          />
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="text-occp-primary">OCCP</span> Dashboard
            </h1>
            <p className="text-sm text-[var(--text-muted)] mt-1">
              Sign in to Mission Control
            </p>
          </div>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-3">
            <div>
              <label
                htmlFor="username"
                className="block text-xs font-medium text-[var(--text-muted)] mb-1.5 uppercase tracking-wider"
              >
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                required
                className="w-full bg-[var(--bg)] border border-occp-muted/30 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-occp-primary/50 focus:border-occp-primary/50 transition-colors"
                placeholder="admin"
              />
            </div>
            <div>
              <label
                htmlFor="password"
                className="block text-xs font-medium text-[var(--text-muted)] mb-1.5 uppercase tracking-wider"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                className="w-full bg-[var(--bg)] border border-occp-muted/30 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-occp-primary/50 focus:border-occp-primary/50 transition-colors"
                placeholder="••••••••"
              />
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="bg-occp-danger/10 border border-occp-danger/30 rounded-lg p-3 text-sm text-occp-danger">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username.trim() || !password.trim()}
            className="w-full py-2.5 bg-occp-primary hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="text-center text-xs text-[var(--text-muted)]">
          OpenCloud Control Plane v0.4.0
        </p>
      </div>
    </div>
  );
}
