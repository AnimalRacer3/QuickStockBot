import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getLicenseDb } from "@/lib/license-db";
import { createLicenseRepository } from "@/lib/license";
import { sendLicenseEmail } from "@/lib/email";
import { Resend } from "resend";

const DOWNLOAD_URL =
  process.env.BOT_DOWNLOAD_URL ?? "https://download.quickstockbot.com/bot/latest"; // stubbed until Section 16

/** POST /api/licenses — issue a license for a verified subscriber and email it. */
export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as { userId?: string; email?: string };
    const { userId, email } = body;

    if (!email && !userId) {
      return NextResponse.json({ error: "email or userId is required" }, { status: 400 });
    }

    // Look up the Prisma user
    const user = await prisma.user.findUnique({
      where: email ? { email } : { id: userId! },
    });

    if (!user) {
      return NextResponse.json({ error: "user not found" }, { status: 404 });
    }

    if (!user.emailVerified) {
      return NextResponse.json({ error: "email not verified" }, { status: 403 });
    }

    const activeSub =
      user.subscriptionStatus === "active" || user.subscriptionStatus === "trialing";
    if (!activeSub) {
      return NextResponse.json({ error: "no active subscription" }, { status: 403 });
    }

    const repo = createLicenseRepository(getLicenseDb());
    const license = repo.issueLicense(user.id);

    const resendClient = new Resend(process.env.RESEND_API_KEY);
    await sendLicenseEmail(resendClient, {
      to: user.email,
      name: null,
      licenseKey: license.key,
      downloadUrl: DOWNLOAD_URL,
    });

    return NextResponse.json({ key: license.key, issuedAt: license.issuedAt }, { status: 201 });
  } catch (err) {
    console.error("[POST /api/licenses]", err);
    return NextResponse.json({ error: "internal server error" }, { status: 500 });
  }
}
