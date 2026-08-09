import { describe, expect, it } from "vitest";
import {
  RESUME_MAX_PCT,
  RESUME_MIN_SEC,
  resumePosition,
} from "./resume-policy";

/**
 * §9.1's resume rule, on the client side.
 *
 * The same two thresholds the API applies, tested here because this copy is
 * what runs after a reload and for anyone who never signed in. If these two
 * ever disagree, the same episode resumes to two different places depending on
 * which path restored it.
 */

const HOUR = 3600;

describe("resuming", () => {
  it("returns the saved position mid-episode", () => {
    expect(resumePosition(1200, HOUR)).toBe(1200);
  });

  it("starts from the beginning when nothing was saved", () => {
    expect(resumePosition(null, HOUR)).toBeNull();
    expect(resumePosition(undefined, HOUR)).toBeNull();
  });

  it("ignores a position from the first few seconds", () => {
    // Offering to resume four seconds in is noise, not a service.
    expect(resumePosition(RESUME_MIN_SEC, HOUR)).toBeNull();
    expect(resumePosition(RESUME_MIN_SEC + 1, HOUR)).toBe(RESUME_MIN_SEC + 1);
  });

  it("ignores a position on an effectively finished episode", () => {
    // Resuming here lands on the sign-off.
    expect(resumePosition(HOUR * RESUME_MAX_PCT, HOUR)).toBeNull();
    expect(resumePosition(HOUR * 0.94, HOUR)).toBe(HOUR * 0.94);
  });

  it("ignores a position past the end", () => {
    // A saved position can outlive the media it belongs to: a re-encode, or a
    // provider swap, and suddenly the file is shorter than where you were.
    expect(resumePosition(HOUR + 10, HOUR)).toBeNull();
  });

  it("resumes on position alone when the length is unknown", () => {
    /**
     * Duration is zero until metadata loads, and never arrives at all on an
     * unbounded stream. Refusing to resume anything whose length is unknown
     * would mean refusing in exactly the case this is most wanted.
     */
    expect(resumePosition(1200, 0)).toBe(1200);
  });

  it("rejects a position that is not a number", () => {
    // localStorage is a string store and anything can be written into it.
    expect(resumePosition(Number.NaN, HOUR)).toBeNull();
    expect(resumePosition(Number.POSITIVE_INFINITY, HOUR)).toBeNull();
  });
});
