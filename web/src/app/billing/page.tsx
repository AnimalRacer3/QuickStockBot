import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { verifySession, SESSION_COOKIE } from "@/lib/session";
import { prisma } from "@/lib/db";
import { statusLabel } from "@/lib/subscription";
import BillingActions from "./BillingActions";

export default async function BillingPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;
  const session = token ? await verifySession(token) : null;
  if (!session?.userId) redirect("/login");

  const user = await prisma.user.findUnique({
    where: { id: session.userId },
    select: {
      subscriptionStatus: true,
      trialEnd: true,
      currentPeriodEnd: true,
      stripeCustomerId: true,
    },
  });

  const status = user?.subscriptionStatus ?? null;
  const trialEnd = user?.trialEnd ? new Date(user.trialEnd) : null;
  const periodEnd = user?.currentPeriodEnd ? new Date(user.currentPeriodEnd) : null;
  const hasCustomer = !!user?.stripeCustomerId;

  return (
    <div className="min-h-screen flex items-start justify-center px-4 py-16">
      <div className="w-full max-w-md rounded-xl border border-border bg-surface p-8">
        <h1 className="text-2xl font-bold text-ink mb-6">Billing</h1>

        <div className="flex items-center gap-3 mb-4">
          <span className="text-sm text-ink-muted">Status</span>
          <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${badgeClass(status)}`}>
            {statusLabel(status)}
          </span>
        </div>

        {status === "trialing" && trialEnd && (
          <p className="text-sm text-ink-muted mb-4">
            Your free trial ends on <strong>{trialEnd.toLocaleDateString()}</strong>.
          </p>
        )}
        {status === "active" && periodEnd && (
          <p className="text-sm text-ink-muted mb-4">
            Next billing date: <strong>{periodEnd.toLocaleDateString()}</strong>.
          </p>
        )}
        {status === "past_due" && (
          <p className="text-sm text-amber-700 bg-amber-50 px-3 py-2 rounded-lg mb-4">
            Your last payment failed. Please update your payment method to restore access.
          </p>
        )}
        {status === "canceled" && (
          <p className="text-sm text-ink-muted mb-4">
            Your subscription was canceled. Resubscribe below to regain access.
          </p>
        )}
        {!status && (
          <p className="text-sm text-ink-muted mb-4">
            Start your 30-day free trial — no charge until the trial ends.
          </p>
        )}

        <BillingActions status={status} hasCustomer={hasCustomer} />
      </div>
    </div>
  );
}

function badgeClass(status: string | null): string {
  if (status === "active") return "bg-green-100 text-green-800";
  if (status === "trialing") return "bg-blue-100 text-blue-800";
  if (status === "past_due") return "bg-amber-100 text-amber-800";
  if (status === "canceled") return "bg-red-100 text-red-800";
  return "bg-gray-100 text-gray-700";
}
