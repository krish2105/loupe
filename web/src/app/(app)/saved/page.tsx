import type { Metadata } from "next";
import Link from "next/link";
import { CollectionSurface } from "@/components/content/CollectionSurface";
import { getCollection, type CollectionKey } from "@/lib/collections";
import { getAccessToken } from "@/lib/supabase/server";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Saved" };
export const dynamic = "force-dynamic";

/**
 * Watch Later and Liked.
 *
 * Two collections, one route. §6.2 calls saved_items one table with two
 * semantics, and the surface follows the data: the same page with a filter,
 * rather than two pages that happen to look alike.
 */

const LISTS: { key: CollectionKey; label: string; href: string }[] = [
  { key: "watch_later", label: "Watch later", href: "/saved" },
  { key: "liked", label: "Liked", href: "/saved?list=liked" },
];

export default async function SavedPage({
  searchParams,
}: {
  searchParams: Promise<{ list?: string }>;
}) {
  const { list } = await searchParams;
  const active = list === "liked" ? "liked" : "watch_later";

  const token = await getAccessToken();
  const collection = await getCollection(active, token);

  const filters = (
    <nav aria-label="Which saved list" className="flex gap-2">
      {LISTS.map((entry) => {
        const isActive = entry.key === active;
        return (
          <Link
            key={entry.key}
            href={entry.href}
            aria-current={isActive ? "true" : undefined}
            className={cn(
              "rounded-(--radius-pill) border px-3.5 py-1.5",
              "text-(length:--step--1) transition-colors",
              isActive
                ? "border-screen bg-screen text-hall"
                : "border-rule bg-riser text-dust hover:text-screen",
            )}
          >
            {entry.label}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <CollectionSurface
      title={collection?.title ?? (active === "liked" ? "Liked" : "Watch later")}
      emptyTitle={collection?.empty_title ?? "Nothing saved yet"}
      emptyBody={
        collection?.empty_body ??
        "Save a talk from its page and it waits here until you have time for it."
      }
      items={collection?.items ?? []}
      isSignedIn={Boolean(token)}
      filters={filters}
    />
  );
}
