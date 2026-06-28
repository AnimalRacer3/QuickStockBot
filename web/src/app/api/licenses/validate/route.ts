import { NextRequest, NextResponse } from "next/server";
import { getLicense, validateLicense } from "@/lib/license";

/** GET /api/licenses/validate?key=QSB-... — phone-home endpoint used by the bot. */
export async function GET(req: NextRequest) {
  const key = req.nextUrl.searchParams.get("key");
  if (!key) {
    return NextResponse.json({ error: "key is required" }, { status: 400 });
  }

  const status = await validateLicense(key);

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
  const relaySecret = process.env.RELAY_SECRET;
  if (relaySecret) {
    const provided = req.headers.get("x-relay-secret");
    if (provided !== relaySecret) {
      return NextResponse.json({ valid: false, error: "unauthorized" }, { status: 401 });
    }
  }
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

  const license = await getLicense(license_key);

  if (!license) {
    return NextResponse.json({ valid: false, error: "license not found" });
  }

  const status = await validateLicense(license_key);
  if (status !== "active") {
    return NextResponse.json({ valid: false, error: `license is ${status}` });
  }

  return NextResponse.json({
    valid: true,
    account_id: license.userId,
    connection_password: license.connectionPassword ?? null,
  });
}
