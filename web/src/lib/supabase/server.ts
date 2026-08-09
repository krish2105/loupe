import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { SUPABASE_ANON_KEY, SUPABASE_URL, isSupabaseConfigured } from "./config";

/**
 * Supabase client for Server Components, Route Handlers, and Server Actions.
 *
 * Returns null when unconfigured so callers decide what to show. A thrown error
 * here would take down every page, including the ones that do not need auth.
 */
export async function createClient() {
  if (!isSupabaseConfigured) return null;

  const cookieStore = await cookies();

  return createServerClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) {
            cookieStore.set(name, value, options);
          }
        } catch {
          // Server Components cannot set cookies. The middleware refreshes the
          // session instead, so this is safe to swallow — it is the documented
          // pattern, not a silent failure.
        }
      },
    },
  });
}

/**
 * The access token to forward to the core API, or null.
 *
 * getSession() is the right call here, unlike for authorisation: this token is
 * not being trusted, only relayed. The API verifies it against the Supabase
 * JWT secret before acting on it, so a forged cookie buys nothing.
 */
export async function getAccessToken(): Promise<string | null> {
  const supabase = await createClient();
  if (!supabase) return null;

  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

/** The signed-in user, or null. Never throws. */
export async function getCurrentUser() {
  const supabase = await createClient();
  if (!supabase) return null;

  // getUser() revalidates against the auth server; getSession() trusts the
  // cookie, which is spoofable. Always getUser() on the server.
  const { data, error } = await supabase.auth.getUser();
  return error ? null : data.user;
}
