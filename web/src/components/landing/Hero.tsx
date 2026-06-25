import { ArrowRight, Zap } from "lucide-react";
import { Button } from "@/components/ui/Button";

const TERMINAL_ROWS = [
  {
    ticker: "AAPL",
    dir: "▲",
    pct: "+2.4%",
    signal: "Bullish",
    action: "BUY  10",
    color: "text-primary",
  },
  {
    ticker: "MSFT",
    dir: "▲",
    pct: "+1.1%",
    signal: "Neutral",
    action: "HOLD   —",
    color: "text-accent",
  },
  {
    ticker: "TSLA",
    dir: "▼",
    pct: "−0.9%",
    signal: "Bearish",
    action: "SELL   5",
    color: "text-red-400",
  },
  {
    ticker: "NVDA",
    dir: "▲",
    pct: "+3.2%",
    signal: "Bullish",
    action: "BUY   8",
    color: "text-primary",
  },
];

function TerminalPreview() {
  return (
    <div className="relative rounded-2xl overflow-hidden border border-border-strong bg-bg-card shadow-2xl">
      {/* Title bar */}
      <div className="flex items-center gap-2 px-4 py-3 bg-bg-surface border-b border-border">
        <span className="w-3 h-3 rounded-full bg-red-500/60" />
        <span className="w-3 h-3 rounded-full bg-yellow-500/60" />
        <span className="w-3 h-3 rounded-full bg-primary/60" />
        <span className="ml-3 text-xs text-ink-subtle font-mono">quickstockbot — paper mode</span>
      </div>

      {/* Table header */}
      <div className="px-4 pt-3 pb-1 grid grid-cols-4 text-xs text-ink-subtle font-mono border-b border-border">
        <span>TICKER</span>
        <span>SIGNAL</span>
        <span>NEWS</span>
        <span>ACTION</span>
      </div>

      {/* Rows */}
      {TERMINAL_ROWS.map((r) => (
        <div
          key={r.ticker}
          className="px-4 py-2 grid grid-cols-4 text-xs font-mono hover:bg-white/3 transition-colors"
        >
          <span className="text-ink font-semibold">{r.ticker}</span>
          <span className={r.color}>
            {r.dir} {r.pct}
          </span>
          <span className="text-ink-muted">{r.signal}</span>
          <span className={`${r.color} font-bold`}>{r.action}</span>
        </div>
      ))}

      {/* Footer bar */}
      <div className="px-4 py-3 bg-bg-surface border-t border-border text-xs font-mono text-ink-muted flex items-center justify-between">
        <span>
          P&amp;L today: <span className="text-primary font-semibold">+$1,204.80</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
          live feed
        </span>
      </div>
    </div>
  );
}

export function Hero() {
  return (
    <section className="relative min-h-screen flex items-center pt-16 overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-grid opacity-100" />
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-bg/60 to-bg" />
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-primary/5 blur-3xl pointer-events-none" />

      <div className="relative mx-auto max-w-6xl px-4 sm:px-6 py-16 sm:py-24 w-full">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Copy */}
          <div className="flex flex-col gap-6">
            <div className="inline-flex items-center gap-2 self-start px-3 py-1.5 rounded-full border border-primary/30 bg-primary/10 text-primary text-xs font-medium">
              <Zap size={12} strokeWidth={2.5} />
              Paper → Live in one toggle
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-[3.5rem] font-bold leading-[1.1] tracking-tight">
              Your stock bot that{" "}
              <span className="text-gradient-primary">trades while you sleep</span>
            </h1>

            <p className="text-ink-muted text-lg leading-relaxed max-w-xl">
              QuickStockBot watches the tape, reads multi-source news, and learns from market
              signals — paper trading first, then live when{" "}
              <em className="not-italic text-ink">you&apos;re confident</em>.
            </p>

            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 pt-2">
              <Button href="/signup" variant="primary" size="lg">
                Start 1 month free
                <ArrowRight size={16} strokeWidth={2.5} />
              </Button>
              <Button href="#how-it-works" variant="ghost" size="lg">
                See how it works
              </Button>
            </div>

            <p className="text-xs text-ink-subtle">No credit card required. Cancel anytime.</p>
          </div>

          {/* Terminal preview */}
          <div className="lg:pl-4">
            <TerminalPreview />
          </div>
        </div>
      </div>
    </section>
  );
}
