import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CollectionSurface } from "@/components/content/CollectionSurface";
import { getPlaylist } from "@/lib/collections";
import { getAccessToken } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const token = await getAccessToken();
  const playlist = await getPlaylist(id, token);
  return { title: playlist?.title ?? "Playlist" };
}

/**
 * One playlist.
 *
 * Renders through CollectionSurface like the other three — a playlist is the
 * same collection with a different membership rule and a forward ordering.
 */
export default async function PlaylistPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const token = await getAccessToken();

  if (!token) {
    return (
      <CollectionSurface
        title="Playlist"
        emptyTitle=""
        emptyBody=""
        items={[]}
        isSignedIn={false}
      />
    );
  }

  const playlist = await getPlaylist(id, token);
  if (!playlist) notFound();

  return (
    <div>
      <CollectionSurface
        title={playlist.title}
        emptyTitle="Nothing in this playlist yet"
        emptyBody="Add a talk from its page and it appears here, in the order you added it."
        items={playlist.items}
        isSignedIn
      />

      {/* §11: an AI playlist's output contract includes a written rationale for
          the ordering, so it is shown rather than stored and forgotten. */}
      {playlist.generated_by === "ai" && playlist.rationale && (
        <div className="mt-8 rounded-(--radius-md) border border-rule bg-surface p-4">
          <h2 className="text-(length:--step--1) font-medium">Why this order</h2>
          <p className="mt-2 text-pretty text-(length:--step--1) text-muted">
            {playlist.rationale}
          </p>
        </div>
      )}
    </div>
  );
}
