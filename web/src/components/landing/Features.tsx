import { ToggleRight, Newspaper, LayoutDashboard } from "lucide-react";

const FEATURES = [
  {
    icon: ToggleRight,
    iconBg: "bg-primary/10",
    iconColor: "text-primary",
    title: "Paper → Live, Zero Friction",
    description:
      "Run your exact strategy in paper mode against live market data. When performance is where you want it, switch to live with a single env variable — no code changes, no workflow disruption.",
    pills: ["Paper mode", "Live mode", "Same strategy", "One toggle"],
  },
  {
    icon: Newspaper,
    iconBg: "bg-accent/10",
    iconColor: "text-accent",
    title: "Multi-source News + AI Analysis",
    description:
      "Aggregates news from Bloomberg, Reuters, SEC filings, and Reddit. FinBERT sentiment scoring weighs each signal and adjusts trade confidence in real time.",
    pills: ["FinBERT NLP", "Sentiment scoring", "RSS + API", "Real-time"],
  },
  {
    icon: LayoutDashboard,
    iconBg: "bg-purple-500/10",
    iconColor: "text-purple-400",
    title: "Real-Time Dashboards",
    description:
      "Live P&L curves, open positions, fill history, and scanner output — all streaming via WebSocket. Desktop and mobile optimized.",
    pills: ["WebSocket", "P&L charts", "Trade history", "Mobile-ready"],
  },
];

export function Features() {
  return (
    <section id="features" className="relative py-24 sm:py-32 border-t border-border bg-bg-surface">
      {/* Subtle grid overlay */}
      <div className="absolute inset-0 bg-grid opacity-50 pointer-events-none" />

      <div className="relative mx-auto max-w-6xl px-4 sm:px-6">
        <div className="text-center mb-16">
          <p className="text-primary text-sm font-semibold uppercase tracking-widest mb-3">
            Features
          </p>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
            Built for serious traders
          </h2>
          <p className="mt-4 text-ink-muted text-lg max-w-2xl mx-auto">
            Not a toy. QuickStockBot runs on your infra, keeps your API keys private, and executes
            with sub-second latency.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="relative flex flex-col gap-5 p-6 rounded-2xl bg-bg-card border border-border hover:border-border-strong transition-colors group"
            >
              <div
                className={`flex items-center justify-center w-12 h-12 rounded-xl ${feature.iconBg} ${feature.iconColor}`}
              >
                <feature.icon size={22} strokeWidth={1.75} />
              </div>

              <div>
                <h3 className="font-semibold text-lg text-ink mb-2">{feature.title}</h3>
                <p className="text-ink-muted text-sm leading-relaxed">{feature.description}</p>
              </div>

              <div className="flex flex-wrap gap-2 mt-auto pt-2">
                {feature.pills.map((pill) => (
                  <span
                    key={pill}
                    className="px-2.5 py-1 text-xs rounded-lg bg-bg-surface text-ink-muted border border-border"
                  >
                    {pill}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
