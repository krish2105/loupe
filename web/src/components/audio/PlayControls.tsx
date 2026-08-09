"use client";

import { Icon } from "@/components/shell/Icon";
import type { Episode } from "@/lib/audio";
import { useQueueControls, type QueueTrack } from "./QueueContext";
import { usePlayerControls } from "@/components/player/PlayerContext";
import { cn } from "@/lib/utils";

/**
 * Play, play next, add to queue, and radio (ADR 0003).
 *
 * The conversion from an API episode to a queue track happens here rather than
 * in the queue, because the queue should not know what shape this API returns.
 */

export function toTrack(episode: Episode): QueueTrack {
  return {
    id: episode.id,
    title: episode.title,
    channelName: episode.channel.name,
    channelHandle: episode.channel.handle,
    durationSec: episode.duration_sec,
    src: episode.hls_url ?? "",
  };
}

export function PlayAllButton({
  episodes,
  startAt = 0,
  label = "Play all",
}: {
  episodes: Episode[];
  startAt?: number;
  label?: string;
}) {
  const { playNow } = useQueueControls();
  const { play } = usePlayerControls();

  const playable = episodes.filter((episode) => episode.hls_url);

  return (
    <button
      type="button"
      disabled={playable.length === 0}
      onClick={() => {
        playNow(playable.map(toTrack), startAt);
        // The store holds a play requested before the source is attached, the
        // same way it holds a seek requested before metadata (§5.1), so this
        // does not need to wait for the manifest.
        void play();
      }}
      className={cn(
        "flex items-center gap-2 rounded-(--radius-pill) bg-brand px-4 py-2",
        "text-(length:--step--1) font-medium text-white transition-opacity",
        "hover:opacity-90 disabled:opacity-40",
      )}
    >
      <Icon name="play" className="size-4" />
      {label}
    </button>
  );
}

export function QueueActions({ episode }: { episode: Episode }) {
  const { playNext, addToQueue } = useQueueControls();

  if (!episode.hls_url) return null;

  return (
    <div className="flex items-center gap-1">
      <SmallButton label="Play next" onClick={() => playNext(toTrack(episode))}>
        Play next
      </SmallButton>
      <SmallButton label="Add to queue" onClick={() => addToQueue(toTrack(episode))}>
        <Icon name="queue" className="size-4" />
      </SmallButton>
    </div>
  );
}

/**
 * Radio: a queue built outward from this episode.
 *
 * Labelled "similar episodes" rather than "for you" when the API says the
 * source was content similarity, and never labelled as personalised, because
 * `video_similarity` is content similarity and calling it a recommendation
 * would be the same overclaim the Phase 9 writeup spends a page refusing to
 * make.
 */
export function RadioButton({ episodes }: { episodes: Episode[] }) {
  const { playNow } = useQueueControls();
  const { play } = usePlayerControls();

  const playable = episodes.filter((episode) => episode.hls_url);
  if (playable.length === 0) return null;

  return (
    <button
      type="button"
      onClick={() => {
        playNow(playable.map(toTrack), 0);
        void play();
      }}
      className={cn(
        "flex items-center gap-2 rounded-(--radius-pill) border border-rule px-4 py-2",
        "text-(length:--step--1) font-medium transition-colors hover:border-brand hover:text-brand",
      )}
    >
      <Icon name="audio" className="size-4" />
      Start radio
    </button>
  );
}

function SmallButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={cn(
        "flex items-center gap-1.5 rounded-(--radius-pill) border border-rule",
        "px-3 py-1.5 text-(length:--step--2) text-muted transition-colors",
        "hover:border-brand hover:text-brand",
      )}
    >
      {children}
    </button>
  );
}
