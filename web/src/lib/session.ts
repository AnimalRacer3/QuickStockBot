import { SignJWT, jwtVerify, type JWTPayload } from "jose";

const SESSION_SECRET = new TextEncoder().encode(
  process.env.SESSION_SECRET ?? "dev-secret-change-in-production-32c"
);

export const SESSION_COOKIE = "qsb-session";
export const SESSION_TTL_SECONDS = 60 * 60 * 24 * 7; // 7 days

export type SessionPayload = JWTPayload & {
  userId: string;
  email: string;
  emailVerified: boolean;
};

export async function signSession(payload: SessionPayload): Promise<string> {
  return new SignJWT(payload)
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(`${SESSION_TTL_SECONDS}s`)
    .sign(SESSION_SECRET);
}

export async function verifySession(token: string): Promise<SessionPayload | null> {
  try {
    const { payload } = await jwtVerify(token, SESSION_SECRET);
    return payload as SessionPayload;
  } catch {
    return null;
  }
}
