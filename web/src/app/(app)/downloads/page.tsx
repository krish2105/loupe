import type { Metadata } from "next";
import { CollectionSurface } from "@/components/content/CollectionSurface";
import { DownloadsNotice } from "@/components/audio/DownloadsNotice";
import { getCollection } from "@/lib/collections";
import { getAccessToken } from "@/lib/supabase/server";

export const metadata: Metadata = { title: "Downloads" };
export const dynamic = "force-dynamic";

/**
 * Downloaded episodes (ADR 0003).
 *
 * The fifth surface built on the §6.2 collection abstraction, and the first one
 * the abstraction was not designed against. It cost a dictionary entry in the
 * API and this file — which is the claim §6.2 made in Phase 0, tested by
 * something written eleven phases later.
 */
export default async function DownloadsPage() {
  const token = await getAccessToken();
  const collection = await getCollection("downloads", token);

  return (
    <div>
      <CollectionSurface
        title={collection?.title ?? "Downloads"}
        emptyTitle={collection?.empty_title ?? "Nothing downloaded yet"}
        emptyBody={
          collection?.empty_body ??
          "Download an episode and it plays without a connection."
        }
        items={collection?.items ?? []}
        isSignedIn={Boolean(token)}
      />

      <DownloadsNotice />
    </div>
  );
}
