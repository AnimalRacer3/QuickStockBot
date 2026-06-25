import { createHmac, randomBytes } from "crypto";
import type { LicenseValidationResult } from "./types.js";

export function generateNonce(): string {
  return randomBytes(32).toString("hex");
}

/** Verify HMAC-SHA256(nonce, secret) === proof */
export function verifyHmac(nonce: string, secret: string, proof: string): boolean {
  const expected = createHmac("sha256", secret).update(nonce).digest("hex");
  // Constant-time compare to prevent timing attacks
  if (expected.length !== proof.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) {
    diff |= expected.charCodeAt(i) ^ proof.charCodeAt(i);
  }
  return diff === 0;
}

/**
 * Validate a license key against the SaaS validation endpoint (Section 12).
 * Returns account_id on success.
 */
export async function validateLicense(
  licenseKey: string,
  botId: string,
  validateUrl: string
): Promise<LicenseValidationResult> {
  try {
    const resp = await fetch(validateUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ license_key: licenseKey, bot_id: botId }),
      signal: AbortSignal.timeout(5000),
    });
    if (!resp.ok) {
      return { valid: false, error: `HTTP ${resp.status}` };
    }
    const data = (await resp.json()) as LicenseValidationResult;
    return data;
  } catch (err) {
    return {
      valid: false,
      error: err instanceof Error ? err.message : "Network error",
    };
  }
}
