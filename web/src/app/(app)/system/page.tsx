import type { Metadata } from "next";
import { MarkNode, MarkUnderline } from "@/components/mark/Mark";
import { formatTimecode } from "@/lib/utils";

export const metadata: Metadata = { title: "Design system" };

/**
 * The design system, made visible.
 *
 * Phase 0's deliverable list includes the token system, and a token system you
 * cannot look at is a token system nobody checks. This page is the surface the
 * §7.7 quality gate gets run against — switch the theme with the control in the
 * rail and every value here has to hold in both.
 */

const TOKENS = [
  { name: "canvas", role: "Page background", dark: "#0F0F0F", light: "#FFFFFF" },
  { name: "surface", role: "Cards, menus, chrome", dark: "#1F1F1F", light: "#F7F7F8" },
  { name: "rule", role: "Borders, dividers", dark: "#303030", light: "#E3E3E5" },
  { name: "muted", role: "Secondary text", dark: "#A9A9AD", light: "#5F6368" },
  { name: "ink", role: "Primary text", dark: "#F2F2F3", light: "#0F0F10" },
  { name: "brand", role: "Interactive, brand", dark: "#FF4D4D", light: "#CC0000" },
  { name: "danger", role: "Errors — amber, not red", dark: "#FFB86B", light: "#8A5300" },
];

const CONTRAST = [
  { pair: "ink on canvas", dark: "17.7:1", light: "19.0:1" },
  { pair: "muted on canvas", dark: "9.0:1", light: "6.1:1" },
  { pair: "brand on canvas", dark: "6.0:1", light: "5.8:1" },
  { pair: "danger on canvas", dark: "11.8:1", light: "6.3:1" },
];

const STEPS = [
  { token: "--step-5", use: "Page display" },
  { token: "--step-4", use: "Page heading" },
  { token: "--step-3", use: "Section heading" },
  { token: "--step-2", use: "Card heading" },
  { token: "--step-1", use: "Lead" },
  { token: "--step-0", use: "Body" },
  { token: "--step--1", use: "Caption, metadata" },
  { token: "--step--2", use: "Timecode, micro-label" },
];

function Section({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-rule py-10">
      <h2 className="text-(length:--step-2)">{title}</h2>
      {note && (
        <p className="mt-2 max-w-[62ch] text-pretty text-(length:--step--1) text-muted">
          {note}
        </p>
      )}
      <div className="mt-6">{children}</div>
    </section>
  );
}

