import { Resend } from "resend";

const FROM = process.env.RESEND_FROM ?? "noreply@quickstockbot.com";
const BASE_URL = process.env.NEXTAUTH_URL || "http://localhost:3000";

function getResend(): Resend {
  return new Resend(process.env.RESEND_API_KEY);
}

// ── Auth email (Section 10) ───────────────────────────────────────────────────

export async function sendVerificationEmail(email: string, token: string): Promise<void> {
  const verifyUrl = `${BASE_URL}/api/auth/verify-email?token=${token}`;
  await getResend().emails.send({
    from: FROM,
    to: email,
    subject: "Verify your QuickStockBot account",
    html: `
      <h1>Welcome to QuickStockBot!</h1>
      <p>Click the link below to verify your email and start your free 1-month trial:</p>
      <p><a href="${verifyUrl}">${verifyUrl}</a></p>
      <p>This link expires in 24 hours. If you didn't sign up, ignore this email.</p>
    `,
  });
}

// ── License delivery email (Section 12) ──────────────────────────────────────

export interface LicenseEmailPayload {
  to: string;
  name: string | null;
  licenseKey: string;
  downloadUrl: string;
}

export interface EmailResult {
  id: string;
}

/** Minimal Resend-compatible client interface for easy mocking in tests. */
export interface ResendClient {
  emails: {
    send(params: {
      from: string;
      to: string | string[];
      subject: string;
      html: string;
      text: string;
    }): Promise<{
      data: { id: string } | null;
      error: { message: string } | null;
    }>;
  };
}

export function buildLicenseEmail(payload: LicenseEmailPayload): {
  subject: string;
  html: string;
  text: string;
} {
  const { name, licenseKey, downloadUrl } = payload;
  const greeting = name ? `Hi ${name}` : "Hi";
  const subject = "Your QuickStockBot License & Download";

  const text = `${greeting},

Thanks for subscribing to QuickStockBot!

Your license key:
  ${licenseKey}

Download the bot:
  ${downloadUrl}

Quick setup:
  1. Download and unzip the bot executable.
  2. Copy .env.example to .env and fill in your Alpaca API keys.
  3. Add LICENSE_KEY=${licenseKey} to your .env file.
  4. Run the bot: ./quickstockbot

Need help? Reply to this email or check our docs.

— The QuickStockBot Team`;

  const html = `<p>${greeting},</p>
<p>Thanks for subscribing to <strong>QuickStockBot</strong>!</p>

<h2>Your license key</h2>
<pre style="background:#f4f4f4;padding:12px 16px;border-radius:6px;font-size:1.1em;letter-spacing:.05em">${licenseKey}</pre>

<h2>Download</h2>
<p>
  <a href="${downloadUrl}"
     style="display:inline-block;background:#0070f3;color:#fff;padding:10px 22px;
            border-radius:5px;text-decoration:none;font-weight:600">
    Download QuickStockBot
  </a>
</p>

<h2>Quick setup</h2>
<ol>
  <li>Download and unzip the bot executable.</li>
  <li>Copy <code>.env.example</code> to <code>.env</code> and fill in your Alpaca API keys.</li>
  <li>Add <code>LICENSE_KEY=${licenseKey}</code> to your <code>.env</code> file.</li>
  <li>Run the bot: <code>./quickstockbot</code></li>
</ol>

<p>Need help? Reply to this email or check our docs.</p>
<p>— The QuickStockBot Team</p>`;

  return { subject, html, text };
}

export async function sendLicenseEmail(
  client: ResendClient,
  payload: LicenseEmailPayload
): Promise<EmailResult> {
  const { subject, html, text } = buildLicenseEmail(payload);
  const from = process.env.RESEND_FROM ?? "QuickStockBot <noreply@quickstockbot.com>";

  const { data, error } = await client.emails.send({
    from,
    to: payload.to,
    subject,
    html,
    text,
  });

  if (error || !data) {
    throw new Error(`Failed to send license email: ${error?.message ?? "unknown error"}`);
  }

  return { id: data.id };
}
