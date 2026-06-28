import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getLicense } from "@/lib/license";

/**
 * POST /api/licenses/seed
 * Body: { key: string, userId: string, expiresAt?: string }
 *
 * Admin-only endpoint to insert a specific license key directly into the
 * database. Protected by ADMIN_API_KEY header (x-admin-key).
 *
 * Use this when a key was distributed (e.g. via installer) before the normal
 * issue flow could run, so the relay's license validation can find it.
 */
export async function POST(req: NextRequest) {
  const adminKey = process.env.ADMIN_API_KEY;
  if (adminKey) {
    const provided = req.headers.get("x-admin-key");
    if (provided !== adminKey) {
      return NextResponse.json({ error: "unauthorized" }, { status: 401 });
    }
  }

  let body: { key?: string; userId?: string; expiresAt?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const { key, userId, expiresAt } = body;
  if (!key || !userId) {
    return NextResponse.json({ error: "key and userId are required" }, { status: 400 });
  }

  if (!/^QSB-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(key)) {
    return NextResponse.json(
      { error: "key must match format QSB-XXXX-XXXX-XXXX-XXXX" },
      { status: 400 }
    );
  }

  const existing = await getLicense(key);
  if (existing) {
    return NextResponse.json(
      { error: "license key already exists", status: existing.status },
      { status: 409 }
    );
  }

  const issuedAt = new Date();
  await prisma.license.create({
    data: {
      key,
      userId,
      status: "active",
      issuedAt,
      expiresAt: expiresAt ? new Date(expiresAt) : null,
    },
  });

  return NextResponse.json(
    { key, userId, status: "active", issuedAt: issuedAt.toISOString() },
    { status: 201 }
  );
}
