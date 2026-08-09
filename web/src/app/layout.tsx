import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import { ThemeScript } from "@/components/theme/ThemeScript";
import "./globals.css";
import { ServiceWorker } from "@/components/ServiceWorker";

/**
 * Display face. Chosen for its width axis: width is magnification, which is
 * what the product's name means, so the wordmark can perform it. Used with
 * restraint — headings only, never below 20px (§7.1).
 */
const display = Bricolage_Grotesque({
  subsets: ["latin"],
  axes: ["opsz", "wdth"],
  variable: "--font-bricolage",
  display: "swap",
});

/** Body and chrome. Drawn for technical products, and it ships a mono sibling. */
const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-sans",
  display: "swap",
});

/** Utility: timecodes, chapter times, chunk ids, eval numbers, stage names. */
const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Loupe — search inside talks",
    template: "%s · Loupe",
  },
  description:
    "A video platform for AI and machine learning talks. Search inside a talk, ask it questions, and land on the exact moment.",
  // ADR 0003: installable, so audio mode has somewhere to run that is not a
  // browser tab. §3.2 rules out a native app, which makes this the ceiling.
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  // Matches the two canvases so the mobile browser chrome does not flash white.
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#14110e" },
    { media: "(prefers-color-scheme: light)", color: "#f6f7f9" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: ThemeScript writes data-theme before React
    // hydrates, so the server markup and the DOM legitimately differ here.
    <html
      lang="en"
      suppressHydrationWarning
      className={`${display.variable} ${sans.variable} ${mono.variable} h-full`}
    >
      <head>
        <ThemeScript />
      </head>
      <body className="min-h-full">
        {children}
        <ServiceWorker />
      </body>
    </html>
  );
}
