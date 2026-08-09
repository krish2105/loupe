import { MarkNode, MarkUnderline } from "@/components/mark/Mark";
import { Reveal } from "@/components/motion/Reveal";

/**
 * Home.
 *
 * Empty in Phase 0 by design — the gate is a signed-in person seeing the shell,
 * not a populated feed. The copy treats the empty screen as an invitation and
 * introduces the Mark, so the one chromatic object in the product has a meaning
 * before it ever appears on a card (§7.6).
 */
export default function HomePage() {
  return (
    <div className="mx-auto grid min-h-[70dvh] max-w-[560px] place-content-center py-16">
      <Reveal>
        <h1 className="text-(length:--step-4)">No talks yet</h1>
      </Reveal>

      <Reveal delay={0.06}>
        <p className="mt-4 text-pretty text-(length:--step-1) text-dust">
          Talks appear here newest first as they finish indexing. A talk becomes
          watchable long before it becomes searchable.
        </p>
      </Reveal>

      <Reveal delay={0.12}>
        <div className="mt-10 rounded-(--radius-md) border border-rule bg-riser p-5">
          <p className="text-(length:--step--1) text-dust">
            <MarkNode /> <span className="ml-1" />
            marks a talk you can search inside. Ask it a question and the answer
            cites the exact moment, like{" "}
            <MarkUnderline>this phrase from the transcript</MarkUnderline>, which
            seeks the player when clicked.
          </p>
        </div>
      </Reveal>
    </div>
  );
}
