import { describe, expect, it } from "vitest";
import { keyToAction } from "./keyboard";

describe("keyToAction", () => {
  it("maps every binding §9.1 specifies", () => {
    expect(keyToAction({ key: " " })).toEqual({ type: "toggle" });
    expect(keyToAction({ key: "k" })).toEqual({ type: "toggle" });
    expect(keyToAction({ key: "ArrowLeft" })).toEqual({ type: "nudge", seconds: -5 });
    expect(keyToAction({ key: "ArrowRight" })).toEqual({ type: "nudge", seconds: 5 });
    expect(keyToAction({ key: "j" })).toEqual({ type: "nudge", seconds: -10 });
    expect(keyToAction({ key: "l" })).toEqual({ type: "nudge", seconds: 10 });
    expect(keyToAction({ key: "f" })).toEqual({ type: "fullscreen" });
    expect(keyToAction({ key: "m" })).toEqual({ type: "mute" });
  });

  it("is case-insensitive, so caps lock does not break playback", () => {
    expect(keyToAction({ key: "K" })).toEqual({ type: "toggle" });
    expect(keyToAction({ key: "J" })).toEqual({ type: "nudge", seconds: -10 });
    expect(keyToAction({ key: "F" })).toEqual({ type: "fullscreen" });
  });

  it("seeks to the matching tenth on a number key", () => {
    expect(keyToAction({ key: "0" })).toEqual({ type: "seekFraction", fraction: 0 });
    expect(keyToAction({ key: "5" })).toEqual({ type: "seekFraction", fraction: 0.5 });
    expect(keyToAction({ key: "9" })).toEqual({
      type: "seekFraction",
      fraction: 0.9,
    });
  });

  it("never shadows a browser or OS shortcut", () => {
    // Cmd-L is the address bar; Cmd-F is find. Stealing either would be worse
    // than having no shortcut at all.
    expect(keyToAction({ key: "l", metaKey: true })).toBeNull();
    expect(keyToAction({ key: "f", ctrlKey: true })).toBeNull();
    expect(keyToAction({ key: " ", altKey: true })).toBeNull();
  });

  it("ignores keys it does not own", () => {
    expect(keyToAction({ key: "q" })).toBeNull();
    expect(keyToAction({ key: "Enter" })).toBeNull();
    expect(keyToAction({ key: "Tab" })).toBeNull();
  });
});
