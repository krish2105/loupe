import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        // Placeholder thumbnail imagery, deterministic per talk. Real frames
        // arrive with the media provider, which generates sprite sheets.
        // Documented as a limitation in the README — these are stock photos,
        // not frames from the talks.
        protocol: "https",
        hostname: "picsum.photos",
      },
      {
        protocol: "https",
        hostname: "fastly.picsum.photos",
      },
    ],
  },
};

export default nextConfig;
