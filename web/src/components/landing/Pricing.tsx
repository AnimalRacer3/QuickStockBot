import { Check, X, ArrowRight, Smartphone } from "lucide-react";
import { Button } from "@/components/ui/Button";

const SHARED_FEATURES = [
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
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
            Simple, transparent pricing
          </h2>
          <p className="mt-4 text-ink-muted text-lg">
            Two plans. One difference. Cancel whenever.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-3xl mx-auto">
          {/* Basic Card */}
          <div className="relative rounded-2xl border border-border bg-bg-card overflow-hidden flex flex-col">
            <div className="pt-8 px-8 pb-8 flex flex-col gap-6 flex-1">
              <div>
                <h3 className="text-xl font-bold text-ink">Basic</h3>
                <p className="mt-1 text-sm text-ink-muted">Desktop access only</p>
              </div>

              <div>
                <div className="flex items-baseline gap-1">
                  <span className="text-4xl font-bold text-ink">$4.99</span>
                  <span className="text-ink-muted text-lg">/month</span>
                </div>
                <p className="mt-1 text-xs text-ink-muted">billed monthly</p>
              </div>

              <ul className="flex flex-col gap-3" aria-label="Basic plan features">
                {SHARED_FEATURES.map((f) => (
                  <li key={f} className="flex items-start gap-3 text-sm">
                    <Check size={16} className="text-primary mt-0.5 shrink-0" strokeWidth={2.5} />
                    <span className="text-ink-muted">{f}</span>
                  </li>
                ))}
                <li className="flex items-start gap-3 text-sm">
                  <X size={16} className="text-ink-subtle mt-0.5 shrink-0" strokeWidth={2.5} />
                  <span className="text-ink-subtle">Mobile access</span>
                </li>
              </ul>

              <div className="flex flex-col gap-3 pt-2 mt-auto">
                <Button
                  href="/signup?plan=basic"
                  variant="secondary"
                  size="lg"
                  className="w-full justify-center"
                  data-testid="pricing-cta-basic"
                >
                  Get Basic
                  <ArrowRight size={16} strokeWidth={2.5} />
                </Button>
                <p className="text-center text-xs text-ink-subtle">No credit card required.</p>
              </div>
            </div>
          </div>

          {/* Premium Card */}
          <div className="relative rounded-2xl border border-primary/30 bg-bg-card overflow-hidden flex flex-col glow-primary">
            {/* Top badge */}
            <div className="absolute top-0 left-0 right-0 flex justify-center">
              <span className="px-4 py-1 bg-primary text-bg text-xs font-bold rounded-b-xl tracking-wide">
                1 MONTH FREE TRIAL
              </span>
            </div>

            <div className="pt-10 px-8 pb-8 flex flex-col gap-6 flex-1">
              <div>
                <h3 className="text-xl font-bold text-ink">Premium</h3>
                <p className="mt-1 text-sm text-ink-muted">Desktop + mobile access</p>
              </div>

              <div>
                <div className="flex items-baseline gap-1 mt-2">
                  <span className="text-4xl font-bold text-ink">$6.99</span>
                  <span className="text-ink-muted text-lg">/month</span>
                </div>
                <p className="mt-1 text-xs text-ink-muted">after your free month — billed monthly</p>
              </div>

              <ul className="flex flex-col gap-3" aria-label="Premium plan features">
                {SHARED_FEATURES.map((f) => (
                  <li key={f} className="flex items-start gap-3 text-sm">
                    <Check size={16} className="text-primary mt-0.5 shrink-0" strokeWidth={2.5} />
                    <span className="text-ink-muted">{f}</span>
                  </li>
                ))}
                <li className="flex items-start gap-3 text-sm">
                  <Smartphone size={16} className="text-primary mt-0.5 shrink-0" strokeWidth={2.5} />
                  <span className="text-ink-muted">Full mobile access — view & manage from anywhere</span>
                </li>
              </ul>

              <div className="flex flex-col gap-3 pt-2 mt-auto">
                <Button
                  href="/signup?plan=premium"
                  variant="primary"
                  size="lg"
                  className="w-full justify-center"
                  data-testid="pricing-cta-premium"
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
        </div>

        <p className="mt-8 text-center text-xs text-ink-subtle">
          Prices in USD. QuickStockBot does not provide financial advice.
        </p>
      </div>
    </section>
  );
}
