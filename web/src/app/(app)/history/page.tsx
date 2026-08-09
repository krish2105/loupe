import type { Metadata } from "next";
import { CollectionSurface } from "@/components/content/CollectionSurface";
import { getCollection } from "@/lib/collections";
import { getAccessToken } from "@/lib/supabase/server";

export const metadata: Metadata = { title: "History" };
export const dynamic = "force-dynamic";

export default async function HistoryPage() {
  const token = await getAccessToken();
  const collection = await getCollection("history", token);

  return (
    <CollectionSurface
      title="History"
      emptyTitle={collection?.empty_title ?? "Nothing watched yet"}
      emptyBody={
        collection?.empty_body ??
        "Talks you watch appear here, most recent first, so you can pick any of them back up."
      }
      items={collection?.items ?? []}
      isSignedIn={Boolean(token)}
    />
  );
}
