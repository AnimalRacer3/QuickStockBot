import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { verifySession, SESSION_COOKIE } from "@/lib/session";
import { prisma } from "@/lib/db";
import { isAccessAllowed, statusLabel } from "@/lib/subscription";
import Link from "next/link";

export default async function DashboardPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;
  if (!token) redirect("/login");

  const session = await verifySession(token);
  if (!session) redirect("/login");

  const user = await prisma.user.findUnique({
    where: { id: session.userId },
    select: {
      email: true,
      subscriptionStatus: true,
      trialEnd: true,
      currentPeriodEnd: true,
    },
  });

  if (!user || !isAccessAllowed(user.subscriptionStatus)) {
    redirect("/billing");
  }

  const trialEnd = user.trialEnd ? new Date(user.trialEnd) : null;
  const periodEnd = user.currentPeriodEnd ? new Date(user.currentPeriodEnd) : null;

  return (
    <div className="min-h-screen flex flex-col pt-16">
      <div className="flex-1 px-6 py-10 max-w-4xl mx-auto w-full">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold text-ink">Dashboard</h1>
          <Link href="/billing" className="text-sm text-accent hover:underline">
            Manage billing
          </Link>
        </div>

        <div className="rounded-xl border border-border bg-surface p-4 mb-8 flex items-center gap-3">
          <span className="text-sm text-ink-muted">Subscription:</span>
          <span className="font-semibold text-sm">{statusLabel(user.subscriptionStatus)}</span>
          {user.subscriptionStatus === "trialing" && trialEnd && (
            <span className="text-sm text-ink-muted">
              — trial ends {trialEnd.toLocaleDateString()}
            </span>
          )}
          {user.subscriptionStatus === "active" && periodEnd && (
            <span className="text-sm text-ink-muted">
              — renews {periodEnd.toLocaleDateString()}
            </span>
          )}
        </div>

        <div className="rounded-xl border-2 border-dashed border-border p-12 text-center text-ink-muted">
          <p>Bot controls and live trading data will appear here.</p>
        </div>
      </div>
    </div>
  );
}
