/** Returns a fully-qualified base URL from NEXTAUTH_URL, adding https:// when
 *  the env var is set to a bare hostname (e.g. "app.example.com"). */
export function getBaseUrl(): string {
  const raw = process.env.NEXTAUTH_URL || "http://localhost:3000";
  if (/^https?:\/\//i.test(raw)) return raw;
  return `https://${raw}`;
}
