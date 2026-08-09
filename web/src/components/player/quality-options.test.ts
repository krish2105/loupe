import { describe, expect, it } from "vitest";
import { AUTO, qualityLabel, qualityOptions } from "./quality-options";

const level = (index: number, height: number, bitrate: number) => ({
  index,
  height,
  bitrate,
});

describe("building the quality menu from a manifest", () => {
  it("offers auto first, then heights from best to worst", () => {
    const options = qualityOptions([
      level(0, 270, 400_000),
      level(1, 540, 1_200_000),
      level(2, 1080, 5_000_000),
      level(3, 720, 2_500_000),
    ]);

    expect(options.map((o) => o.label)).toEqual([
      "Auto",
      "1080p",
      "720p",
      "540p",
      "270p",
    ]);
    expect(options[0].index).toBe(AUTO);
  });

  it("collapses duplicate heights to the highest bitrate", () => {
    /**
     * A ladder with two bitrates at 720p is ordinary, and showing both gives
     * two rows a person cannot tell apart. Picking "720p" means the better one.
     */
    const options = qualityOptions([
      level(0, 720, 1_800_000),
      level(1, 720, 3_000_000),
      level(2, 1080, 5_000_000),
    ]);

    expect(options.map((o) => o.label)).toEqual(["Auto", "1080p", "720p"]);
    expect(options.find((o) => o.label === "720p")?.index).toBe(1);
  });

  it("drops audio-only renditions rather than offering 0p", () => {
    const options = qualityOptions([
      level(0, 0, 128_000),
      level(1, 540, 1_200_000),
      level(2, 1080, 5_000_000),
    ]);

    expect(options.map((o) => o.label)).toEqual(["Auto", "1080p", "540p"]);
  });

  it("offers nothing when there is nothing to choose between", () => {
    // One rendition is one outcome. A menu here would be a control that
    // changes nothing, which is worse than no control.
    expect(qualityOptions([level(0, 720, 2_000_000)])).toEqual([]);
    expect(qualityOptions([])).toEqual([]);
  });

  it("still offers a choice when one height has several bitrates", () => {
    // Two variants, one height — after collapsing there is still only one
    // real row, so there is still nothing to choose.
    expect(
      qualityOptions([level(0, 720, 1_000_000), level(1, 720, 3_000_000)]),
    ).toEqual([]);
  });
});

describe("what the quality button reads", () => {
  it("names the resolution auto landed on", () => {
    expect(qualityLabel(AUTO, 1080)).toBe("Auto 1080p");
  });

  it("names just the resolution when one is pinned", () => {
    expect(qualityLabel(2, 1080)).toBe("1080p");
  });

  it("says auto before any level has been chosen", () => {
    // LEVEL_SWITCHED has not fired yet, so there is no height to report and
    // the button must still say something true.
    expect(qualityLabel(AUTO, null)).toBe("Auto");
  });
});
