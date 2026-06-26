"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import Link from "next/link";
import { TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/Button";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [verified] = useState(() => params.get("verified") === "1");
  const [error, setError] = useState(() => {
    const e = params.get("error");
    if (e === "invalid-token") return "Invalid verification link.";
    if (e === "expired-token") return "Verification link has expired. Please sign up again.";
    return "";
  });
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    let res: Response;
    let data: { error?: string; emailVerified?: boolean } = {};
    try {
      res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      data = await res.json();
    } catch {
      setLoading(false);
      setError("Unable to reach the server. Please try again.");
      return;
    }
    setLoading(false);

    if (!res.ok) {
      setError(data.error ?? "Login failed");
      return;
    }

    if (!data.emailVerified) {
      router.push("/verify-email");
    } else {
      router.push("/dashboard");
    }
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
        <h1 className="text-2xl font-bold text-ink mb-1">Welcome back</h1>
        <p className="text-ink-muted text-sm mb-8">Sign in to your account</p>

        {verified && (
          <p role="status" className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3.5 py-2.5 mb-4">
            Your email is verified — please log in.
          </p>
        )}

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
              disabled={loading}
              autoComplete="email"
              placeholder="you@example.com"
              className="w-full px-3.5 py-2.5 rounded-lg bg-bg border border-border-strong text-ink placeholder:text-ink-subtle text-sm focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
              disabled={loading}
              autoComplete="current-password"
              placeholder="••••••••"
              className="w-full px-3.5 py-2.5 rounded-lg bg-bg border border-border-strong text-ink placeholder:text-ink-subtle text-sm focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3.5 py-2.5">
              {error}
            </p>
          )}

          <Button type="submit" disabled={loading} className="w-full" size="md">
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-muted">
          Don&apos;t have an account?{" "}
          <Link href="/signup" className="text-primary hover:text-primary-hover font-medium transition-colors">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
