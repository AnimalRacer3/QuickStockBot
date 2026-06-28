import { NextRequest, NextResponse } from "next/server";
import { revokeLicense } from "@/lib/license";

/** PATCH /api/licenses/:key/revoke — admin endpoint to revoke a license. */
export async function PATCH(req: NextRequest, { params }: { params: Promise<{ key: string }> }) {
  const adminKey = process.env.ADMIN_API_KEY;
  if (adminKey) {
    const provided = req.headers.get("x-admin-key");
    if (provided !== adminKey) {
      return NextResponse.json({ error: "unauthorized" }, { status: 401 });
    }
  }

  const { key } = await params;
  const revoked = await revokeLicense(key);

  if (!revoked) {
    return NextResponse.json({ error: "license not found or already revoked" }, { status: 404 });
  }

  return NextResponse.json({ key, status: "revoked" });
}
