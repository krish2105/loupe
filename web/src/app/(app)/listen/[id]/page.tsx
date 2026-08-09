import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { AiPanel } from "@/components/ai/AiPanel";
import { DownloadButton } from "@/components/audio/DownloadButton";
import { PlayAllButton, QueueActions, RadioButton } from "@/components/audio/PlayControls";
import { TranscriptView } from "@/components/audio/TranscriptView";
import { Comments } from "@/components/content/Comments";
import { Avatar } from "@/components/shell/Avatar";
import { getRadio, getTranscript, type Episode } from "@/lib/audio";
import { getComments, getVideo } from "@/lib/catalogue";
import { getCurrentUser } from "@/lib/supabase/server";
import { formatAge, formatTimecode, formatViews } from "@/lib/utils";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const episode = await getVideo(id);
  return { title: episode?.title ?? "Episode" };
}

/**
 * One episode (ADR 0003).
 *
 * The video page with the player taken out. There is no media element here at
 * all — playback lives in the persistent bar, so navigating away from this page
 * does not interrupt the episode, which is the entire reason the player store
 * moved to the root layout.
 *
 * Everything below the header is the video page's own components, unchanged:
 * the AI panel, the comments. That reuse is the payoff of one `content_kind`
 * column instead of a parallel schema.
 */
export default async function EpisodePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const [episode, transcript, radio, comments, user] = await Promise.all([
    getVideo(id),
    getTranscript(id),
    getRadio(id),
    getComments(id),
    getCurrentUser(),
  ]);

  if (!episode) notFound();

  // getVideo returns the detail shape, which carries hls_url. The play controls
  // want the feed shape, and they are the same row.
  const asEpisode = episode as unknown as Episode;

  return (
    <div className="mx-auto grid max-w-[1100px] items-start gap-x-10 gap-y-8 py-6 lg:grid-cols-[minmax(0,1fr)_380px]">
      <div className="min-w-0 lg:col-start-1 lg:row-start-1">
        <div className="flex flex-wrap items-start gap-4">
          <Avatar name={episode.channel.name} size={72} />

          <div className="min-w-0 flex-1">
            <Link
              href={`/c/${episode.channel.handle}`}
              className="text-(length:--step--1) text-muted hover:underline"
            >
              {episode.channel.name}
            </Link>
            <h1 className="mt-1 text-pretty text-(length:--step-3)">
              {episode.title}
            </h1>
            <p className="mt-2 text-(length:--step--2) text-muted">
              {formatViews(episode.view_count)} · {formatAge(episode.published_at)}
              {episode.duration_sec
                ? ` · ${formatTimecode(episode.duration_sec)}`
                : ""}
            </p>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-2 border-y border-rule py-4">
          <PlayAllButton episodes={[asEpisode]} label="Play episode" />
          <RadioButton episodes={radio?.items ?? []} />
          <QueueActions episode={asEpisode} />
          <DownloadButton episode={asEpisode} />
        </div>

        {episode.description && (
          <p className="mt-5 text-pretty text-(length:--step--1) text-muted">
            {episode.description}
          </p>
        )}

        <div className="mt-8">
          <TranscriptView lines={transcript?.lines ?? []} />
        </div>

        <div className="mt-10">
          <Comments
            videoId={episode.id}
            comments={comments?.items ?? []}
            isSignedIn={Boolean(user)}
          />
        </div>
      </div>

      <div className="min-w-0 lg:col-start-2 lg:row-start-1">
        <AiPanel video={episode} />

        {(radio?.items.length ?? 0) > 0 && (
          <section className="mt-8" aria-labelledby="radio-heading">
            <h2
              id="radio-heading"
              className="text-(length:--step--1) font-medium text-muted"
            >
              {radio?.source === "similarity"
                ? "Similar episodes"
                : "More from this show"}
            </h2>
            {/* Named for what it is. video_similarity is content similarity, and
                calling this "for you" would be the overclaim the Phase 9
                writeup spends a page refusing to make. */}
            <ol className="mt-3 divide-y divide-rule border-y border-rule">
              {radio?.items.slice(0, 6).map((item) => (
                <li key={item.id} className="py-3">
                  <Link
                    href={`/listen/${item.id}`}
                    className="block text-pretty text-(length:--step--1) hover:underline"
                  >
                    {item.title}
                  </Link>
                  <p className="mt-1 text-(length:--step--2) text-muted">
                    {item.channel.name}
                    {item.duration_sec
                      ? ` · ${formatTimecode(item.duration_sec)}`
                      : ""}
                  </p>
                </li>
              ))}
            </ol>
          </section>
        )}
      </div>
    </div>
  );
}
