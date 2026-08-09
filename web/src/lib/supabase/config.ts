/**
 * Supabase configuration, read once.
 *
 * Phase 0 is developed against local Postgres with no hosted Supabase project
 * (no Docker on the build machine, so `supabase start` is unavailable). The app
 * therefore has to build and run without credentials and say plainly that
 * sign-in is unavailable, rather than throwing at import time — §7.6: errors
 * explain what went wrong and how to fix it.
 */

export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export const isSupabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
