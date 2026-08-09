/**
 * Supabase configuration, read once.
 *
 * The app has to build and run with no credentials at all and say plainly that
 * sign-in is unavailable, rather than throwing at import time — §7.6: errors
 * explain what went wrong and how to fix it. Local development uses the
 * identity provider in services/auth (ADR 0004), which speaks the same API, so
 * these two variables point at it instead.
 */

export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";

/**
 * The browser-safe key.
 *
 * Two names, because Supabase renamed this. Projects created before the change
 * issue a JWT called the *anon* key; newer ones issue `sb_publishable_…` and
 * the dashboard writes it as `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. They are
 * the same thing in the same position — `createBrowserClient`'s second argument
 * — so this accepts either rather than making someone rename a variable to
 * match a file they did not write.
 */
const CONFIGURED_KEY =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??
  "";

/**
 * Whether the key is the browser-safe one.
 *
 * This exists because the wrong value was pasted here once and the consequence
 * was severe enough to be worth a guard. Supabase's API settings page lists
 * several long opaque strings and only one of them belongs in a `NEXT_PUBLIC_`
 * variable. Two of the others are secrets:
 *
 *   - the **JWT secret** signs every access token. Published, anyone can mint a
 *     valid token for any account.
 *   - the **service_role** / `sb_secret_…` key bypasses row-level security
 *     entirely.
 *
 * `NEXT_PUBLIC_` values are inlined into the JavaScript bundle and served to
 * every visitor, so pasting either of those here does not fail quietly — it
 * publishes them. Supabase answers a wrong key with "Invalid API key", which
 * says nothing about which value was used or what it now costs.
 *
 * The browser-safe key is recognisable: `sb_publishable_…` on newer projects, a
 * JWT beginning `eyJ` on older ones. Anything else is refused here rather than
 * shipped.
 */
function keyProblem(key: string): string | null {
  if (!key) return null;
  if (key.startsWith("sb_publishable_") || key.startsWith("eyJ")) return null;

  if (key.startsWith("sb_secret_") || key.startsWith("service_role")) {
    return (
      "That is the secret key, which bypasses row-level security. It must " +
      "never be in a NEXT_PUBLIC_ variable. Rotate it, then use the " +
      "publishable key."
    );
  }

  return (
    "That does not look like the publishable key — it may be the JWT secret, " +
    "which signs access tokens. If it has been deployed, rotate it in " +
    "Supabase → JWT Keys and update SUPABASE_JWT_SECRET, then use the " +
    "publishable key (sb_publishable_…) here."
  );
}

export const SUPABASE_KEY_PROBLEM = keyProblem(CONFIGURED_KEY);

export const SUPABASE_ANON_KEY = SUPABASE_KEY_PROBLEM ? "" : CONFIGURED_KEY;

export const isSupabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
