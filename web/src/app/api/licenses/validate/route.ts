import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { createLicenseRepository } from "@/lib/license";

/** GET /api/licenses/validate?key=QSB-... — phone-home endpoint used by the bot. */
export async function GET(req: NextRequest) {
  const key = req.nextUrl.searchParams.get("key");
  if (!key) {
    return NextResponse.json({ error: "key is required" }, { status: 400 });
  }

  const repo = createLicenseRepository(getDb());
  const status = repo.validateLicense(key);

  if (status === null) {
    return NextResponse.json({ error: "license not found" }, { status: 404 });
  }

  return NextResponse.json({ status });
}
