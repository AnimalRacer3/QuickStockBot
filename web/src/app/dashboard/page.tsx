import { LayoutDashboard } from "lucide-react";
import { Button } from "@/components/ui/Button";

export default function DashboardPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-24">
      <div className="text-center max-w-sm">
        <span className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-accent/10 text-accent mb-6">
          <LayoutDashboard size={28} strokeWidth={1.75} />
        </span>
        <h1 className="text-2xl font-bold text-ink mb-2">Dashboard</h1>
        <p className="text-ink-muted mb-8">
          Your real-time trading dashboard is coming soon. Sign in to access live P&L, positions,
          and trade history.
        </p>
        <div className="flex gap-3 justify-center">
          <Button href="/login" variant="outline" size="md">
            Log in
          </Button>
          <Button href="/signup" variant="primary" size="md">
            Start free
          </Button>
        </div>
      </div>
    </div>
  );
}
