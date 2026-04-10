"use client";

import Image from "next/image";
import Link from "next/link";
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
      setError(err instanceof Error ? err.message : "LOGIN FAILED");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center space-y-4">
          <Image src="/logo.png" alt="OCCP" width={64} height={64} className="mx-auto rounded-xl" />
          <div className="space-y-2">
            <div className="font-pixel text-[11px] text-occp-primary/50 tracking-wider">
              **** OPENCLOUD CONTROL PLANE ****
            </div>
            <h1 className="font-pixel text-sm tracking-wide">
              <span className="text-occp-primary text-glow">OCCP</span>{" "}
              <span className="text-[var(--text)]">DASHBOARD</span>
            </h1>
            <p className="text-xs text-[var(--text-muted)] font-mono">AUTHENTICATION REQUIRED</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="retro-card p-6 space-y-5 crt-glow">
          <div className="space-y-4">
            <div>
              <label
                htmlFor="username"
                className="block font-pixel text-[11px] text-[var(--text-muted)] mb-2 uppercase tracking-widest"
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
                className="retro-input w-full"
                placeholder="admin"
              />
            </div>
            <div>
              <label
                htmlFor="password"
                className="block font-pixel text-[11px] text-[var(--text-muted)] mb-2 uppercase tracking-widest"
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
                className="retro-input w-full"
                placeholder="&#9679;&#9679;&#9679;&#9679;&#9679;&#9679;&#9679;&#9679;"
              />
            </div>
          </div>

          {error && (
            <div className="retro-card border-occp-danger/40 bg-occp-danger/5 p-3">
              <span className="font-pixel text-[11px] text-occp-danger mr-2">?ERROR</span>
              <span className="text-sm text-occp-danger font-mono">{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username.trim() || !password.trim()}
            className="retro-btn-primary w-full py-3 font-pixel text-[11px] tracking-wider"
          >
            {loading ? "LOADING..." : "LOGIN"}
          </button>
        </form>

        <div className="text-center space-y-2">
          <p className="font-pixel text-[11px] text-[var(--text-muted)]/40 tracking-wider">
            OCCP V0.8.2 &mdash; READY
            <span className="inline-block w-1.5 h-2.5 bg-occp-primary ml-1 animate-blink align-middle" />
          </p>
          <p className="text-[10px] text-[var(--text-muted)]/30 font-mono">
            New user?{" "}
            <Link href="/register" className="text-occp-primary hover:text-glow transition-colors">
              CREATE ACCOUNT
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
