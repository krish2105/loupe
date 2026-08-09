import { ChipRow } from "@/components/content/ChipRow";
import { VideoCard } from "@/components/content/VideoCard";
import { MarkNode, MarkUnderline } from "@/components/mark/Mark";
import { Reveal } from "@/components/motion/Reveal";
import { getFeed } from "@/lib/catalogue";

/**
 * Home.
 *
 * §7.2: the thumbnail grid is the design and the chrome recedes. There is no
 * hero and no page heading — the catalogue is the first thing, because on a
 * video product anything above the grid is something between you and it.
 */

export const dynamic = "force-dynamic";

function ApiUnavailable() {
  return (
    <div className="mx-auto grid min-h-[70dvh] max-w-[560px] place-content-center py-16">
      <Reveal>
        <h1 className="text-(length:--step-4)">No talks yet</h1>
      </Reveal>
      <Reveal delay={0.06}>
        <p className="mt-4 text-pretty text-(length:--step-1) text-dust">
          Talks appear here newest first as they finish indexing. A talk becomes
          watchable long before it becomes searchable.
        </p>
      </Reveal>
      <Reveal delay={0.12}>
        <div className="mt-10 rounded-(--radius-md) border border-rule bg-riser p-5">
          <p className="text-(length:--step--1) text-dust">
            <MarkNode /> <span className="ml-1" />
            marks a talk you can search inside. Ask it a question and the answer
            cites the exact moment, like{" "}
            <MarkUnderline>this phrase from the transcript</MarkUnderline>,
            which seeks the player when clicked.
          </p>
        </div>
      </Reveal>
    </div>
  );
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ only?: string }>;
}) {
  const { only } = await searchParams;
  const filter = only === "searchable" ? "searchable" : "all";

  // Filtered by the API, not here: the client should never have to fetch 48
  // rows to display 6.
  const feed = await getFeed(48, {
    only: filter === "searchable" ? "searchable" : undefined,
  });

  // The API is not deployed yet, so this is a routine state rather than a fault.
  if (!feed) return <ApiUnavailable />;

  const items = feed.items;

  return (
    <div className="py-6">
      <ChipRow active={filter} />

      {items.length === 0 ? (
        <div className="mt-16 text-center">
          <p className="text-(length:--step-1)">Nothing indexed yet</p>
          <p className="mx-auto mt-2 max-w-[46ch] text-pretty text-(length:--step--1) text-dust">
            Talks become searchable once transcription and indexing finish.
            Everything in the catalogue is still watchable in the meantime.
          </p>
        </div>
      ) : (
        <div
          className="mt-6 grid gap-x-4 gap-y-8"
          style={{
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          }}
        >
          {items.map((video) => (
            <VideoCard key={video.id} video={video} />
          ))}
        </div>
      )}
    </div>
  );
}
