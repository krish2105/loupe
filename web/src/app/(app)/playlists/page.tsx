import type { Metadata } from "next";
import Link from "next/link";
import { MarkNode } from "@/components/mark/Mark";
import { ComposePlaylist } from "@/components/playlists/ComposePlaylist";
import { getPlaylists } from "@/lib/collections";
import { getAccessToken } from "@/lib/supabase/server";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Playlists" };
export const dynamic = "force-dynamic";

/**
 * Playlists.
 *
 * The one surface of the four that lists *lists* rather than talks, which is
 * why it does not use CollectionSurface — forcing it through the same component
 * would have meant a component that renders two unrelated things. Each
 * individual playlist does go through the shared collection loader, which is
 * where the reuse actually belongs.
 */
export default async function PlaylistsPage() {
  const token = await getAccessToken();
  const playlists = await getPlaylists(token);

  if (!token) {
    return (
      <div className="mx-auto max-w-[46ch] py-24 text-center">
        <h1 className="text-(length:--step-3)">Playlists</h1>
        <p className="mt-3 text-pretty text-(length:--step--1) text-muted">
          This is yours, so it needs an account.
        </p>
        <Link
          href="/login"
          className={cn(
            "mt-6 inline-block rounded-(--radius-sm) bg-ink px-4 py-2",
            "text-(length:--step--1) font-medium text-canvas hover:opacity-90",
          )}
        >
          Sign in
        </Link>
      </div>
    );
  }

  const items = playlists?.items ?? [];

  return (
    <div className="py-6">
      <h1 className="text-(length:--step-3)">Playlists</h1>

      <ComposePlaylist />

      {items.length === 0 ? (
        <div className="mx-auto max-w-[46ch] py-24 text-center">
          <p className="text-(length:--step-1)">No playlists yet</p>
          <p className="mt-2 text-pretty text-(length:--step--1) text-muted">
            Compose one from a brief above, or save a talk to a playlist from
            its own page.
          </p>
        </div>
      ) : (
        <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((playlist) => (
            <li key={playlist.id}>
              <Link
                href={`/playlists/${playlist.id}`}
                className={cn(
                  "block rounded-(--radius-md) border border-rule bg-surface p-4",
                  "transition-colors hover:border-muted",
                )}
              >
                <p className="flex items-center gap-2 text-(length:--step-0) font-medium">
                  {/* An AI-composed playlist is marked, never passed off as
                      hand-made. §12.2: the disclosure is the professional
                      signal. */}
                  {playlist.generated_by === "ai" && <MarkNode label="Composed by Loupe" />}
                  {playlist.title}
                </p>
                <p className="mt-1 text-(length:--step--1) text-muted">
                  {playlist.item_count} talk
                  {playlist.item_count === 1 ? "" : "s"}
                </p>
                {playlist.rationale && (
                  <p className="mt-3 line-clamp-3 text-pretty text-(length:--step--2) text-muted">
                    {playlist.rationale}
                  </p>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
