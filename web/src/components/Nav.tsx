import Link from "next/link";
import { TrendingUp } from "lucide-react";
import { cookies } from "next/headers";
import { verifySession, SESSION_COOKIE } from "@/lib/session";
import { NavAuthButtons } from "@/components/NavAuthButtons";

export async function Nav() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;
  const session = token ? await verifySession(token) : null;
  const isAuthed = !!session;

  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border bg-bg/80 backdrop-blur-md">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 h-16 flex items-center justify-between">
        <Link
          href="/"
          className="flex items-center gap-2.5 text-ink font-semibold text-lg hover:opacity-90 transition-opacity"
        >
          <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 text-primary">
            <TrendingUp size={18} strokeWidth={2.5} />
          </span>
          <span>
            Quick<span className="text-primary">Stock</span>Bot
          </span>
        </Link>

        <nav className="hidden sm:flex items-center gap-1 text-sm text-ink-muted">
          <Link
            href="/#how-it-works"
            className="px-3 py-1.5 rounded-lg hover:text-ink hover:bg-white/5 transition-all"
          >
            How it works
          </Link>
          <Link
            href="/#features"
            className="px-3 py-1.5 rounded-lg hover:text-ink hover:bg-white/5 transition-all"
          >
            Features
          </Link>
          <Link
            href="/#pricing"
            className="px-3 py-1.5 rounded-lg hover:text-ink hover:bg-white/5 transition-all"
          >
            Pricing
          </Link>
        </nav>

        <div className="flex items-center gap-2">
          <NavAuthButtons isAuthed={isAuthed} />
        </div>
      </div>
    </header>
  );
}
