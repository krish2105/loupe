import { describe, expect, it } from "vitest";
import {
  buildOfflineMaster,
  findAudioRendition,
  findMediaFile,
  parseRangeHeader,
} from "./hls-manifest";

/**
 * Manifest parsing for downloads (ADR 0003).
 *
 * The byte arithmetic here is the kind that is wrong by one and produces a
 * download that looks fine, reports the right size, and plays static.
 */

const BASE = "https://cdn.example.com/talks/ep1/master.m3u8";

const MASTER = `#EXTM3U
#EXT-X-VERSION:6
#EXT-X-INDEPENDENT-SEGMENTS
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud1",LANGUAGE="en",NAME="English",AUTOSELECT=YES,DEFAULT=YES,CHANNELS="2",URI="a1/prog_index.m3u8"
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud2",LANGUAGE="en",NAME="Surround",AUTOSELECT=YES,DEFAULT=NO,CHANNELS="6",URI="a2/prog_index.m3u8"
#EXT-X-STREAM-INF:BANDWIDTH=541052,CODECS="avc1.640015,mp4a.40.2",RESOLUTION=480x270,AUDIO="aud1"
v2/prog_index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=8001098,CODECS="avc1.64002a,ac-3",RESOLUTION=1920x1080,AUDIO="aud2"
v9/prog_index.m3u8
`;

describe("finding the audio rendition", () => {
  it("takes the default audio group", () => {
    const rendition = findAudioRendition(MASTER, BASE);

    expect(rendition?.url).toBe("https://cdn.example.com/talks/ep1/a1/prog_index.m3u8");
    expect(rendition?.name).toBe("English");
  });

  it("reads the codec off a variant that uses that group", () => {
    /**
     * The EXT-X-MEDIA entry carries no CODECS attribute of its own, and hls.js
     * will not select a rendition whose codec it was not told. Taking it from
     * the wrong variant would hand back "ac-3" for a stereo AAC rendition.
     */
    expect(findAudioRendition(MASTER, BASE)?.codecs).toBe("mp4a.40.2");
  });

  it("returns nothing when the audio is muxed into the video", () => {
    // A muxed stream cannot be stored as audio alone, and pretending otherwise
    // produces a download that plays video nobody asked for.
    const muxed = `#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=541052,CODECS="avc1.640015,mp4a.40.2"
v2/prog_index.m3u8
`;
    expect(findAudioRendition(muxed, BASE)).toBeNull();
  });
});

describe("finding the media file", () => {
  const PLAYLIST_URL = "https://cdn.example.com/talks/ep1/a1/prog_index.m3u8";

  it("follows a byte-range playlist to one file and its highest byte", () => {
    const playlist = `#EXTM3U
#EXT-X-TARGETDURATION:6
#EXT-X-PLAYLIST-TYPE:VOD
#EXT-X-MAP:URI="main.mp4",BYTERANGE="616@0"
#EXTINF:5.99467,
#EXT-X-BYTERANGE:121090@616
main.mp4
#EXTINF:5.99467,
#EXT-X-BYTERANGE:120000@121706
main.mp4
#EXT-X-ENDLIST
`;

    expect(findMediaFile(playlist, PLAYLIST_URL)).toEqual({
      url: "https://cdn.example.com/talks/ep1/a1/main.mp4",
      lastByte: 241706,
    });
  });

  it("treats a missing offset as continuing from the previous range", () => {
    /**
     * EXT-X-BYTERANGE's offset is optional and means "immediately after the
     * previous one". Reading a missing offset as zero would make every range
     * after the first overlap the start of the file.
     */
    const playlist = `#EXTM3U
#EXT-X-MAP:URI="main.mp4",BYTERANGE="600@0"
#EXTINF:6,
#EXT-X-BYTERANGE:1000@600
main.mp4
#EXTINF:6,
#EXT-X-BYTERANGE:1000
main.mp4
`;

    expect(findMediaFile(playlist, PLAYLIST_URL)?.lastByte).toBe(2600);
  });

  it("counts only the bytes the playlist actually addresses", () => {
    // A playlist can address part of a larger file. Downloading the rest is
    // storing bytes that will never be played.
    const playlist = `#EXTM3U
#EXT-X-MAP:URI="main.mp4",BYTERANGE="100@0"
#EXTINF:6,
#EXT-X-BYTERANGE:500@100
main.mp4
`;
    expect(findMediaFile(playlist, PLAYLIST_URL)?.lastByte).toBe(600);
  });

  it("declines a playlist of separate segment files", () => {
    const playlist = `#EXTM3U
#EXTINF:6,
seg1.ts
#EXTINF:6,
seg2.ts
`;
    expect(findMediaFile(playlist, PLAYLIST_URL)).toBeNull();
  });

  it("returns nothing for an empty playlist rather than a file of length zero", () => {
    expect(findMediaFile("#EXTM3U\n", PLAYLIST_URL)).toBeNull();
  });
});

describe("the offline master", () => {
  it("offers exactly one rendition", () => {
    /**
     * Serving the original master offline lets the player pick a video
     * rendition that was never stored, and the failure reads as a broken
     * download rather than a missing one.
     */
    const rendition = findAudioRendition(MASTER, BASE)!;
    const master = buildOfflineMaster(rendition, "a1/prog_index.m3u8");

    expect(master.match(/#EXT-X-STREAM-INF/g)).toHaveLength(1);
    expect(master).toContain('CODECS="mp4a.40.2"');
    expect(master).toContain("a1/prog_index.m3u8");
  });
});

describe("range headers", () => {
  it("parses an explicit range", () => {
    expect(parseRangeHeader("bytes=616-121705", 1_000_000)).toEqual({
      start: 616,
      end: 121705,
    });
  });

  it("treats an open end as the end of the file", () => {
    expect(parseRangeHeader("bytes=900-", 1000)).toEqual({ start: 900, end: 999 });
  });

  it("reads a suffix range as the last n bytes", () => {
    // "bytes=-500" is the last 500 bytes, not "up to byte 500". Backwards here
    // plays the wrong part of the file.
    expect(parseRangeHeader("bytes=-500", 1000)).toEqual({ start: 500, end: 999 });
  });

  it("clamps an end past the file", () => {
    expect(parseRangeHeader("bytes=0-99999", 1000)).toEqual({ start: 0, end: 999 });
  });

  it("rejects a backwards or out-of-bounds range", () => {
    expect(parseRangeHeader("bytes=500-100", 1000)).toBeNull();
    expect(parseRangeHeader("bytes=2000-3000", 1000)).toBeNull();
  });

  it("rejects nonsense rather than guessing", () => {
    expect(parseRangeHeader(null, 1000)).toBeNull();
    expect(parseRangeHeader("items=0-10", 1000)).toBeNull();
    expect(parseRangeHeader("bytes=abc-def", 1000)).toBeNull();
  });
});
