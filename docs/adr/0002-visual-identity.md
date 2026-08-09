# ADR 0002 — Visual identity: red and white, mainstream video layout

**Status:** Accepted, 9 Aug 2026. Owner's decision, taken against the plan's stated position.
**Amends:** §2 (positioning), §7.2 (direction constraints), §18.3 (design freeze).
**Supersedes:** the palette and system rule in `docs/design/direction.md`.

## The decision

Loupe adopts a red-and-white identity and the layout conventions of a
mainstream video platform: a persistent top bar with centred search, an
expanded left sidebar carrying sections and subscribed channels, a denser
thumbnail grid, and channel avatars on cards.

Both themes are designed to equal weight; neither is primary.

## What the plan said, and why it is being overruled

This is a reversal, and the reasoning against it should survive the decision.

- **§2:** *"Feature parity with YouTube; zero trademark, logo, or visual
  cloning. A pixel-identical skin reads as a tutorial follow-along. An original
  identity over the same feature set reads as a product engineer."*
- **§7.2:** *"Accent: Exactly one. Not acid green. Not video-platform red."*
- **§18.3:** The system was frozen at the Phase 2 gate, which had passed.

The plan's argument was about how the work reads to a technical reviewer: that
an original identity over a familiar feature set demonstrates product judgment,
while a recognisable skin invites the assumption that the project followed a
tutorial.

The owner weighed that and chose familiarity. That is a legitimate call — the
plan's position was a bet about reviewer perception, not a fact — and it is
recorded here so the trade is visible rather than accidental.

**What is preserved regardless:** no trademark. Loupe keeps its own wordmark and
lens glyph. No third-party logo, brand mark, or exact brand colour is
reproduced. The red is Loupe's own value, not a sampled one.

## Consequences

### The system rule is retired

The old system had one idea doing most of the work: *chrome is achromatic, and
colour means the machine found something.* Buttons, links, and navigation were
built from neutrals so the single accent could carry meaning — the semantic
layer, and nothing else.

Red on buttons and active navigation ends that. Colour now means "interactive",
which is the mainstream convention and the point of the change.

**The Mark survives by changing what distinguishes it.** It was recognisable by
being the only chromatic object; it is now recognisable by *form* — a stroke
with a node, under cited text and on the scrubber at the same timestamp. The
citation-seek moment in §7.4 still works: one object, two places.

This is a real loss. The old rule was teachable in one sentence and made the
interface self-explaining. Nothing replaces it; the product now relies on
convention instead, which is exactly what convention is for.

### Tokens are renamed, not just revalued

The old names encoded the old concept — `hall`, `riser`, `screen`, `citrine`
came from a dimmed auditorium. Keeping a token called `citrine` holding a red
value would be a name that lies, so they are renamed to describe role rather
than metaphor: `canvas`, `surface`, `rule`, `muted`, `ink`, `brand`.

### The freeze is re-set, not removed

§18.3 exists to stop endless re-litigation of visual decisions mid-build. This
amendment re-establishes it at the new system: six tokens, the same three
faces, the same eight type steps. No further palette changes without another
ADR.

### Errors are amber, not red

With red as the brand, a red error state is ambiguous — the same colour would
mean both "primary action" and "something went wrong". `danger` is therefore
amber. Unconventional, and the alternative was worse.

## Not changed

Typography (Bricolage Grotesque, IBM Plex Sans, IBM Plex Mono), the fluid type
scale, the four-step radius scale, the accessibility floor in §7.7, and the
motion policy in §7.3 all stand. §2's exclusion list and every other section of
the plan are untouched.
