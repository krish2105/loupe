"use client";

import type { Chapter } from "@/components/player/Scrubber";
import { PlayerProvider, usePlayerControls } from "@/components/player/PlayerContext";
import { VideoPlayer } from "@/components/player/VideoPlayer";
import { MarkNode, MarkUnderline } from "@/components/mark/Mark";
import { cn, formatTimecode } from "@/lib/utils";

/**
 * Phase 1 verification surface.
 *
 * Apple's reference HLS stream, which carries several renditions — so "plays
 * adaptively" (the Phase 1 gate) is actually observable rather than asserted.
 * The rendition indicator in the controls shows which level ABR selected.
 *
 * The chapters and citations below are hand-written stand-ins. They exercise
 * the chapter-segmented scrubber and the citation-seek path now, six weeks
 * before the pipeline can generate real ones — which is the whole reason §5.1
 * insists the player abstraction is built in week 1.
 *
 * This route is scaffolding and comes out when real videos exist.
 */

const DEMO_SRC =
  "https://devstreaming-cdn.apple.com/videos/streaming/examples/img_bipbop_adv_example_fmp4/master.m3u8";

const DEMO_CHAPTERS: Chapter[] = [
  { startSec: 0, endSec: 120, title: "Opening" },
  { startSec: 120, endSec: 300, title: "The attention bottleneck" },
  { startSec: 300, endSec: 480, title: "Caching strategies" },
  { startSec: 480, endSec: 1800, title: "Questions" },
];

const DEMO_CITATIONS = [
  { atSec: 142, text: "the cost is quadratic in sequence length" },
  { atSec: 331, text: "memory bandwidth becomes the limit" },
  { atSec: 512, text: "we cache the KV pairs across steps" },
];

function CitationChip({ atSec, text }: { atSec: number; text: string }) {
  const { seek, play } = usePlayerControls();

  return (
    <button
      type="button"
      onClick={() => {
        seek(atSec);
        play();
      }}
      className={cn(
        "block w-full rounded-(--radius-md) border border-rule bg-riser",
        "px-4 py-3 text-left transition-colors hover:border-dust",
      )}
    >
      <span className="font-mono text-(length:--step--2) text-dust">
        {formatTimecode(atSec)}
      </span>
      <span className="mt-1 block text-(length:--step-0)">
        …<MarkUnderline>{text}</MarkUnderline>…
      </span>
    </button>
  );
}

export default function WatchDemoPage() {
  return (
    <PlayerProvider>
      <div className="grid gap-8 py-8 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div>
          <VideoPlayer
            src={DEMO_SRC}
            title="Player verification stream"
            chapters={DEMO_CHAPTERS}
            marks={DEMO_CITATIONS.map((citation) => citation.atSec)}
            resumeAtSec={95}
          />

          <h1 className="mt-5 text-(length:--step-3)">
            Player verification stream
          </h1>
          <p className="mt-2 text-(length:--step--1) text-dust">
            Apple reference HLS · multiple renditions · the level indicator in
            the controls shows what adaptive bitrate selected.
          </p>

          <div className="mt-6 rounded-(--radius-md) border border-rule bg-riser p-4">
            <h2 className="text-(length:--step--1) font-medium">Keyboard</h2>
            <p className="mt-2 text-(length:--step--1) text-dust">
              Space or K play and pause · ← → seek five seconds · J and L seek
              ten · 0–9 jump to that tenth · F full screen · M mute. None of
              them fire while you are typing in the search field.
            </p>
          </div>
        </div>

        <aside>
          <h2 className="flex items-center gap-2 text-(length:--step-1)">
            <MarkNode /> Citations
          </h2>
          <p className="mt-2 text-(length:--step--1) text-dust">
            Click one. The player seeks and the matching tick is already on the
            scrubber — one object, two places.
          </p>

          <div className="mt-4 space-y-2">
            {DEMO_CITATIONS.map((citation) => (
              <CitationChip key={citation.atSec} {...citation} />
            ))}
          </div>
        </aside>
      </div>
    </PlayerProvider>
  );
}
