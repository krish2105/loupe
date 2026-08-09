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
 *
 * Neither is a secret: both identify the project and carry no privileges beyond
 * what row-level security allows anonymously. The key that *is* a secret is
 * `service_role` (older) or `sb_secret_…` (newer), and this project never uses
 * one. If either ever appears in a `NEXT_PUBLIC_` variable it has been shipped
 * to every visitor.
 */
export const SUPABASE_ANON_KEY =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??
  "";

export const isSupabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
