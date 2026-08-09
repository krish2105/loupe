import type { Metadata } from "next";
import { CollectionSurface } from "@/components/content/CollectionSurface";
import { getCollection } from "@/lib/collections";
import { getAccessToken } from "@/lib/supabase/server";

export const metadata: Metadata = { title: "Subscriptions" };
export const dynamic = "force-dynamic";

/**
 * Subscriptions.
 *
 * Thin on purpose. §6.2 puts the shared behaviour in one place; a page that
 * grows logic here is the first step back towards four one-offs.
 */
export default async function SubscriptionsPage() {
  const token = await getAccessToken();
  const collection = await getCollection("subscriptions", token);

  return (
    <CollectionSurface
      title="Subscriptions"
      emptyTitle={collection?.empty_title ?? "No subscriptions yet"}
      emptyBody={collection?.empty_body ?? "Follow a channel and its new talks land here."}
      items={collection?.items ?? []}
      isSignedIn={Boolean(token)}
    />
  );
}
