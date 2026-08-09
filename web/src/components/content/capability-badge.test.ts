import { describe, expect, it } from "vitest";
import { badgeFor } from "./capability-badge";
import type { Capabilities } from "@/lib/catalogue";

/**
 * The API derives these five flags from one `processing_status` enum, so only
 * some of the thirty-two combinations can actually occur. The cases below are
 * built from the stages the API has, not from the flags in the abstract.
 */
function atStage(stage: string): Capabilities {
  const searchable = ["indexed", "enriched"].includes(stage);
  return {
    playable: !["uploaded", "transcoding"].includes(stage),
    searchable_inside: searchable,
    askable: searchable,
    has_chapters: searchable,
    processing: !searchable,
  };
}

describe("what a card claims about a talk", () => {
  it("says a finished talk is searchable inside", () => {
    expect(badgeFor(atStage("indexed"))).toBe("searchable");
    expect(badgeFor(atStage("enriched"))).toBe("searchable");
  });

  it("does not promise watchable before there is anything to watch", () => {
    /**
     * The bug. `processing` is true at both of these stages and there is no
     * stream behind either, so a card reading `processing` alone said
     * "watchable now" and the watch page then said "Still processing". A card
     * may say less than the page it leads to; it may not say more.
     */
    for (const stage of ["uploaded", "transcoding"]) {
      expect(badgeFor(atStage(stage))).toBe("processing");
    }
  });

  it("says watchable once there is a stream, even while indexing continues", () => {
    for (const stage of ["transcoded", "transcribing", "embedding"]) {
      expect(badgeFor(atStage(stage))).toBe("indexing");
    }
  });

  it("says nothing about ordinary referenced content", () => {
    /**
     * Class B is the common case, roughly four cards in five. Every one of them
     * announcing an absence would make the feed look broken rather than full.
     */
    expect(
      badgeFor({
        playable: false,
        searchable_inside: false,
        askable: false,
        has_chapters: false,
        processing: false,
      }),
    ).toBe("none");
  });
});
