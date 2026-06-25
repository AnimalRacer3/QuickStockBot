// @vitest-environment node
import { describe, it, expect, vi } from "vitest";
import {
  buildLicenseEmail,
  sendLicenseEmail,
  type ResendClient,
  type LicenseEmailPayload,
} from "../email";

const BASE_PAYLOAD: LicenseEmailPayload = {
  to: "user@example.com",
  name: "Alice",
  licenseKey: "QSB-ABCD-1234-EFGH-5678",
  downloadUrl: "https://download.quickstockbot.com/bot/latest",
};

// ── buildLicenseEmail ───────────────────────────────────────────────────────

describe("buildLicenseEmail", () => {
  it("subject is non-empty", () => {
    const { subject } = buildLicenseEmail(BASE_PAYLOAD);
    expect(subject.length).toBeGreaterThan(5);
  });

  it("text body contains the license key", () => {
    const { text } = buildLicenseEmail(BASE_PAYLOAD);
    expect(text).toContain("QSB-ABCD-1234-EFGH-5678");
  });

  it("html body contains the license key", () => {
    const { html } = buildLicenseEmail(BASE_PAYLOAD);
    expect(html).toContain("QSB-ABCD-1234-EFGH-5678");
  });

  it("html body contains the download URL", () => {
    const { html } = buildLicenseEmail(BASE_PAYLOAD);
    expect(html).toContain("https://download.quickstockbot.com/bot/latest");
  });

  it("text body contains the download URL", () => {
    const { text } = buildLicenseEmail(BASE_PAYLOAD);
    expect(text).toContain("https://download.quickstockbot.com/bot/latest");
  });

  it("greets the user by name when name is provided", () => {
    const { text } = buildLicenseEmail(BASE_PAYLOAD);
    expect(text).toContain("Hi Alice");
  });

  it("uses a generic greeting when name is null", () => {
    const { text } = buildLicenseEmail({ ...BASE_PAYLOAD, name: null });
    expect(text).toContain("Hi,");
  });

  it("includes setup step referencing the license key in html", () => {
    const { html } = buildLicenseEmail(BASE_PAYLOAD);
    expect(html).toContain("LICENSE_KEY=QSB-ABCD-1234-EFGH-5678");
  });

  it("includes setup step referencing the license key in text", () => {
    const { text } = buildLicenseEmail(BASE_PAYLOAD);
    expect(text).toContain("LICENSE_KEY=QSB-ABCD-1234-EFGH-5678");
  });
});

// ── sendLicenseEmail ────────────────────────────────────────────────────────

describe("sendLicenseEmail", () => {
  function makeMockClient(
    response: Awaited<ReturnType<ResendClient["emails"]["send"]>>
  ): ResendClient {
    return { emails: { send: vi.fn().mockResolvedValue(response) } };
  }

  it("returns the email id on success", async () => {
    const client = makeMockClient({ data: { id: "email-abc123" }, error: null });
    const result = await sendLicenseEmail(client, BASE_PAYLOAD);
    expect(result.id).toBe("email-abc123");
  });

  it("calls Resend with the recipient address", async () => {
    const client = makeMockClient({ data: { id: "x" }, error: null });
    await sendLicenseEmail(client, BASE_PAYLOAD);
    const call = (client.emails.send as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(call.to).toBe("user@example.com");
  });

  it("sends html containing the license key", async () => {
    const client = makeMockClient({ data: { id: "x" }, error: null });
    await sendLicenseEmail(client, BASE_PAYLOAD);
    const call = (client.emails.send as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(call.html).toContain("QSB-ABCD-1234-EFGH-5678");
  });

  it("sends plain text containing the license key", async () => {
    const client = makeMockClient({ data: { id: "x" }, error: null });
    await sendLicenseEmail(client, BASE_PAYLOAD);
    const call = (client.emails.send as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(call.text).toContain("QSB-ABCD-1234-EFGH-5678");
  });

  it("throws when Resend returns an error", async () => {
    const client = makeMockClient({
      data: null,
      error: { message: "rate limited" },
    });
    await expect(sendLicenseEmail(client, BASE_PAYLOAD)).rejects.toThrow("rate limited");
  });

  it("throws when Resend returns null data with no error message", async () => {
    const client = makeMockClient({ data: null, error: null });
    await expect(sendLicenseEmail(client, BASE_PAYLOAD)).rejects.toThrow(
      "Failed to send license email"
    );
  });
});
