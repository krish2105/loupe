import { describe, expect, it } from "vitest";
import { ownsItsOwnPlayer } from "./player-ownership";

/**
 * Which routes own playback.
 *
 * There is one player store (§5.1) and `attach` replaces whatever was bound to
 * it. The player bar is rendered after the page in the root layout, so on a
 * video page it attached second and took playback over: two media elements,
 * one of them 0×0, and every control driving the hidden one.
 *
 * The rule is one line and the bug it fixes was invisible until a queue existed
 * in localStorage — which is why it survived local testing and appeared only
 * once someone had actually played something.
 */

describe("routes that own their own player", () => {
  it("claims the video page", () => {
    expect(ownsItsOwnPlayer("/watch/10000000-0000-4000-a000-000000000003")).toBe(
      true,
    );
  });

  it("claims the shorts feed", () => {
    expect(ownsItsOwnPlayer("/shorts")).toBe(true);
  });

  it("does not claim the episode page", () => {
    /**
     * The episode page deliberately has no media element — playback lives in
     * the bar, which is the whole reason the bar survives navigation. Claiming
     * this route would leave nothing able to play audio at all.
     */
    expect(ownsItsOwnPlayer("/listen/12000000-0000-4000-a000-000000000001")).toBe(
      false,
    );
  });

  it("does not claim the listen index", () => {
    expect(ownsItsOwnPlayer("/listen")).toBe(false);
  });

  it("does not claim ordinary pages", () => {
    for (const path of ["/", "/search", "/playlists", "/downloads", "/history"]) {
      expect(ownsItsOwnPlayer(path)).toBe(false);
    }
  });

  it("is not fooled by a route that merely starts with the same letters", () => {
    // /watchlist would not be a video page, and matching it would silently
    // remove the bar from a surface that needs it.
    expect(ownsItsOwnPlayer("/watchlist")).toBe(false);
  });
});
