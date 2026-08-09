import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { AiPanel } from "@/components/ai/AiPanel";
import { Comments } from "@/components/content/Comments";
import { Description } from "@/components/content/Description";
import { VideoCard } from "@/components/content/VideoCard";
import { PlayerProvider } from "@/components/player/PlayerContext";
import { VideoPlayer } from "@/components/player/VideoPlayer";
import { VideoActions } from "@/components/actions/VideoActions";
import { getComments, getRelated, getVideo } from "@/lib/catalogue";
import { getVideoState } from "@/lib/collections";
import { getAccessToken, getCurrentUser } from "@/lib/supabase/server";
import { formatAge, formatViews } from "@/lib/utils";

/**
 * The video page — §9, "the product", which is why it gets the most
 * specification effort.
 *
 * Regions: player · title and action bar · channel strip · description ·
 * AI panel · comments · related rail.
 *
 * Below lg the AI panel moves inline above the comments and the related rail
 * drops beneath them, per §9.
 */

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const video = await getVideo(id);
  return { title: video?.title ?? "Talk" };
}

/**
 * Class B playback (§9.1): the custom player is swapped for the third-party
 * embed and the custom controls hide. There is no embed to show until the
 * ingest phase supplies one, so this states the situation instead of rendering
 * a broken frame.
 */
function ReferencedPlayback() {
  return (
    <div className="grid aspect-video w-full place-content-center rounded-(--radius-md) border border-rule bg-riser px-6 text-center">
      <p className="text-(length:--step-0)">Plays at the original source</p>
      <p className="mx-auto mt-2 max-w-[44ch] text-pretty text-(length:--step--1) text-dust">
        Loupe lists this talk but does not host it, so playback happens on the
        original platform.
      </p>
    </div>
  );
}

function ProcessingPlayback() {
  return (
    <div className="grid aspect-video w-full place-content-center rounded-(--radius-md) border border-rule bg-riser px-6 text-center">
      <p className="text-(length:--step-0)">Still processing</p>
      <p className="mx-auto mt-2 max-w-[44ch] text-pretty text-(length:--step--1) text-dust">
        This talk is being prepared for playback. It will appear here shortly.
      </p>
    </div>
  );
}

export default async function WatchPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const token = await getAccessToken();

  const [video, related, comments, user, state] = await Promise.all([
    getVideo(id),
    getRelated(id, 8),
    getComments(id),
    getCurrentUser(),
    getVideoState(id, token),
  ]);

  if (!video) notFound();

  const canPlay = video.capabilities.playable && video.hls_url;

  const aiPanel = <AiPanel video={video} />;
  const relatedRail = (
    <section aria-labelledby="related-heading">
      <h2 id="related-heading" className="text-(length:--step--1) font-medium text-dust">
        More talks
      </h2>
      <div className="mt-4 space-y-4">
        {(related?.items ?? []).map((item) => (
          <VideoCard key={item.id} video={item} density="row" />
        ))}
      </div>
    </section>
  );

  return (
    <PlayerProvider>
      {/*
        One DOM instance of everything, repositioned by grid placement.

        The obvious way to do this is to render the panel and rail twice and
        hide one copy per breakpoint. That was the first version, and it was
        wrong twice over: it duplicated `id="related-heading"` and
        `id="comments-heading"`, which silently breaks every aria-labelledby
        pointing at them, and it rendered the related rail's cards twice.

        DOM order is the mobile order §9 specifies — panel above the
        conversation, rail below it. Grid placement moves the panel and rail
        into the side column at lg without touching the markup.
      */}
      <div className="grid items-start gap-x-8 gap-y-8 py-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 lg:col-start-1 lg:row-start-1">
          {canPlay ? (
            <VideoPlayer
              src={video.hls_url!}
              title={video.title}
              videoId={video.id}
            />
          ) : video.source_class === "referenced" ? (
            <ReferencedPlayback />
          ) : (
            <ProcessingPlayback />
          )}

          <h1 className="mt-5 text-(length:--step-3)">{video.title}</h1>

          <p className="mt-2 text-(length:--step--1) text-dust">
            {formatViews(video.view_count)} ·{" "}
            {formatAge(video.published_at)}
          </p>

          {/* Channel strip and action bar (§9) */}
          <div className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-4 border-y border-rule py-4">
            <span
              aria-hidden="true"
              className="grid size-10 shrink-0 place-items-center rounded-full border border-rule bg-riser font-mono text-(length:--step--1) text-dust"
            >
              {video.channel.name.slice(0, 1)}
            </span>
            <div className="min-w-0">
              <Link
                href={`/c/${video.channel.handle}`}
                className="block truncate text-(length:--step-0) font-medium hover:text-dust"
              >
                {video.channel.name}
              </Link>
              <p className="text-(length:--step--2) text-dust">
                @{video.channel.handle}
              </p>
            </div>

            <div className="ml-auto">
              <VideoActions
                videoId={video.id}
                channelId={video.channel.id}
                initialState={state}
                isSignedIn={Boolean(user)}
              />
            </div>
          </div>

          {video.description && (
            <div className="mt-5">
              <Description text={video.description} />
            </div>
          )}

        </div>

        <div className="min-w-0 lg:col-start-2 lg:row-start-1">{aiPanel}</div>

        <div className="min-w-0 lg:col-start-1 lg:row-start-2">
          <Comments
            videoId={video.id}
            comments={comments?.items ?? []}
            isSignedIn={Boolean(user)}
          />
        </div>

        <div className="min-w-0 lg:col-start-2 lg:row-start-2">{relatedRail}</div>
      </div>
    </PlayerProvider>
  );
}
