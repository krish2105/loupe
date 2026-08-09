import type { Metadata } from "next";
import Link from "next/link";
import { DownloadButton } from "@/components/audio/DownloadButton";
import { PlayAllButton, QueueActions } from "@/components/audio/PlayControls";
import { Avatar } from "@/components/shell/Avatar";
import { getEpisodes } from "@/lib/audio";
import { cn, formatAge, formatTimecode } from "@/lib/utils";

export const metadata: Metadata = { title: "Listen" };
export const dynamic = "force-dynamic";

/**
 * The audio feed (ADR 0003).
 *
 * A list rather than the thumbnail grid the video feed uses, and that is the
 * one visual decision audio mode actually needed. Episode artwork is the show's
 * artwork, so a grid of episodes from two shows is a grid of the same two
 * images repeated, carrying no information and taking most of the screen. A
 * list puts the title first, which is the only thing that distinguishes one
 * episode from another.
 */
export default async function ListenPage() {
  const data = await getEpisodes();
  const episodes = data?.items ?? [];

  const shows = new Map(
    episodes.map((episode) => [episode.channel.handle, episode.channel]),
  );

  return (
    <div className="mx-auto max-w-[900px] py-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-(length:--step-3)">Listen</h1>
          <p className="mt-1 text-(length:--step--1) text-muted">
            Spoken audio, with everything the talks get: search inside, ask it a
            question, jump to the moment.
          </p>
        </div>

        {episodes.length > 0 && <PlayAllButton episodes={episodes} />}
      </div>

      {episodes.length === 0 ? (
        <div className="mx-auto max-w-[46ch] py-24 text-center">
          <p className="text-(length:--step-1)">Nothing to listen to yet</p>
          <p className="mt-2 text-pretty text-(length:--step--1) text-muted">
            Seed the audio catalogue and run the pipeline over it, and episodes
            appear here.
          </p>
        </div>
      ) : (
        <>
          <section className="mt-8">
            <h2 className="text-(length:--step--1) font-medium text-muted">Shows</h2>
            <ul className="mt-3 flex flex-wrap gap-3">
              {[...shows.values()].map((show) => (
                <li key={show.handle}>
                  <Link
                    href={`/c/${show.handle}`}
                    className={cn(
                      "flex items-center gap-2 rounded-(--radius-pill) border border-rule",
                      "py-1.5 pl-1.5 pr-4 transition-colors hover:border-brand",
                    )}
                  >
                    <Avatar name={show.name} size={28} />
                    <span className="text-(length:--step--1)">{show.name}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>

          <ol className="mt-8 divide-y divide-rule border-y border-rule">
            {episodes.map((episode, index) => (
              <li
                key={episode.id}
                className="flex flex-wrap items-center gap-x-4 gap-y-2 py-4"
              >
                <span className="w-6 shrink-0 font-mono text-(length:--step--2) text-muted tabular-nums">
                  {index + 1}
                </span>

                <div className="min-w-0 flex-1">
                  <Link
                    href={`/listen/${episode.id}`}
                    className="block text-pretty text-(length:--step-0) font-medium hover:underline"
                  >
                    {episode.title}
                  </Link>
                  <p className="mt-1 text-(length:--step--2) text-muted">
                    {episode.channel.name} · {formatAge(episode.published_at)}
                    {episode.duration_sec
                      ? ` · ${formatTimecode(episode.duration_sec)}`
                      : ""}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <PlayAllButton
                    episodes={episodes}
                    startAt={index}
                    label="Play"
                  />
                  <QueueActions episode={episode} />
                  <DownloadButton episode={episode} />
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
