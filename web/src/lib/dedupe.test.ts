// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("./db", () => ({
  prisma: {
    user: {
      findUnique: vi.fn(),
    },
    trialRecord: {
      findFirst: vi.fn(),
    },
  },
}));

import { prisma } from "./db";
import { isEmailTaken, isRepeatIp } from "./dedupe";

const mockUser = prisma.user as unknown as {
  findUnique: ReturnType<typeof vi.fn>;
};
const mockTrialRecord = prisma.trialRecord as unknown as {
  findFirst: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("isEmailTaken", () => {
  it("returns false when no user exists", async () => {
    mockUser.findUnique.mockResolvedValue(null);
    await expect(isEmailTaken("new@example.com")).resolves.toBe(false);
    expect(mockUser.findUnique).toHaveBeenCalledWith({
      where: { email: "new@example.com" },
    });
  });

  it("returns true when user exists (duplicate email blocked)", async () => {
    mockUser.findUnique.mockResolvedValue({ id: "u1", email: "taken@example.com" });
    await expect(isEmailTaken("taken@example.com")).resolves.toBe(true);
  });
});

describe("isRepeatIp", () => {
  it("returns false when IP has no prior signups", async () => {
    mockTrialRecord.findFirst.mockResolvedValue(null);
    await expect(isRepeatIp("1.2.3.4")).resolves.toBe(false);
    expect(mockTrialRecord.findFirst).toHaveBeenCalledWith({
      where: { signupIp: "1.2.3.4" },
    });
  });

  it("returns true when IP already has a trial record (repeat IP flagged)", async () => {
    mockTrialRecord.findFirst.mockResolvedValue({
      id: "t1",
      signupIp: "1.2.3.4",
    });
    await expect(isRepeatIp("1.2.3.4")).resolves.toBe(true);
  });
});
