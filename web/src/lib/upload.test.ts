import { describe, expect, it } from "vitest";
import {
  fileProblem,
  formatBytes,
  progressLabel,
  ticketProblem,
  type UploadTicket,
} from "./upload";

const NOW = 1_770_000_000_000; // fixed, so expiry is a comparison and not a race

function ticket(overrides: Partial<UploadTicket> = {}): UploadTicket {
  return {
    upload_url: "https://s3.example/loupe-media/videos/abc/source/original?X-Amz-Signature=x",
    expires_at: Math.floor(NOW / 1000) + 3600,
    method: "PUT",
    ...overrides,
  };
}

/** A File without needing a browser. */
function fakeFile(bytes: number, type = "video/mp4"): File {
  return { size: bytes, type, name: "talk.mp4" } as File;
}

describe("whether a ticket can be used", () => {
  it("accepts a fresh S3 ticket", () => {
    expect(ticketProblem(ticket(), NOW)).toBeNull();
  });

  it("catches a ticket that expired before the file was sent", () => {
    /**
     * The reason this is checked at all. An expired presigned URL fails as a
     * 403 with an XML body, which reaches someone uploading a conference talk
     * as "Upload failed" and nothing more.
     */
    const expired = ticket({ expires_at: Math.floor(NOW / 1000) - 1 });

    expect(ticketProblem(expired, NOW)).toMatch(/expired/);
  });

  it("treats the expiry second itself as expired", () => {
    // The bucket will already have rejected it by the time the request lands.
    const onTheBoundary = ticket({ expires_at: Math.floor(NOW / 1000) });

    expect(ticketProblem(onTheBoundary, NOW)).toMatch(/expired/);
  });

  it("catches a ticket with no upload address", () => {
    expect(ticketProblem(ticket({ upload_url: "" }), NOW)).toMatch(/no upload address/);
  });

  it("catches the Bunny shape missing its signature", () => {
    const incomplete = ticket({ method: "POST", signature: null });

    expect(ticketProblem(incomplete, NOW)).toMatch(/incomplete/);
  });

  it("accepts the Bunny shape when it is complete", () => {
    const complete = ticket({ method: "POST", signature: "abc", library_id: "1" });

    expect(ticketProblem(complete, NOW)).toBeNull();
  });
});

describe("whether the file is worth sending", () => {
  const LIMIT = 2 * 1024 * 1024 * 1024;

  it("accepts an ordinary video", () => {
    expect(fileProblem(fakeFile(500 * 1024 * 1024), LIMIT)).toBeNull();
  });

  it("accepts audio, since the catalogue has episodes too", () => {
    expect(fileProblem(fakeFile(40 * 1024 * 1024, "audio/mpeg"), LIMIT)).toBeNull();
  });

  it("asks for a file when there is none", () => {
    expect(fileProblem(null, LIMIT)).toMatch(/Choose a video file/);
  });

  it("rejects an empty file", () => {
    // Uploads cleanly, transcodes to nothing, fails much later and confusingly.
    expect(fileProblem(fakeFile(0), LIMIT)).toMatch(/empty/);
  });

  it("names both sizes when the file is too large", () => {
    const problem = fileProblem(fakeFile(3 * 1024 * 1024 * 1024), LIMIT);

    expect(problem).toContain("3.0 GB");
    expect(problem).toContain("2.0 GB");
  });

  it("rejects something that is not media", () => {
    expect(fileProblem(fakeFile(1024, "application/pdf"), LIMIT)).toMatch(/not look like/);
  });
});

describe("sizes people can read", () => {
  it("uses one decimal below ten and none above", () => {
    // "1.4 GB" beats "1 GB"; "847 MB" beats "847.3 MB".
    expect(formatBytes(1.4 * 1024 * 1024 * 1024)).toBe("1.4 GB");
    expect(formatBytes(847 * 1024 * 1024)).toBe("847 MB");
  });

  it("leaves bytes alone", () => {
    expect(formatBytes(512)).toBe("512 B");
  });

  it("stops at gigabytes rather than inventing units", () => {
    expect(formatBytes(5 * 1024 ** 4)).toBe("5120 GB");
  });
});

describe("the progress line", () => {
  it("reports a percentage of the total", () => {
    expect(progressLabel(512 * 1024 * 1024, 1024 * 1024 * 1024)).toBe(
      "Sending… 50% of 1.0 GB",
    );
  });

  it("says something true when the total is unknown", () => {
    // Rare but real. "NaN%" is worse than being less precise.
    expect(progressLabel(1024 * 1024, 0)).toBe("Sending… 1.0 MB");
  });

  it("never exceeds a hundred percent", () => {
    expect(progressLabel(1100, 1000)).toContain("100%");
  });
});
