import Link from "next/link";
import { TrendingUp, Mail } from "lucide-react";

export default function VerifyEmailPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-16">
      <Link
        href="/"
        className="flex items-center gap-2.5 text-ink font-semibold text-lg hover:opacity-90 transition-opacity mb-10"
      >
        <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 text-primary">
          <TrendingUp size={18} strokeWidth={2.5} />
        </span>
        <span>
          Quick<span className="text-primary">Stock</span>Bot
        </span>
      </Link>

      <div className="w-full max-w-sm bg-bg-card border border-border rounded-2xl p-8 text-center">
        <div className="flex items-center justify-center w-12 h-12 rounded-full bg-primary/10 text-primary mx-auto mb-5">
          <Mail size={22} strokeWidth={2} />
        </div>

        <h1 className="text-2xl font-bold text-ink mb-2">Check your email</h1>
        <p className="text-ink-muted text-sm mb-3">
          We&apos;ve sent a verification link to your email address. Click the link to verify your
          account and start your free 1-month trial.
        </p>
        <p className="text-ink-subtle text-sm mb-8">
          The link expires in 24 hours. Check your spam folder if you don&apos;t see it.
        </p>

        <p className="text-sm text-ink-muted">
          Already verified?{" "}
          <Link
            href="/login"
            className="text-primary hover:text-primary-hover font-medium transition-colors"
          >
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
