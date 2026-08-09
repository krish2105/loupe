import { describe, expect, it } from "vitest";
import { activeLine, type TimedLine } from "./transcript-policy";

/**
 * Which transcript line is highlighted.
 *
 * Small enough to look obvious and wrong in a way nobody sees until they read
 * along and the highlight sits one line ahead of the audio.
 */

const LINES: TimedLine[] = [
  { start_sec: 0 },
  { start_sec: 10 },
  { start_sec: 20 },
];

describe("the active line", () => {
  it("is nothing before the first word", () => {
    expect(activeLine(LINES, -1)).toBe(-1);
  });

  it("is the line that has started", () => {
    expect(activeLine(LINES, 11)).toBe(1);
  });

  it("switches exactly on the boundary, not after it", () => {
    expect(activeLine(LINES, 10)).toBe(1);
    expect(activeLine(LINES, 9.99)).toBe(0);
  });

  it("holds the previous line through a silence", () => {
    /**
     * Line 0 ends before line 1 starts at 10. Highlighting nothing through that
     * gap makes the transcript look broken every time the speaker pauses.
     */
    expect(activeLine(LINES, 7)).toBe(0);
  });

  it("holds the last line past the end", () => {
    expect(activeLine(LINES, 9999)).toBe(2);
  });

  it("has nothing to highlight in an empty transcript", () => {
    expect(activeLine([], 5)).toBe(-1);
  });
});
