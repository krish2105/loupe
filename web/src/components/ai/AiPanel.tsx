import { MarkNode } from "@/components/mark/Mark";
import type { VideoDetail } from "@/lib/catalogue";
import { cn } from "@/lib/utils";

/**
 * The AI panel.
 *
 * In Phase 2 this renders only states that are true today: the two unavailable
 * ones, and an empty one for talks that are indexed but have no summary
 * generated yet. The summariser, ask thread, and citation chips arrive in
 * Phase 6.
 *
 * Built now on purpose. §4.2 rule 4: "Design the unavailable state early.
 * Retrofitting this in week 9 is painful and it will look like an
 * afterthought." The unavailable state is not an error — for roughly 84% of
 * this catalogue it is the normal state, and it should read as a property of
 * the content rather than a failure of the product.
 */

function Panel({
  title,
  children,
  muted = false,
}: {
  title: React.ReactNode;
  children: React.ReactNode;
  muted?: boolean;
}) {
  return (
    <section
      aria-label="About this talk"
      className={cn(
        "rounded-(--radius-md) border border-rule p-4",
        muted ? "bg-transparent" : "bg-riser",
      )}
    >
      <h2 className="flex items-center gap-2 text-(length:--step--1) font-medium">
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function AiPanel({ video }: { video: VideoDetail }) {
  // Class B. The asymmetry is architectural, not a bug, and §4.2 rule 3 is
  // explicit that closing it by unofficial means is both a licensing risk and
  // worse engineering. So the panel says what is true and why.
  if (video.source_class === "referenced") {
    return (
      <Panel title="Not searchable" muted>
        <p className="text-pretty text-(length:--step--1) text-dust">
          This talk is listed from its original source, so Loupe holds its
          details but not its transcript. Searching inside and asking questions
          work only on talks in the indexed library.
        </p>
        <p className="mt-3 text-pretty text-(length:--step--2) text-dust">
          Look for the <MarkNode /> mark to find talks you can search inside.
        </p>
      </Panel>
    );
  }

  // Class A, still moving through the pipeline. §5.1: async by default, and the
  // UI has to be designed for partial availability rather than pretending
  // everything is either finished or broken.
  if (video.capabilities.processing) {
    return (
      <Panel title="Indexing" muted>
        <p className="text-pretty text-(length:--step--1) text-dust">
          This talk is watchable now. Searching inside it and asking it
          questions become available once transcription and indexing finish.
        </p>
        <p className="mt-3 font-mono text-(length:--step--2) text-dust">
          stage: {video.processing_status}
        </p>
      </Panel>
    );
  }

  return (
    <Panel
      title={
        <>
          <MarkNode /> Ask this talk
        </>
      }
    >
      <p className="text-pretty text-(length:--step--1) text-dust">
        No summary has been generated for this talk yet. When one exists it
        appears here with key points you can click to jump to.
      </p>
    </Panel>
  );
}
