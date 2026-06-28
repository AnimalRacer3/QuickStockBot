import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { verifySession, SESSION_COOKIE } from "@/lib/session";
import { prisma } from "@/lib/db";
import { isAccessAllowed, statusLabel } from "@/lib/subscription";
import { getLicenseByUserId } from "@/lib/license";
import Link from "next/link";
import { BotConnectionCard } from "./BotConnectionCard";
import { CopyButton } from "./CopyButton";
import { ResendLicenseButton } from "./ResendLicenseButton";

const DOWNLOAD_URL =
  process.env.BOT_DOWNLOAD_URL ?? "https://download.quickstockbot.com/bot/latest";

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

  const license = await getLicenseByUserId(session.userId);

  return (
    <div className="min-h-screen flex flex-col pt-16">
      <div className="flex-1 px-6 py-10 max-w-4xl mx-auto w-full">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold text-ink">Dashboard</h1>
          <Link href="/billing" className="text-sm text-accent hover:underline">
            Manage billing
          </Link>
        </div>

        {/* Subscription status */}
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

        {/* Connection board CTA */}
        <Link
          href="/connect"
          className="rounded-xl border border-accent bg-surface p-6 mb-6 flex items-center justify-between gap-4 hover:bg-bg-card transition-colors group block"
        >
          <div>
            <h2 className="font-semibold text-ink text-lg mb-1">Open connection board</h2>
            <p className="text-sm text-ink-muted">
              Connect your bot and access live actions, active tickers, settings, ticker manager,
              trade history, and the calendar.
            </p>
          </div>
          <span className="text-accent text-2xl font-bold group-hover:translate-x-1 transition-transform shrink-0">
            →
          </span>
        </Link>

        {/* Connect your bot */}
        <BotConnectionCard />

        {/* Account → License */}
        <div className="rounded-xl border border-border bg-surface p-6 mb-6">
          <h2 className="font-semibold text-ink mb-1">Account → License</h2>
          {license ? (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-ink-muted">
                Your license key is shown below and was also sent to{" "}
                <strong className="text-ink">{user.email}</strong>. Paste it into the bot&apos;s
                setup wizard when prompted.
              </p>
              <div className="flex items-center gap-3 flex-wrap">
                <code className="font-mono text-sm bg-bg-card px-3 py-2 rounded-lg border border-border text-ink tracking-wider">
                  {license.key}
                </code>
                <CopyButton text={license.key} />
              </div>
            </div>
          ) : (
            <ResendLicenseButton userId={session.userId} />
          )}
        </div>

        {/* Download the bot */}
        <div className="rounded-xl border border-border bg-surface p-6">
          <h2 className="font-semibold text-ink mb-1">Download the bot</h2>
          <p className="text-sm text-ink-muted mb-3">
            Download the QuickStockBot installer for your platform and run it to launch the setup
            wizard.
          </p>
          <a
            href={DOWNLOAD_URL}
            className="text-sm text-accent hover:underline font-semibold"
            rel="noopener noreferrer"
          >
            Download latest installer →
          </a>
        </div>
      </div>
    </div>
  );
}
