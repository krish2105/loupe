/**
 * Which routes own playback.
 *
 * There is one player store (§5.1) and `attach` replaces whatever is bound to
 * it, so exactly one surface may hold a media element at a time. The player bar
 * is rendered after the page in the root layout, which means on a video page it
 * attached *second* and took playback over: two media elements on screen, one
 * of them 0×0, every control driving the hidden one, and the visible player
 * stuck at 0:00. On browsers without native HLS the second attach broke
 * playback outright.
 *
 * Its own module so the rule is testable without a router, and so the list of
 * routes is somewhere findable rather than inline in a component.
 */

/** `/shorts` and `/watch/…` render their own player. `/listen/…` does not. */
export function ownsItsOwnPlayer(pathname: string): boolean {
  return (
    pathname === "/shorts" ||
    pathname.startsWith("/shorts/") ||
    pathname.startsWith("/watch/")
  );
}
