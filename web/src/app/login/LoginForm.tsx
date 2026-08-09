"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import { Wordmark } from "@/components/shell/Wordmark";
import { cn } from "@/lib/utils";

/**
 * Sign-in.
 *
 * Structure adapted from 21st.dev `ephraimduncan/login-03` (a permitted
 * primitive under §8.1 rule 2). Fully re-tokened per rule 3: every shadcn
 * token — bg-primary, text-foreground, text-muted-foreground, rounded-md — is
 * replaced with a Loupe token, which also removed the Radix Slot, Radix Label,
 * and cva dependencies the original carried. No component enters this codebase
 * with its own colour or spacing values.
 */

type Mode = "signin" | "signup";

const fieldStyles = cn(
  "mt-2 h-10 w-full rounded-(--radius-sm) border border-rule bg-canvas px-3",
  "text-(length:--step-0) text-ink placeholder:text-muted",
  "outline-none transition-colors focus:border-muted",
);

export function LoginForm() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);

    const supabase = createClient();
    if (!supabase) {
      setError(
        "Sign-in is not connected yet. Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY (or NEXT_PUBLIC_SUPABASE_ANON_KEY) to .env.local, then restart the dev server.",
      );
      return;
    }

    setPending(true);

    const result =
      mode === "signin"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({
            email,
            password,
            options: { emailRedirectTo: `${location.origin}/auth/callback` },
          });

    setPending(false);

    if (result.error) {
      setError(result.error.message);
      return;
    }

    if (mode === "signup" && !result.data.session) {
      setNotice("Check your email to confirm the address, then sign in.");
      return;
    }

    router.push("/");
    router.refresh();
  }

  return (
    <div className="flex min-h-dvh flex-col justify-center px-4 py-10">
      <div className="mx-auto w-full max-w-[380px]">
        <div className="flex flex-col items-center gap-3">
          <Wordmark variant="glyph" />
          <h1 className="text-center text-(length:--step-3)">
            {mode === "signin" ? "Sign in to Loupe" : "Create your account"}
          </h1>
          <p className="text-pretty text-center text-(length:--step--1) text-muted">
            Search inside talks, ask them questions, and keep your place.
          </p>
        </div>

        <form onSubmit={onSubmit} className="mt-8 space-y-4">
          <div>
            <label
              htmlFor="email"
              className="text-(length:--step--1) font-medium text-ink"
            >
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className={fieldStyles}
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="text-(length:--step--1) font-medium text-ink"
            >
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              className={fieldStyles}
            />
          </div>

          {/* Errors explain what went wrong and how to fix it. They do not
              apologise and they are never vague (§7.6). */}
          {error && (
            <p role="alert" className="text-(length:--step--1) text-danger">
              {error}
            </p>
          )}
          {notice && (
            <p role="status" className="text-(length:--step--1) text-muted">
              {notice}
            </p>
          )}

          <button
            type="submit"
            disabled={pending}
            className={cn(
              "h-10 w-full rounded-(--radius-sm) bg-ink text-canvas",
              "text-(length:--step-0) font-medium transition-opacity",
              "hover:opacity-90 disabled:opacity-60",
            )}
          >
            {/* An action keeps the same name through the whole flow (§7.6). */}
            {pending
              ? mode === "signin"
                ? "Signing in…"
                : "Creating account…"
              : mode === "signin"
                ? "Sign in"
                : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-(length:--step--1) text-muted">
          {mode === "signin" ? "No account yet?" : "Already have an account?"}{" "}
          <button
            type="button"
            onClick={() => {
              setMode(mode === "signin" ? "signup" : "signin");
              setError(null);
              setNotice(null);
            }}
            className="font-medium text-ink underline underline-offset-4"
          >
            {mode === "signin" ? "Create one" : "Sign in"}
          </button>
        </p>

        {!isSupabaseConfigured && (
          <p className="mt-8 rounded-(--radius-md) border border-rule bg-surface p-3 text-(length:--step--2) text-muted">
            Sign-in is not connected in this environment. Add the two Supabase
            keys to <code className="font-mono">.env.local</code> to enable it.
          </p>
        )}
      </div>
    </div>
  );
}