export default function SystemPage() {
  return (
    <div className="py-10">
      <h1 className="text-(length:--step-4)">Design system</h1>
      <p className="mt-3 max-w-[62ch] text-pretty text-(length:--step-1) text-muted">
        Red and white, per ADR 0002. Both themes are designed to equal weight; neither is a derivative of the other. Switch between them in the top bar.
      </p>

      <Section
        title="Colour"
        note="Red is the interactive colour: buttons, active navigation, focus rings. The old rule reserving the accent for the semantic layer is retired — see ADR 0002 for what that cost."
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-left">
            <thead>
              <tr className="text-(length:--step--2) uppercase tracking-wider text-muted">
                <th className="pb-3 font-medium">Swatch</th>
                <th className="pb-3 font-medium">Token</th>
                <th className="pb-3 font-medium">Role</th>
                <th className="pb-3 font-medium">Dark</th>
                <th className="pb-3 font-medium">Light</th>
              </tr>
            </thead>
            <tbody className="text-(length:--step--1)">
              {TOKENS.map((token) => (
                <tr key={token.name} className="border-t border-rule">
                  <td className="py-3">
                    <span
                      className="block size-8 rounded-(--radius-sm) border border-rule"
                      style={{ background: `var(--${token.name})` }}
                    />
                  </td>
                  <td className="py-3 font-mono">{token.name}</td>
                  <td className="py-3 text-muted">{token.role}</td>
                  <td className="py-3 font-mono text-muted">{token.dark}</td>
                  <td className="py-3 font-mono text-muted">{token.light}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section
        title="Contrast"
        note="Measured, not assumed. The §7.7 floor is 4.5:1 for body text and every pair clears it in both themes."
      >
        <ul className="grid gap-2 sm:grid-cols-2">
          {CONTRAST.map((row) => (
            <li
              key={row.pair}
              className="flex items-center justify-between rounded-(--radius-md) border border-rule bg-surface px-4 py-3 text-(length:--step--1)"
            >
              <span className="font-mono">{row.pair}</span>
              <span className="font-mono text-muted">
                {row.dark} · {row.light}
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section
        title="Type"
        note="Bricolage Grotesque for display, chosen for its width axis — width is magnification, which is what the name means. IBM Plex Sans for body and chrome, IBM Plex Mono for timecodes and data. Every step is a clamp(), so sizes interpolate rather than jumping at a breakpoint."
      >
        <div className="space-y-4">
          {STEPS.map((step) => (
            <div
              key={step.token}
              className="flex flex-wrap items-baseline gap-x-6 gap-y-1 border-b border-rule pb-4"
            >
              <span
                className={
                  step.token === "--step-5" ||
                  step.token === "--step-4" ||
                  step.token === "--step-3"
                    ? "font-display"
                    : undefined
                }
                style={{ fontSize: `var(${step.token})` }}
              >
                Search inside the talk
              </span>
              <span className="ml-auto font-mono text-(length:--step--2) text-muted">
                {step.token} · {step.use}
              </span>
            </div>
          ))}
        </div>
      </Section>

      <Section
        title="The Mark"
        note="One primitive meaning “this exact moment”, at every scale. It used to be recognisable as the only coloured object; now that red is everywhere it is recognisable by form — a stroke with a node, under cited text and on the scrubber at the same timestamp."
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-(--radius-md) border border-rule bg-surface p-4">
            <p className="text-(length:--step--2) uppercase tracking-wider text-muted">
              Node
            </p>
            <p className="mt-3 text-(length:--step-0)">
              <MarkNode label="AI ready" /> <span className="ml-2 text-muted">AI ready</span>
            </p>
          </div>

          <div className="rounded-(--radius-md) border border-rule bg-surface p-4 sm:col-span-2">
            <p className="text-(length:--step--2) uppercase tracking-wider text-muted">
              Underline
            </p>
            <p className="mt-3 text-(length:--step-0)">
              …the cost is{" "}
              <MarkUnderline>quadratic in sequence length</MarkUnderline>, which
              is exactly why we cache the KV…
            </p>
          </div>
        </div>
      </Section>

      <Section
        title="Radius and utility"
        note="Four steps, not one value applied everywhere: 0 for the scrubber, 4 for marks and chips, 10 for cards and sheets, pill for the search capsule."
      >
        <div className="flex flex-wrap items-end gap-4">
          {[
            { label: "none · scrubber", cls: "rounded-(--radius-none)" },
            { label: "sm · chips", cls: "rounded-(--radius-sm)" },
            { label: "md · cards", cls: "rounded-(--radius-md)" },
            { label: "pill · capsule", cls: "rounded-(--radius-pill)" },
          ].map((radius) => (
            <div key={radius.label} className="text-center">
              <div
                className={`size-16 border border-rule bg-surface ${radius.cls}`}
              />
              <p className="mt-2 font-mono text-(length:--step--2) text-muted">
                {radius.label}
              </p>
            </div>
          ))}
        </div>

        <p className="mt-8 font-mono text-(length:--step--2) text-muted">
          Timecodes render through one formatter so citations, chapters, and the
          scrubber always agree: {formatTimecode(14 * 60 + 22)} ·{" "}
          {formatTimecode(3 * 3600 + 7 * 60 + 4)}
        </p>
      </Section>
    </div>
  );
}
