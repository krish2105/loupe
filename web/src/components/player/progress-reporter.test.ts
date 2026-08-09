import { describe, expect, it } from "vitest";
import { ProgressReporter } from "./progress-reporter";

describe("ProgressReporter", () => {
  it("stays quiet until the first interval has elapsed", () => {
    const reporter = new ProgressReporter(10);

    expect(reporter.shouldReport(3, "tick")).toBe(false);
    expect(reporter.shouldReport(9, "tick")).toBe(false);
    expect(reporter.shouldReport(10, "tick")).toBe(true);
  });

  it("reports once per interval, not once per timeupdate", () => {
    const reporter = new ProgressReporter(10);
    let writes = 0;

    // A real element fires timeupdate about four times a second.
    for (let quarter = 0; quarter <= 120; quarter++) {
      const position = quarter * 0.25;
      if (reporter.shouldReport(position, "tick")) {
        reporter.markReported(position);
        writes++;
      }
    }

    // Thirty seconds of playback is three writes, not a hundred and twenty.
    expect(writes).toBe(3);
  });

  it("always reports on pause and unload", () => {
    const reporter = new ProgressReporter(10);

    expect(reporter.shouldReport(4, "pause")).toBe(true);
    reporter.markReported(4);
    expect(reporter.shouldReport(7, "unload")).toBe(true);
  });

  it("never writes the same second twice", () => {
    const reporter = new ProgressReporter(10);

    expect(reporter.shouldReport(42, "pause")).toBe(true);
    reporter.markReported(42);

    // Pause and unload both fire as a tab closes; this is the duplicate that
    // would otherwise land in an append-only table.
    expect(reporter.shouldReport(42, "unload")).toBe(false);
    expect(reporter.shouldReport(42.4, "tick")).toBe(false);
  });

  it("records a seek immediately rather than waiting out the interval", () => {
    const reporter = new ProgressReporter(10);
    reporter.markReported(30);

    // A citation click jumps the playhead. The new position is meaningful now.
    expect(reporter.shouldReport(512, "tick")).toBe(true);
  });

  it("records a backward seek too", () => {
    const reporter = new ProgressReporter(10);
    reporter.markReported(500);

    expect(reporter.shouldReport(100, "tick")).toBe(true);
  });

  it("ignores position zero, which cannot be resumed to", () => {
    const reporter = new ProgressReporter(10);

    expect(reporter.shouldReport(0, "tick")).toBe(false);
    expect(reporter.shouldReport(0, "pause")).toBe(false);
    expect(reporter.shouldReport(0, "unload")).toBe(false);
  });

  it("starts fresh for another talk", () => {
    const reporter = new ProgressReporter(10);
    reporter.markReported(900);

    reporter.reset();

    expect(reporter.shouldReport(10, "tick")).toBe(true);
  });
});
