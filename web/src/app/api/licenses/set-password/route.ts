import { NextRequest, NextResponse } from "next/server";
import { getLicense, validateLicense, setConnectionPassword } from "@/lib/license";

/**
 * POST /api/licenses/set-password
 * Body: { license_key: string, connection_password: string }
 *
 * Links a user-chosen connection password to their license key.
 * Called by the installer during initial setup. Subsequent calls
 * update the password (the caller must already know the license key).
 */
export async function POST(req: NextRequest) {
  let body: { license_key?: string; connection_password?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: "invalid JSON body" }, { status: 400 });
  }

  const { license_key, connection_password } = body;

  if (!license_key) {
    return NextResponse.json({ ok: false, error: "license_key is required" }, { status: 400 });
  }
  if (!connection_password || connection_password.length < 8) {
    return NextResponse.json(
      { ok: false, error: "connection_password must be at least 8 characters" },
      { status: 400 }
    );
  }

  const license = await getLicense(license_key);

  if (!license) {
    return NextResponse.json({ ok: false, error: "license not found" }, { status: 404 });
  }

  const status = await validateLicense(license_key);
  if (status !== "active") {
    return NextResponse.json({ ok: false, error: `license is ${status}` }, { status: 403 });
  }

  await setConnectionPassword(license_key, connection_password);
  return NextResponse.json({ ok: true });
}
