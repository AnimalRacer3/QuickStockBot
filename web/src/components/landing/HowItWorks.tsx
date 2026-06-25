import { Settings2, FlaskConical, Rocket, BarChart3 } from "lucide-react";

const STEPS = [
  {
    icon: Settings2,
    number: "01",
    title: "Configure your strategy",
    description:
      "Add your watchlist, set momentum thresholds, and define risk limits. JSON-based config that lives in your repo.",
  },
  {
    icon: FlaskConical,
    number: "02",
    title: "Paper trade to validate",
    description:
      "Run your strategy against real market data with zero real money. Watch the bot make decisions, learn what to tune.",
  },
  {
    icon: Rocket,
    number: "03",
    title: "Go live when you're ready",
    description:
      "Flip one environment variable. Same bot, same strategy — now executing real orders via your broker API.",
  },
  {
    icon: BarChart3,
    number: "04",
    title: "Monitor & improve",
    description:
      "Track P&L, positions, and trade history on the real-time dashboard. Replay trades, identify patterns, iterate.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="relative py-24 sm:py-32 border-t border-border">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="text-center mb-16">
          <p className="text-primary text-sm font-semibold uppercase tracking-widest mb-3">
            How it works
          </p>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
            From setup to live trading
            <br className="hidden sm:block" /> in under an hour
          </h2>
        </div>

        <div className="relative">
          {/* Connecting line (desktop) */}
          <div className="hidden lg:block absolute top-8 left-[calc(12.5%-1px)] right-[calc(12.5%-1px)] h-px bg-gradient-to-r from-transparent via-border-strong to-transparent" />

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 lg:gap-4">
            {STEPS.map((step) => (
              <div key={step.number} className="flex flex-col gap-4">
                <div className="relative flex items-center justify-center w-16 h-16 rounded-2xl bg-bg-card border border-border-strong">
                  <step.icon size={24} className="text-primary" strokeWidth={1.75} />
                  <span className="absolute -top-2 -right-2 text-[10px] font-bold font-mono text-ink-subtle bg-bg border border-border rounded-md px-1.5 py-0.5">
                    {step.number}
                  </span>
                </div>
                <div>
                  <h3 className="font-semibold text-ink mb-1.5">{step.title}</h3>
                  <p className="text-ink-muted text-sm leading-relaxed">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
