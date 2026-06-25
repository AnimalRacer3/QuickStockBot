import { TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/Button";

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-24 bg-bg">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <span className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-primary/10 text-primary mb-4">
            <TrendingUp size={24} strokeWidth={2} />
          </span>
          <h1 className="text-2xl font-bold text-ink">Welcome back</h1>
          <p className="mt-1 text-ink-muted text-sm">Log in to your QuickStockBot account</p>
        </div>

        <div className="rounded-2xl border border-border bg-bg-card p-6 flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="email"
              className="text-xs font-medium text-ink-muted uppercase tracking-wide"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              placeholder="you@example.com"
              className="w-full px-4 py-2.5 rounded-xl bg-bg-surface border border-border text-ink placeholder:text-ink-subtle text-sm focus:outline-none focus:border-primary/50 transition-colors"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="password"
              className="text-xs font-medium text-ink-muted uppercase tracking-wide"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              placeholder="••••••••"
              className="w-full px-4 py-2.5 rounded-xl bg-bg-surface border border-border text-ink placeholder:text-ink-subtle text-sm focus:outline-none focus:border-primary/50 transition-colors"
            />
          </div>
          <Button variant="primary" size="md" className="w-full justify-center mt-1">
            Log in
          </Button>
        </div>

        <p className="mt-4 text-center text-sm text-ink-muted">
          No account?{" "}
          <a href="/signup" className="text-primary hover:underline">
            Sign up free
          </a>
        </p>
      </div>
    </div>
  );
}
