/**
 * Whether a saved position is worth returning someone to (§9.1).
 *
 * These two numbers also exist in the API, in `resume_position`. That is a
 * duplicate and it is a deliberate one: the API's copy answers "where should
 * this signed-in person pick up, on any device", and needs a round trip. This
 * copy answers "where was this tab when it reloaded", has to be instant, and
 * has to work for someone who never signed in.
 *
 * They must agree, because the same episode resuming to two different places
 * depending on which path restored it is worse than either rule alone. So they
 * are stated identically and each points at the other.
 */

/** Below this, there is nothing to resume to — it barely started. */
export const RESUME_MIN_SEC = 10;

/** Past this, it is effectively finished and resuming lands on the credits. */
export const RESUME_MAX_PCT = 0.95;

/**
 * @param savedSec the last position recorded for this content, if any
 * @param durationSec its length, or 0 when the media has not reported one yet
 * @returns the second to seek to, or null to start from the beginning
 */
export function resumePosition(
  savedSec: number | null | undefined,
  durationSec: number,
): number | null {
  if (savedSec == null || !Number.isFinite(savedSec)) return null;
  if (savedSec <= RESUME_MIN_SEC) return null;

  // Duration is unknown until metadata loads, and on a live or unbounded stream
  // it never arrives. Resuming on the position alone is right in both cases:
  // the alternative is refusing to resume anything whose length is unknown.
  if (durationSec > 0) {
    if (savedSec >= durationSec) return null;
    if (savedSec / durationSec >= RESUME_MAX_PCT) return null;
  }

  return savedSec;
}
