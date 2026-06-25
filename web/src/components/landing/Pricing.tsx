import { Check, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/Button";

const FEATURES = [
  "1 full month free — no credit card",
  "Paper & live trading modes",
  "Multi-source news + FinBERT AI analysis",
  "Momentum pre-open scanner",
  "Real-time WebSocket dashboard",
  "Trade history & P&L analytics",
  "JSON-based strategy config",
  "Email support",
];

export function Pricing() {
  return (
    <section id="pricing" className="relative py-24 sm:py-32 border-t border-border">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="text-center mb-16">
          <p className="text-primary text-sm font-semibold uppercase tracking-widest mb-3">
            Pricing
          </p>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">Simple, honest pricing</h2>
          <p className="mt-4 text-ink-muted text-lg">
            One plan. Everything included. Cancel whenever.
          </p>
        </div>

        {/* Pricing card — centered, max-md width */}
        <div className="mx-auto max-w-md">
          <div className="relative rounded-2xl border border-primary/30 bg-bg-card overflow-hidden glow-primary">
            {/* Top badge */}
            <div className="absolute top-0 left-0 right-0 flex justify-center">
              <span className="px-4 py-1 bg-primary text-bg text-xs font-bold rounded-b-xl tracking-wide">
                1 MONTH FREE
              </span>
            </div>

            <div className="pt-10 px-8 pb-8 flex flex-col gap-6">
              {/* Price */}
              <div className="text-center">
                <div className="flex items-baseline justify-center gap-1 mt-2">
                  <span className="text-5xl font-bold text-ink">$6.99</span>
                  <span className="text-ink-muted text-lg">/month</span>
                </div>
                <p className="mt-1.5 text-sm text-ink-muted">
                  after your free month — billed monthly
                </p>
              </div>

              {/* Feature list */}
              <ul className="flex flex-col gap-3" aria-label="Plan features">
                {FEATURES.map((f) => (
                  <li key={f} className="flex items-start gap-3 text-sm">
                    <Check size={16} className="text-primary mt-0.5 shrink-0" strokeWidth={2.5} />
                    <span className="text-ink-muted">{f}</span>
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <div className="flex flex-col gap-3 pt-2">
                <Button
                  href="/signup"
                  variant="primary"
                  size="lg"
                  className="w-full justify-center"
                  data-testid="pricing-cta"
                >
                  Start free trial
                  <ArrowRight size={16} strokeWidth={2.5} />
                </Button>
                <p className="text-center text-xs text-ink-subtle">
                  No credit card required. Cancel anytime.
                </p>
              </div>
            </div>
          </div>

          <p className="mt-6 text-center text-xs text-ink-subtle">
            Prices in USD. QuickStockBot does not provide financial advice.
          </p>
        </div>
      </div>
    </section>
  );
}
