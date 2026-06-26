"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/Button";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    const res = await fetch("/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    const data = await res.json();
    setLoading(false);

    if (!res.ok) {
      setError(data.error ?? "Signup failed");
      return;
    }

    router.push("/verify-email");
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-16">
      <Link
        href="/"
        className="flex items-center gap-2.5 text-ink font-semibold text-lg hover:opacity-90 transition-opacity mb-10"
      >
        <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 text-primary">
          <TrendingUp size={18} strokeWidth={2.5} />
        </span>
        <span>
          Quick<span className="text-primary">Stock</span>Bot
        </span>
      </Link>

      <div className="w-full max-w-sm bg-bg-card border border-border rounded-2xl p-8">
        <h1 className="text-2xl font-bold text-ink mb-1">Create account</h1>
        <p className="text-ink-muted text-sm mb-8">Start trading smarter today</p>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-ink-muted mb-1.5" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              placeholder="you@example.com"
              className="w-full px-3.5 py-2.5 rounded-lg bg-bg border border-border-strong text-ink placeholder:text-ink-subtle text-sm focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-ink-muted mb-1.5" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
              placeholder="Min. 8 characters"
              className="w-full px-3.5 py-2.5 rounded-lg bg-bg border border-border-strong text-ink placeholder:text-ink-subtle text-sm focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-colors"
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3.5 py-2.5">
              {error}
            </p>
          )}

          <Button type="submit" disabled={loading} className="w-full" size="md">
            {loading ? "Creating account…" : "Create account"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-muted">
          Already have an account?{" "}
          <Link href="/login" className="text-primary hover:text-primary-hover font-medium transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
