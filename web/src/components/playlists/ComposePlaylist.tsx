"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { MarkNode } from "@/components/mark/Mark";
import { API_URL } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";

/**
 * Compose a playlist from a brief (§11).
 *
 * The refusal is the part worth designing. "Nothing in the catalogue covers
 * this well enough" is a correct answer, so it renders as an answer — plain
 * text in the normal colour — rather than as an error in amber. Treating it as
 * a failure would teach people that asking for something specific is a mistake,
 * which is the opposite of what the feature is for.
 */

const EXAMPLES = [
  "How attention scales with sequence length",
  "Where reinforcement learning from human feedback breaks down",
  "Making inference cheap enough to deploy",
];

type Result =
  | { kind: "refused"; reason: string }
  | { kind: "error"; message: string };

export function ComposePlaylist() {
  const router = useRouter();
  const [brief, setBrief] = useState("");
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<Result | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (pending || brief.trim().length < 8) return;

    setPending(true);
    setResult(null);

    try {
      const supabase = createClient();
      const token = supabase
        ? (await supabase.auth.getSession()).data.session?.access_token
        : null;

      if (!token || !API_URL) {
        setResult({ kind: "error", message: "Sign in to compose a playlist." });
        return;
      }

      const response = await fetch(`${API_URL}/v1/me/playlists/compose`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ brief: brief.trim() }),
      });

      if (!response.ok) {
        setResult({
          kind: "error",
          message:
            response.status === 503
              ? "Composition is unavailable right now. Try again shortly."
              : "That did not work. Try again.",
        });
        return;
      }

      const body = await response.json();

      if (body.refused) {
        setResult({ kind: "refused", reason: body.reason });
        return;
      }

      setBrief("");
      router.push(`/playlists/${body.id}`);
    } catch {
      setResult({ kind: "error", message: "That did not work. Try again." });
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="mt-6 rounded-(--radius-md) border border-rule bg-surface p-5">
      <h2 className="flex items-center gap-2 text-(length:--step-0) font-medium">
        <MarkNode label="Composed by Loupe" />
        Compose from a brief
      </h2>
      <p className="mt-1.5 max-w-[58ch] text-pretty text-(length:--step--1) text-muted">
        Describe what you want to understand. Loupe searches inside the talks,
        not their titles, and opens each one at the moment it addresses you.
      </p>

      <form onSubmit={submit} className="mt-4 flex flex-wrap gap-2">
        <label htmlFor="brief" className="sr-only">
          What do you want to understand?
        </label>
        <input
          id="brief"
          value={brief}
          onChange={(event) => setBrief(event.target.value)}
          placeholder="How attention scales with sequence length"
          maxLength={300}
          className={cn(
            "min-w-[16rem] flex-1 rounded-(--radius-pill) border border-rule bg-canvas",
            "px-4 py-2.5 text-(length:--step--1) text-ink",
            "placeholder:text-muted focus-visible:border-brand focus-visible:outline-none",
          )}
        />
        <button
          type="submit"
          disabled={pending || brief.trim().length < 8}
          className={cn(
            "rounded-(--radius-pill) bg-brand px-5 py-2.5 text-(length:--step--1)",
            "font-medium text-white transition-opacity hover:opacity-90",
            "disabled:opacity-40",
          )}
        >
          {pending ? "Composing…" : "Compose"}
        </button>
      </form>

      {result?.kind === "refused" && (
        <p className="mt-3 max-w-[58ch] text-pretty text-(length:--step--1)">
          {result.reason}
        </p>
      )}

      {result?.kind === "error" && (
        <p className="mt-3 text-(length:--step--1) text-danger">{result.message}</p>
      )}

      {!result && !pending && (
        <ul className="mt-4 flex flex-wrap gap-2">
          {EXAMPLES.map((example) => (
            <li key={example}>
              <button
                type="button"
                onClick={() => setBrief(example)}
                className={cn(
                  "rounded-(--radius-pill) border border-rule px-3 py-1.5",
                  "text-(length:--step--2) text-muted transition-colors",
                  "hover:border-brand hover:text-brand",
                )}
              >
                {example}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
