import { prisma } from "./db";

export async function isEmailTaken(email: string): Promise<boolean> {
  const user = await prisma.user.findUnique({ where: { email } });
  return user !== null;
}

export async function isRepeatIp(ip: string): Promise<boolean> {
  const record = await prisma.trialRecord.findFirst({ where: { signupIp: ip } });
  return record !== null;
}
