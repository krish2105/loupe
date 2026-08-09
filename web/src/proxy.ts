import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { SUPABASE_ANON_KEY, SUPABASE_URL, isSupabaseConfigured } from "@/lib/supabase/config";

/**
 * Refreshes the auth session on every request.
 *
 * Supabase access tokens are short-lived. Without this the session expires
 * mid-visit and Server Components start seeing a signed-out user while the
 * browser still believes it is signed in.
 *
 * Next 16 renamed this convention from `middleware` to `proxy`. The Supabase
 * documentation still shows the old name, which is why this file does not
 * match it verbatim.
 */
export async function proxy(request: NextRequest) {
  if (!isSupabaseConfigured) return NextResponse.next();

  /*
    A confirmation link that landed somewhere other than /auth/callback.

    Sign-up asks Supabase to send people to `${origin}/auth/callback`, but
    Supabase ignores that unless the URL is in its allow-list, and falls back to
    the project's Site URL — which on a new project is `http://localhost:3000`.
    The link then arrives at `/?code=…`, the code is never exchanged, and the
    person is signed out with no explanation. Worse, on a machine running
    another project on port 3000, the link opens a different application
    entirely.

    Fixing the Site URL in the dashboard is the real fix and no code can do it
    from here. Forwarding the code is what stops a misconfiguration from eating
    a single-use link: the code is valid, it just arrived at the wrong door.
  */
  const code = request.nextUrl.searchParams.get("code");
  if (code && request.nextUrl.pathname === "/") {
    const callback = request.nextUrl.clone();
    callback.pathname = "/auth/callback";
    return NextResponse.redirect(callback);
  }

  let response = NextResponse.next({ request });

  const supabase = createServerClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        for (const { name, value } of cookiesToSet) {
          request.cookies.set(name, value);
        }
        response = NextResponse.next({ request });
        for (const { name, value, options } of cookiesToSet) {
          response.cookies.set(name, value, options);
        }
      },
    },
  });

  // Do not remove: this call is what performs the refresh.
  await supabase.auth.getUser();

  return response;
}

export const config = {
  matcher: [
    // Everything except static assets and image optimisation.
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|avif|woff2?)$).*)",
  ],
};
