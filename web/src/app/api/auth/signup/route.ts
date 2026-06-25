import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { hashPassword, generateToken, getClientIp } from "@/lib/auth";
import { isEmailTaken, isRepeatIp } from "@/lib/dedupe";
import { sendVerificationEmail } from "@/lib/email";
import { checkRateLimit } from "@/lib/rate-limit";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const { email, password } = body as { email?: string; password?: string };

  if (!email || typeof email !== "string" || !email.includes("@")) {
    return NextResponse.json({ error: "Valid email required" }, { status: 400 });
  }
  if (!password || typeof password !== "string" || password.length < 8) {
    return NextResponse.json({ error: "Password must be at least 8 characters" }, { status: 400 });
  }

  const clientIp = getClientIp(req);

  // 5 signup attempts per IP per minute
  if (!checkRateLimit(`signup:${clientIp}`, 5, 5 / 60)) {
    return NextResponse.json({ error: "Too many requests" }, { status: 429 });
  }

  if (await isEmailTaken(email)) {
    return NextResponse.json({ error: "Email already registered" }, { status: 409 });
  }

  if (await isRepeatIp(clientIp)) {
    return NextResponse.json(
      { error: "A trial account already exists from this network" },
      { status: 409 }
    );
  }

  const passwordHash = await hashPassword(password);
  const verifyToken = generateToken();
  const verifyTokenExpiry = new Date(Date.now() + 24 * 60 * 60 * 1000);

  const user = await prisma.user.create({
    data: {
      email,
      passwordHash,
      verifyToken,
      verifyTokenExpiry,
      trialRecord: {
        create: { email, signupIp: clientIp },
      },
    },
  });

  try {
    await sendVerificationEmail(email, verifyToken);
  } catch (err) {
    console.error("Failed to send verification email:", err);
  }

  const body2: Record<string, unknown> = {
    success: true,
    message: "Check your email to verify your account",
  };
  // Expose token only in test mode so Playwright can complete the flow
  if (process.env.NODE_ENV === "test") {
    body2.verifyToken = verifyToken;
    body2.userId = user.id;
  }

  return NextResponse.json(body2, { status: 201 });
}
