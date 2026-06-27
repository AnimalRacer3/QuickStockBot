import { NextRequest, NextResponse } from "next/server";
import { getLicenseDb } from "@/lib/license-db";
import { createLicenseRepository } from "@/lib/license";

/** GET /api/licenses/validate?key=QSB-... — phone-home endpoint used by the bot. */
export async function GET(req: NextRequest) {
  const key = req.nextUrl.searchParams.get("key");
  if (!key) {
    return NextResponse.json({ error: "key is required" }, { status: 400 });
  }

  const repo = createLicenseRepository(getLicenseDb());
  const status = repo.validateLicense(key);

  if (status === null) {
    return NextResponse.json({ error: "license not found" }, { status: 404 });
  }

  return NextResponse.json({ status });
}

/**
 * POST /api/licenses/validate
 * Body: { license_key: string, bot_id: string }
 * Response: { valid: true, account_id: string } | { valid: false, error: string }
 *
 * Used by the relay server to authenticate bot connections.
 */
export async function POST(req: NextRequest) {
  let body: { license_key?: string; bot_id?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ valid: false, error: "invalid JSON body" }, { status: 400 });
  }

  const { license_key } = body;
  if (!license_key) {
    return NextResponse.json({ valid: false, error: "license_key is required" }, { status: 400 });
  }

  const repo = createLicenseRepository(getLicenseDb());
  const license = repo.getLicense(license_key);

  if (!license) {
    return NextResponse.json({ valid: false, error: "license not found" });
  }

  const status = repo.validateLicense(license_key);
  if (status !== "active") {
    return NextResponse.json({ valid: false, error: `license is ${status}` });
  }

  return NextResponse.json({ valid: true, account_id: license.userId });
}
