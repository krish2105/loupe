import type { Metadata } from "next";
import { VideoCard } from "@/components/content/VideoCard";
import { MarkNode } from "@/components/mark/Mark";
import { API_URL } from "@/lib/api";
import type { VideoSummary } from "@/lib/catalogue";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}): Promise<Metadata> {
  const { q } = await searchParams;
  return { title: q ? `${q} — search` : "Search" };
}

type SearchResponse = {
  query: string;
  items: VideoSummary[];
  mode: "keyword" | "semantic";
};

async function runSearch(q: string): Promise<SearchResponse | null> {
  if (!API_URL) return null;
  try {
    const response = await fetch(
      `${API_URL}/v1/search?q=${encodeURIComponent(q)}`,
      { cache: "no-store" },
    );
    if (!response.ok) return null;
    return (await response.json()) as SearchResponse;
  } catch {
    return null;
  }
}

/**
 * Search results.
 *
 * Keyword-only today, and it says so. §11's contract for semantic search is
 * that it degrades to keyword and the degradation is *flagged in the UI* —
 * so the flag exists from the first version rather than being added once
 * there is something to degrade from.
 */
export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  const query = (q ?? "").trim();

  if (!query) {
    return (
      <div className="mx-auto max-w-[52ch] py-24 text-center">
        <h1 className="text-(length:--step-3)">Search</h1>
        <p className="mt-3 text-pretty text-(length:--step--1) text-muted">
          Find a talk by its title, its channel, or what it is about.
        </p>
      </div>
    );
  }

  const results = await runSearch(query);
  const items = results?.items ?? [];

  return (
    <div className="py-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3 border-b border-rule pb-4">
        <h1 className="text-(length:--step-2)">
          {items.length} result{items.length === 1 ? "" : "s"} for{" "}
          <span className="font-medium">{query}</span>
        </h1>

        {/* The honest label. When Phase 6 lands, this flips to "searching
            inside transcripts" and the difference is visible to the person
            using it rather than only in a changelog. */}
        <p className="inline-flex items-center gap-2 text-(length:--step--2) text-muted">
          <MarkNode />
          Matching titles and descriptions. Searching inside talks is not on yet.
        </p>
      </div>

      {items.length === 0 ? (
        <div className="mx-auto max-w-[46ch] py-24 text-center">
          <p className="text-(length:--step-1)">Nothing matched</p>
          <p className="mt-2 text-pretty text-(length:--step--1) text-muted">
            Try fewer words, or a channel name.
          </p>
        </div>
      ) : (
        <div
          className="mt-6 grid gap-x-4 gap-y-8"
          style={{ gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}
        >
          {items.map((video, index) => (
            <VideoCard key={video.id} video={video} priority={index < 4} />
          ))}
        </div>
      )}
    </div>
  );
}
