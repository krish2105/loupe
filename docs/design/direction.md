# Loupe — design direction

> **Superseded in part by [ADR 0002](../adr/0002-visual-identity.md).** The
> palette, the token names, and the "chrome is achromatic" system rule below
> were replaced by a red-and-white identity with mainstream video-platform
> layout. Typography, the type scale, the radius scale, the motion policy, and
> the accessibility floor still stand. This document is kept because the
> reasoning it records is what ADR 0002 is a decision *against* — deleting it
> would leave the reversal looking uncontested.

Produced per plan §7.1 before any component existed, and locked. §18.3 freezes
the system at the week-4 gate; until then, changes are recorded here.

**Referent:** a dimmed auditorium and an optical instrument. Not "a video app".
Every decision below traces to one of those two.

---

## Palette

Six semantic tokens, two independently designed modes. Named from the subject's
world rather than from lightness values, so switching mode never means flipping
a number.

| Token | Role | Dark | Light |
|---|---|---|---|
| `hall` | Canvas | `#14110E` | `#F6F7F9` |
| `riser` | Elevated surface | `#1E1A17` | `#FFFFFF` |
| `rule` | Borders, scrubber track | `#2E2823` | `#E3E5EA` |
| `dust` | Secondary text, timecodes | `#9A9187` | `#5E636B` |
| `screen` | Primary text | `#F4F0E9` | `#14161A` |
| `citrine` | The semantic layer, only | `#E2D45E` | `#6E5F12` / ground `#F4EA6B` |

Plus `danger`, deliberately dull so it never competes with citrine:
`#C8756B` dark, `#9B3B2F` light.

### The rule that makes this a system

**Chrome is achromatic. Colour means "the machine found this."**

Buttons, links, active navigation, and focus rings are built from
`screen`/`dust`/`rule` alone. `citrine` appears on transcript matches, citation
marks, chapter boundaries, and the AI-ready state — nowhere else. A reader
learns the mapping in seconds and never unlearns it.

### Why the modes are not inversions

Dark's referent is a warm *room*: a brown-black at hue 30°, lit by an off-white
screen. Light's is a cool *lit surface*: a blue-neutral white with cool grey
text. Deliberately opposite in temperature.

This forces `citrine` to change *behaviour*, not just value. In dark it is a
**mark** — a stroke on near-black. In light it is a **ground** — a highlighter
wash behind near-black text. Same gesture, different physics.

### Measured contrast

| Pair | Dark | Light |
|---|---|---|
| `screen` on `hall` | 16.8:1 | 16.8:1 |
| `dust` on `hall` | 6.3:1 | 5.7:1 |
| `citrine` on `hall` | 12.6:1 | 5.9:1 |
| `danger` on `hall` | 5.7:1 | 6.4:1 |

All clear the §7.7 floor of 4.5:1. Verifiable at `/system`.

---

## Type

| Role | Face | Where |
|---|---|---|
| Display | **Bricolage Grotesque** (`wdth`, `opsz`) | Wordmark, H1, eyebrows, large timecode. Never below 20px |
| Body | **IBM Plex Sans** | Titles, chrome, descriptions, comments, AI answers |
| Utility | **IBM Plex Mono** | Timecodes, chapter times, chunk ids, eval numbers, stage names |

Bricolage was chosen for its width axis: width is magnification, which is what
the product's name means, so the display face can perform it. Plex was drawn for
technical products and ships a mono sibling, so one decision buys two roles.

AI answers get no fourth family — they are differentiated by measure (68ch) and
leading (1.7), so the machine's prose reads as a document while the chrome stays
instrument-like.

Eight fluid `clamp()` steps, ratio opening from 1.20 at 360px to 1.25 at 1440px.

Radius is a four-step scale: `0` scrubber, `4` marks and chips, `10` cards and
sheets, pill for the search capsule.

---

## Layout — "two grids"

Chrome is a 56px icon rail and nothing else. No header band. Search is a
floating capsule over the content field, because search-inside-video is the
thesis and burying it in chrome would contradict it.

The product has two grids, and they do not look alike:

- **Video grid** (home) — dense 16:9 thumbnail field, chrome recedes
- **Moment grid** (semantic search, citations) — small square frame, the
  **transcript line is the headline**, timecode-anchored

If a semantic-search result looked like an ordinary video card, the product
would have silently conceded its own thesis. Two grids is that argument made
structural.

Below 768px the rail becomes bottom navigation, the AI panel becomes a bottom
sheet, and the related rail moves below comments (§9).

---

## Signature element — the Mark

One graphic primitive meaning *this exact moment*. The only chromatic object in
the product, and the same object everywhere:

| Where | Form |
|---|---|
| Transcript, AI answer | underline beneath the cited phrase |
| Scrubber | 2px tick at that timestamp |
| Video card | the node alone — "AI ready" |
| Moment card | underline on the matched span |
| Light mode | the stroke fills into a highlighter ground |

**The moment it is remembered by:** you click a mark inside a sentence, and the
identical mark appears on the timeline as the player arrives there. One object,
two places, one meaning — a single point of magnification you can move. This is
the vehicle for §7.4's citation-seek.

---

## Calibration review

Per §7.1, the brief was run as if generating blind, then revised where it
matched a default.

**The blind default would have been:** `#0A0A0A` neutral-black, Inter, a violet
accent, glass cards, uniform 12px radius, a purple gradient on the AI panel.
That is calibration default #2 plus the AI-purple convention.

| Changed | Why |
|---|---|
| Violet → citrine | Colour here means "semantic layer", and violet-means-AI is the strongest cliché in this exact category. Citrine's lineage is the highlighter — marking a passage in a text is the literal gesture the product performs |
| Neutral/blue-black → warm brown-black | Blue-black is the tell of default #2; §7.2 asked for warm-neutral and the auditorium gives it a reason |
| Inverted light theme → opposite referent | Forced the accent to change behaviour, which is what makes the pair read as designed |
| Accent on all chrome → accent on the semantic layer only | Default #2 sprays its accent across every button. Restricting it makes the colour carry information |
| Inter/Geist → Bricolage + Plex | Not novelty: Bricolage's width axis lets the display face perform magnification |
| Filtered video grid → two structurally different grids | A search result shaped like a video card concedes the thesis |

**The accessory removed:** a fourth typeface, a reading serif for AI answers.
Cut; the answer is differentiated by setting instead.

**The risk taken:** a yellow-family accent on warm dark sits near warning
territory, which is why it is rarely chosen. Mitigated three ways — hue pulled
green-mineral (≤55°, citrine not amber), never used on error or warning
surfaces, and deployed as thin strokes rather than fills. If it reads as "alert"
in use, the fallback is a pale ice-blue.

---

## Corrections to this document

- The original plan claimed a **three**-step radius scale (0/4/10). The search
  capsule needs a pill radius, making it four. Recorded rather than glossed.
- The slide-placeholder thumbnail was first drawn in `riser`, which measured
  **1.15:1** against the canvas — the thumbnails were effectively invisible and
  the grid read as flat, which is fatal when §7.2 makes the grid the design.
  Rebuilt from `screen` at varying alpha so the projected screen emits. No new
  token; the six still hold.

---

## Freeze

§18.3 and the Phase 2 gate lock the system here: **no new colours, type scales,
or spacing values after this point.** The six tokens, three faces, eight type
steps, and four radii above are the whole vocabulary for the remaining phases.

Anything that feels like it needs a new value is a signal that an existing one
is being used wrongly. Changing this list later requires an explicit recorded
decision, the same as §18.7 demands for the exclusion list.
