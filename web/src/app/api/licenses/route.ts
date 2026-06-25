import { NextRequest, NextResponse } from "next/server";
import { randomUUID } from "crypto";
import { getDb } from "@/lib/db";
import { createLicenseRepository } from "@/lib/license";
import { sendLicenseEmail } from "@/lib/email";

const DOWNLOAD_URL =
  process.env.BOT_DOWNLOAD_URL ??
  "https://download.quickstockbot.com/bot/latest"; // stubbed until Section 16

/** POST /api/licenses — issue a license for a user and send the delivery email. */
export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as {
      userId?: string;
      email?: string;
      name?: string;
    };
    const { userId, email, name } = body;

    if (!email) {
      return NextResponse.json({ error: "email is required" }, { status: 400 });
    }

    const db = getDb();
    const repo = createLicenseRepository(db);

    let user = repo.getUserByEmail(email);
    if (!user) {
      const id = userId ?? randomUUID();
      user = repo.createUser(id, email, name);
    }

    const license = repo.issueLicense(user.id);

    const { Resend } = await import("resend");
    const resend = new Resend(process.env.RESEND_API_KEY);
    await sendLicenseEmail(resend, {
      to: email,
      name: user.name,
      licenseKey: license.key,
      downloadUrl: DOWNLOAD_URL,
    });

    return NextResponse.json(
      { key: license.key, issuedAt: license.issuedAt },
      { status: 201 },
    );
  } catch (err) {
    console.error("[POST /api/licenses]", err);
    return NextResponse.json(
      { error: "internal server error" },
      { status: 500 },
    );
  }
}
