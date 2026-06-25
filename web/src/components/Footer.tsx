import { TrendingUp } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-border bg-bg-surface mt-auto">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 py-10">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <div className="flex items-center gap-2.5">
            <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-primary/10 text-primary">
              <TrendingUp size={15} strokeWidth={2.5} />
            </span>
            <span className="text-ink font-semibold">
              Quick<span className="text-primary">Stock</span>Bot
            </span>
          </div>

          <nav className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-muted">
            <a href="#pricing" className="hover:text-ink transition-colors">
              Pricing
            </a>
            <a href="/login" className="hover:text-ink transition-colors">
              Log in
            </a>
            <a href="/signup" className="hover:text-ink transition-colors">
              Sign up
            </a>
            <a href="/dashboard" className="hover:text-ink transition-colors">
              Dashboard
            </a>
          </nav>
        </div>

        <div className="mt-8 pt-6 border-t border-border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs text-ink-subtle">
          <p>&copy; {new Date().getFullYear()} QuickStockBot. Not financial advice.</p>
          <p>Past performance does not guarantee future results.</p>
        </div>
      </div>
    </footer>
  );
}
