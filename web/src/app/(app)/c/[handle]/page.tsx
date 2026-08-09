import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { VideoCard } from "@/components/content/VideoCard";
import { getChannel } from "@/lib/catalogue";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ handle: string }>;
}): Promise<Metadata> {
  const { handle } = await params;
  const data = await getChannel(handle);
  return { title: data?.channel.name ?? "Channel" };
}

export default async function ChannelPage({
  params,
}: {
  params: Promise<{ handle: string }>;
}) {
  const { handle } = await params;
  const data = await getChannel(handle);

  if (!data) notFound();

  const { channel, videos } = data;
  const searchableCount = videos.filter((v) => v.capabilities.askable).length;

  return (
    <div className="py-6">
      <header className="flex flex-wrap items-center gap-4 border-b border-rule pb-6">
        <span
          aria-hidden="true"
          className="grid size-16 shrink-0 place-items-center rounded-full border border-rule bg-surface font-display text-(length:--step-2) text-muted"
        >
          {channel.name.slice(0, 1)}
        </span>

        <div className="min-w-0">
          <h1 className="text-(length:--step-3)">{channel.name}</h1>
          <p className="mt-1 text-(length:--step--1) text-muted">
            @{channel.handle} · {videos.length} talk
            {videos.length === 1 ? "" : "s"}
            {/* Say how much of this channel is searchable, because on a
                referenced channel the answer is none of it and that is the
                thing worth knowing. */}
            {searchableCount > 0 && ` · ${searchableCount} searchable`}
          </p>
        </div>
      </header>

      {channel.description && (
        <p className="mt-5 max-w-[70ch] text-pretty text-(length:--step-0) text-muted">
          {channel.description}
        </p>
      )}

      {videos.length === 0 ? (
        <p className="mt-16 text-center text-(length:--step--1) text-muted">
          This channel has no talks yet.
        </p>
      ) : (
        <div
          className="mt-8 grid gap-x-4 gap-y-8"
          style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}
        >
          {videos.map((video) => (
            <VideoCard key={video.id} video={video} />
          ))}
        </div>
      )}
    </div>
  );
}
