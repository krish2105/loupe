# Mashhad — Implementation Plan

**A video platform with a semantic layer**

| | |
|---|---|
| **Owner** | Krishna Mathur |
| **Version** | 1.0 |
| **Date** | August 2026 |
| **Duration** | 12 weeks |
| **Commitment** | 20+ hrs/week |
| **Status** | Approved for build |

---

## 1. Executive summary

Mashhad is a full-stack video platform built to demonstrate production-grade system design across media infrastructure, retrieval, recommendation, and premium frontend engineering.

It reproduces the complete feature surface of a modern video product — home feed, shorts, subscriptions, history, watch later, playlists, search, video page, channel, comments, notifications — and adds a semantic layer that mainstream video platforms do not offer: search *inside* videos, ask a video questions with clickable timestamp citations, automatically generated chapters, and AI-composed playlists.

**The strategic bet:** feature parity is table stakes and proves nothing on its own. The differentiator is the transcript-grounded intelligence layer, and the proof of that layer is a **published retrieval benchmark** — not a demo GIF.

**Positioning:** own brand, own visual identity, own name. Feature parity with YouTube; zero trademark, logo, or visual cloning. A pixel-identical skin reads as a tutorial follow-along. An original identity over the same feature set reads as a product engineer.

**Headline claim on completion:** *"A video platform where you can search inside videos and ask them questions. Retrieval benchmark published. Runs for under $10 a month."*

---

## 2. Strategic rationale

### 2.1 Why this project

| Signal it produces | Where it comes from |
|---|---|
| System design at scale | Multi-service architecture, async pipeline, stage machine |
| Media infrastructure | Transcoding, adaptive bitrate, CDN, signed playback |
| Applied retrieval | Chunking strategy, hybrid search, timestamp-accurate citation |
| Recommendation systems | Two-stage candidate generation and ranking with offline eval |
| Evaluation rigour | Hand-labelled benchmark with published metrics |
| Premium frontend | Design system, orchestrated motion, accessibility floor |
| Cost consciousness | Documented sub-$10/month operating envelope |

Agentic orchestration and responsible AI documentation are the two most underrepresented skills in candidate portfolios. This project demonstrates both without labelling itself as either.

### 2.2 The constraint that shapes everything

The YouTube Data API cannot serve as a backend for this product. The daily quota is 10,000 units; a single search call costs 100 units, yielding roughly 100 searches per day. There is no self-service path to more quota, and extension requests citing bulk data harvesting are routinely rejected. Critically, the Data API does not expose transcripts at all — and every AI feature in this plan depends on transcripts.

**Consequence:** the platform owns its catalogue. This is not a workaround. It is strictly better, because semantic search over owned embeddings can do things platform search cannot — and that capability *is* the portfolio argument.

---

## 3. Scope

### 3.1 In scope

**Product surfaces (11):** Home · Shorts · Subscriptions · History · Watch Later · Playlists · Search · Video page · Channel · Comments · Notifications

**AI capabilities (6):** Video summariser · Ask-video · Semantic search · Auto chapters · Personalised feed · AI playlist generation

**Cross-cutting:** authentication, responsive design system, accessibility floor, async processing pipeline, observability, published evaluation.

### 3.2 Explicitly out of scope

Written into the README as deliberate exclusions:

- Content moderation and trust & safety
- Monetisation, ads, creator payouts
- Live streaming and real-time chat
- Native mobile applications
- Multi-tenant creator analytics dashboards
- Video-native (non-transcript) visual retrieval

Knowing what to leave out is itself a hiring signal. Do not silently expand this list.

### 3.3 Success criteria

| Dimension | Target | Verification |
|---|---|---|
| Functional | 11 surfaces live, 6 AI features working on owned content | Manual acceptance walkthrough |
| Performance | Home LCP < 2.5s; player time-to-first-frame < 1.5s | Lighthouse + real-device test |
| Scale proof | 200+ videos indexed, 50+ hours transcribed and embedded | Pipeline dashboard |
| Retrieval quality | Precision@5, citation accuracy ±5s, faithfulness, refusal accuracy — all published | Hand-labelled eval set |
| Recsys quality | Beats popularity baseline on recall@20 and NDCG@20, or failure analysed | Offline holdout eval |
| Accessibility | Keyboard-complete, reduced-motion honoured, contrast ≥ 4.5:1 | Axe audit + manual keyboard pass |
| Cost | Under $10/month | Documented breakdown in README |

---

## 4. Content model — the hybrid architecture

This is the single most consequential design decision. It determines the schema, the UI, and what the AI layer can honestly claim.

Two content classes with **different capability sets**, treated as a first-class domain concept rather than an edge case.

| | **Class A — Owned** | **Class B — Referenced** |
|---|---|---|
| Source | Direct uploads + Creative Commons / public-domain catalogue | Curated channel metadata, ingested once |
| Storage | Bunny Stream; own HLS renditions | Not stored; embedded player |
| Transcript | Yes — WhisperX, word-level timestamps | No; assume none |
| Playback | Custom player, full control | Third-party embed, custom controls hidden |
| AI features | All six | Metadata-level only |
| Search coverage | Full-text + semantic over transcript chunks | Title, description, tags |
| Purpose | **Depth** — proves the intelligence layer | **Breadth** — makes the feed feel like a real product |

### 4.1 Why Class B exists

A video platform with 40 items looks like a demo. A platform with 2,000 items in the feed and 200 deeply indexed looks like a real product with an indexing backlog — which is exactly what every real platform is.

### 4.2 Non-negotiable rules

1. **Never call third-party search at runtime.** A nightly batch walks curated channels' uploads playlists at 1 unit per 50 items and writes to the local index. Everything is served from the local index.
2. **Maintain an explicit quota ledger.** Log consumption per run. Fail closed when the budget is exhausted.
3. **Do not close the capability gap by unofficial means.** Class B carries no transcript. The asymmetry is a legitimate architectural fact; document *why* in the README. Fabricating parity through unofficial extraction is both a licensing risk and worse engineering.
4. **Design the unavailable state early.** Every AI surface needs a designed empty state for Class B content. Retrofitting this in week 9 is painful and it will look like an afterthought.

---

## 5. Service architecture

| Service | Responsibility | Boundary rule |
|---|---|---|
| **Web app** | All UI, routing, SEO, session | Never talks to the media provider or LLM directly |
| **Core API** | CRUD, authorisation, feed assembly, search orchestration | Stateless; horizontally scalable |
| **Media service** | Upload signing, provider webhooks, playback URL signing | Sole holder of media provider credentials |
| **Ingest worker** | Nightly referenced-content sync, quota accounting | Idempotent; safe to re-run at any time |
| **Pipeline worker** | Transcription, normalisation, chunking, embedding, chapter detection | Queue-driven; never blocks a request |
| **AI service** | Summarise, ask-video, playlist composition | Owns all prompts and model routing |
| **Ranker** | Candidate generation and scoring for the personalised feed | Reads precomputed features; sub-100ms budget |

### 5.1 Architectural principles — lock these in week 1

**Async by default.** Upload returns immediately in a `processing` state. Every downstream stage is a queued job. The UI must be designed for partial availability: a video is watchable long before it is searchable.

**Idempotency everywhere.** Every pipeline job keyed on `(video_id, stage, version)`. The pipeline will be re-run many times during development. Make that free.

**Single source of truth for state.** One `processing_status` enum per video with explicit named stages. Not a scatter of boolean flags.

**Signed playback URLs.** Even for openly licensed content. It costs nothing and demonstrates media security awareness.

**Player abstraction from day one.** A single player context exposing seek, play, pause, and current time. The AI panel, chapter list, and scrubber all consume it. Build this in week 1 even though it isn't needed until week 6 — without it, the citation-seek feature becomes prop-drilling spaghetti.

### 5.2 Technology selections

| Layer | Selection | Rationale |
|---|---|---|
| Frontend | Next.js App Router, Tailwind, Motion | Motion imported from `motion/react`, not the legacy package |
| Player | `hls.js` with custom controls | Provider HLS URLs consumed directly; own player required for AI features |
| Media infrastructure | Bunny Stream | Storage ~$0.005/GB/month, delivery from ~$0.01/GB, transcoding included at no per-minute charge. Roughly $5–15 for 100 hours hosted with 10k monthly views |
| Backend API | FastAPI | Same language as the ML pipeline; no context switching |
| Database | Postgres with pgvector (Supabase) | Metadata, chunks, embeddings, and watch events in one system |
| Queue | Redis with a worker process | Transcription is long-running; serverless is the wrong shape |
| ASR | WhisperX | Word-level timestamps. Plain Whisper does not give clean word timing, and citation accuracy depends on it |
| Embeddings | `bge-m3` | Multilingual, open-weight, no per-call cost |
| LLM | Gemini Flash primary, Groq fallback | Long context for single-pass summarisation; verified free-tier availability |
| Auth | Supabase Auth | Four surfaces depend on real user identity |

**Alternatives considered and rejected:** Cloudflare Stream (simpler but per-minute pricing is worse at this library size); Mux (best analytics, highest cost, unjustified at portfolio scale); self-hosted FFmpeg transcoding (weeks of work for zero portfolio signal).

---

## 6. Data model

Entity-level specification. Field names are indicative; the implementing agent finalises types and constraints.

### 6.1 Core content

| Entity | Key fields | Notes |
|---|---|---|
| `videos` | id, source_class, external_id, title, description, duration, published_at, channel_id, processing_status, visibility | `source_class` drives every downstream capability decision |
| `channels` | id, handle, name, avatar, banner, description, source_class | Referenced channels are synthetic records, not real users |
| `video_assets` | video_id, provider_guid, hls_url, thumbnail_sprite_url, resolutions | Class A only |
| `video_stats` | video_id, view_count, like_count, comment_count | Denormalised counters, updated asynchronously |

### 6.2 Identity and relationships

The four "list" surfaces are one abstraction with different semantics. Build the abstraction once; get four surfaces.

| Entity | Key fields | Serves |
|---|---|---|
| `users` | id, handle, display_name, avatar | — |
| `subscriptions` | user_id, channel_id, notify_enabled, created_at | Subscriptions, Notifications |
| `watch_events` | user_id, video_id, position_sec, watch_pct, completed, occurred_at | History, resume, recsys training |
| `saved_items` | user_id, video_id, list_type, added_at | Watch Later, Liked |
| `playlists`, `playlist_items` | owner_id, title, visibility, generated_by, rationale | Playlists, AI playlists |
| `comments` | id, video_id, user_id, parent_id, body, created_at, edited_at | One reply level only |
| `notifications` | user_id, type, actor_id, target_id, read_at | Fan-out on write |

### 6.3 Intelligence layer

| Entity | Key fields | Notes |
|---|---|---|
| `transcripts` | video_id, language, engine, engine_version, full_text | Un-normalised, for display |
| `transcript_chunks` | id, video_id, chunk_index, start_sec, end_sec, speaker, text_normalised, text_display, embedding, embedding_model | The vector table. Timestamps are never flattened |
| `chapters` | video_id, index, start_sec, end_sec, title, confidence | Generated, not user-authored |
| `video_summaries` | video_id, model, tldr, key_points, generated_at | Key points each carry a start_sec. Cached permanently |
| `ask_sessions`, `ask_turns` | video_id, user_id, question, answer, cited_chunk_ids | Doubles as the raw material for the eval set |

### 6.4 Recommendation features

| Entity | Purpose |
|---|---|
| `user_topic_affinity` | Nightly precompute; user × topic × score |
| `video_similarity` | Top-K neighbours per video from content embeddings |
| `feed_candidates` | Materialised per user, refreshed nightly |

### 6.5 Two decisions to be able to defend

1. **`transcript_chunks` stores both a normalised text (embedded) and a display text (shown).** Normalising for retrieval while displaying the original is the correct separation and almost no implementation does it.
2. **`watch_events` is append-only and never mutated.** Resume position is a read-side aggregate. This is what makes the recommendation model trainable later rather than requiring a schema migration.

---

## 7. Design system and frontend direction

### 7.1 Working method — mandatory

The implementing agent must follow this two-skill sequence. Direction before implementation, always.

**Step 1 — `frontend-design` skill: lock the direction.**

Produce a written design plan before any component exists:

- **Palette:** 4–6 named hex values, described as a system
- **Type:** a characterful display face used with restraint, a complementary body face, and a utility face for captions and data
- **Layout:** the concept, expressed in prose and ASCII wireframes
- **Signature:** the single element this product will be remembered by

Then review the plan against the brief. If any part reads like the default you would produce for any similar product, revise it and state what changed and why.

**Calibration — the three current AI-generated defaults to avoid:** warm cream background with high-contrast serif and terracotta accent; near-black with a single acid-green or vermilion accent; broadsheet layout with hairline rules and zero border-radius. All are legitimate for some briefs. None is a *choice*.

**Step 2 — `premium-frontend` skill: implement the motion and components.**

Load `references/setup.md` first, then `references/motion.md` for the animation cookbook and `references/effects.md` for glassmorphism, bento, marquees, and magnetic interactions. Do not improvise animation code when a reference pattern exists.

### 7.2 Direction constraints for this brief

| Decision | Constraint |
|---|---|
| Theme | Dark-first, designed as primary — never an inverted light theme |
| Canvas | Near-black but not pure black; a warm-neutral base reads more premium |
| Accent | Exactly one. Not acid green. Not video-platform red. Restrained enough to read as brand, not alert |
| Typography | Fluid `clamp()` sizing across all breakpoints; deliberate display/body pairing |
| Density | Content-forward. The thumbnail grid *is* the design; chrome recedes |
| Boldness budget | Spend it in one place. In a video product, the video is the boldness |

### 7.3 Motion policy

| Rule | Reason |
|---|---|
| Only `transform` and `opacity` animate | Anything else drops frames during scroll |
| Four signature moments, no more | One orchestrated moment beats twenty scattered effects |
| `backdrop-filter` on navigation and player chrome only | Costs 15–30% FPS on mid-tier Android; never on the grid |
| Every motion gated behind reduced-motion with a static fallback | Non-negotiable accessibility floor |
| Smooth scroll subtle; native experience for reduced-motion users | "Buttery" is a feel, not a distance |

### 7.4 The four signature moments

1. **Thumbnail → player shared-element expansion.** Motion `layoutId`; the card expands into the player position. This single transition is what makes the product feel native rather than web.
2. **The citation seek.** An answer timestamp is clicked; the player seeks and a marker pulses on the scrubber. This is the product's defining interaction.
3. **Chapter-segmented scrubber** with sprite-sheet hover preview.
4. **Shorts spring-settle** on the vertical snap feed — momentum that settles rather than snapping hard.

### 7.5 Component inventory

Build once, reuse everywhere.

- **Shell:** app frame, collapsible sidebar, top bar with search, mobile bottom navigation
- **Content:** video card (three density variants), channel card, playlist card, chip row, matching skeleton for each
- **Player:** shell, custom controls, chapter-segmented scrubber, hover preview, settings sheet, ambient glow
- **AI:** panel container, summary block, ask thread, citation chip, chapter list, source-unavailable state
- **Feedback:** toast, empty state, error state, loading shimmer

### 7.6 Copy standards

Words are design material, not decoration. Active voice by default. A control states exactly what happens when used. An action keeps the same name through the entire flow — a button that says "Publish" produces a toast that says "Published." Errors explain what went wrong and how to fix it; they do not apologise and are never vague. An empty screen is an invitation to act. Name things by what the person controls, never by how the system is built.

### 7.7 Quality gate — every phase, no exceptions

- Responsive to 360px width; nothing clips or requires horizontal scroll
- Keyboard-complete: visible focus rings, logical tab order, no traps, real `button` and `a` elements
- `prefers-reduced-motion` respected; content remains fully usable
- 60fps scroll on a mid-range Android device
- No layout shift caused by animation
- Body text contrast ≥ 4.5:1
- Semantic heading hierarchy intact; motion never costs the document

---

## 8. Tooling — MCP and skills

### 8.1 21st MCP (component generation)

**Important:** the Magic MCP server has been superseded by the unified 21st MCP, and all previously issued Magic API keys were reset. A fresh key is required from `21st.dev/mcp` before the first session.

| Item | Detail |
|---|---|
| Install | `npx @21st-dev/cli@latest init --client claude` |
| Key | Fresh key from `21st.dev/mcp`. Old Magic console keys no longer work anywhere |
| Legacy configs | Existing `@21st-dev/magic` entries still function as a compatibility proxy, but migration to the CLI is recommended |
| Emitted stack | React + TypeScript on shadcn/ui, Tailwind, Radix |
| Invocation | Natural language — ask the agent to search or generate. The old `/ui` and `/21` triggers were a convention of legacy tool descriptions, not protocol |
| Known issue | Transient hosted-API failures are common in Claude Code. Confirm latest version, valid key, remaining quota, and retry |

**Rules of engagement — this matters more than the setup:**

1. **Direction first, generation second.** Never generate a component before the `frontend-design` plan is written and reviewed. Generated components arrive with their own aesthetic opinions; without a locked token system they will pull the product toward a generic shadcn default.
2. **Generate primitives, not signature elements.** Use the MCP for forms, sheets, menus, tables, toasts, and dialogs. The player, the AI panel, the video card, and the four signature moments are hand-built.
3. **Re-token everything on arrival.** Every generated component is refactored to the project's token system before it is committed. No component enters the codebase carrying its own colour or spacing values.
4. **Search before generating.** The catalogue is large; retrieving an existing component is faster and more consistent than generating a new one.

### 8.2 Skill usage per phase

| Phase | Skills invoked |
|---|---|
| 0 — Foundations | `frontend-design` (token system), `karpathy-guidelines` |
| 1 — Media spine | `karpathy-guidelines` |
| 2 — Core surfaces | `premium-frontend`, 21st MCP, `karpathy-guidelines` |
| 3 — Identity surfaces | `premium-frontend`, 21st MCP |
| 4 — Referenced ingest | `karpathy-guidelines` |
| 5 — Pipeline | `karpathy-guidelines` |
| 6 — AI layer | `premium-frontend` (AI panel), `karpathy-guidelines` |
| 7 — Eval | — |
| 8 — Shorts | `premium-frontend` |
| 9 — Recsys | `karpathy-guidelines` |
| 10 — Ship | `humanizer` (README and writeups) |

---

## 9. Video page and player specification

The video page is the product. It receives disproportionate specification effort.

**Layout regions:** player · title and action bar · channel strip · description with expand · AI panel · comments · related rail.

On mobile the AI panel becomes a bottom sheet and the related rail moves below comments.

### 9.1 Player behavioural contract

| Behaviour | Requirement |
|---|---|
| Startup | Adaptive bitrate from the HLS manifest. Never force a resolution |
| Resume | If a prior watch event exists past 10s and under 95%, resume with a dismissible notice |
| Progress | Write position every 10s and on pause/unload. Debounced, fire-and-forget |
| Chapters | Scrubber segments by chapter; hover shows chapter title plus sprite frame |
| External seek | Public seek method consumed by the AI panel. Must be smooth, never a reload |
| Keyboard | Space, arrow keys, J/K/L, F, M, number-key seek |
| Class B content | Swaps to the third-party embed; custom controls hide; AI panel shows the unavailable state |

---

## 10. Processing pipeline

### 10.1 Stage machine

Explicit, resumable states. Failures park at `failed_<stage>` with a retry count. The UI surfaces `indexed` as "AI ready."

`uploaded → transcoding → transcoded → transcribing → transcribed → chunking → embedding → indexed → enriched`

### 10.2 Stage specifications

| Stage | Input | Output | Design notes |
|---|---|---|---|
| Transcode | Source file | HLS renditions, thumbnail sprite | Provider-handled; consume the webhook |
| Transcribe | Audio track | Word-level timestamped segments | Word timing is a hard requirement — citation accuracy depends on it |
| Normalise | Raw transcript | Cleaned text plus preserved display copy | Strip bracketed caption annotations and filler tokens; collapse whitespace; retain the original |
| Chunk | Normalised transcript | 300–600 token chunks, ~50 token overlap | Split on natural pauses and topic shifts, never fixed windows. Every chunk carries video_id, start_sec, end_sec, speaker |
| Embed | Chunks | Vectors | Pin the model version in the row. Models will change; stale rows must be identifiable |
| Chapter detect | Chunk embeddings | Boundaries plus titles | Two-stage: cosine drift between consecutive windows finds boundaries; an LLM names them. Not a single prompt |
| Summarise | Full transcript | TL;DR plus timestamped key points | Single long-context pass; cached permanently |

### 10.3 Operational decisions

**Backfill strategy.** Transcription runs at roughly 1× realtime on CPU. Execute the initial 50-hour batch on free GPU compute, export as a portable artifact, and load into the database. Do not attempt this on the API host.

**Cost ceiling.** Enforce a hard monthly cap on transcription minutes inside the worker. Not by discipline — by code.

**Language handling.** Detect and store per-video language. Multilingual embeddings give cross-language retrieval at no additional cost. Demonstrate this deliberately; it is a memorable moment in any walkthrough.

**Versioning.** `engine_version` and `embedding_model` on every generated row enables selective re-indexing rather than a full rebuild.

---

## 11. AI feature contracts

Defined by input, output, failure mode, and cache policy. This is the level at which a technical lead reviews.

| Feature | Input | Output contract | On failure | Cache |
|---|---|---|---|---|
| **Summariser** | Full transcript | TL;DR (≤3 sentences) plus 5 key points, each with start_sec | Hide the block. Never show a partial summary | Permanent; invalidated on re-transcription |
| **Ask-video** | Question plus this video's chunks only | Answer plus 1–4 citations with start_sec; explicit "not covered in this video" when retrieval is weak | Return the refusal, never a guess | Session-scoped |
| **Semantic search** | Query | Ranked videos, each with best-matching moment and start_sec | Degrade to keyword-only, flagged in the UI | Query-level, short TTL |
| **Chapters** | Chunk embeddings | Ordered segments with titles and confidence | Render an unsegmented scrubber | Permanent |
| **Personalised feed** | Watch history plus affinities | Ranked list with reason codes | Fall back to trending | Nightly precompute |
| **AI playlists** | Natural-language brief | Ordered list plus written rationale for the ordering | Return fewer items rather than padding with poor matches | Saved as a real playlist |

### 11.1 The two contracts that make this credible

**Ask-video must refuse.** A confident wrong answer about video content is the failure mode that gets noticed in a demo. Threshold on retrieval score and refuse below it. Track refusal rate as a headline metric — it is a feature, not a defect.

**Citations must seek correctly.** If a timestamp lands on the wrong moment, the entire intelligence layer loses credibility instantly. This is the reason word-level ASR is non-negotiable. Manually spot-check 50 citations in week 9.

### 11.2 Evaluation — built in at week 6, not bolted on at the end

Hand-label 100 question / answer / timestamp triples across 20 videos, spanning five categories: factual lookup, cross-video comparison, out-of-scope (should refuse), adversarial, and non-English.

**Metrics published:** retrieval precision@5 · citation timestamp accuracy within ±5s · answer faithfulness · refusal accuracy.

**Methodological note to include in the writeup:** LLM-as-judge scoring carries measurable, published biases. Pin the judge model, use tolerance bands rather than exact thresholds, and hold a stable golden set so non-deterministic output does not produce false regressions. This paragraph is worth more in a technical interview than another 500 lines of feature code.

---

## 12. Recommendation system

### 12.1 Two-stage design

**Stage 1 — candidate generation.** Union of: content-similarity neighbours of recently watched videos; new uploads from subscribed channels; topic-affinity matches; a trending pool. Target ~500 candidates.

**Stage 2 — ranking.** Gradient-boosted model over predicted watch percentage, recency decay, channel affinity, topic affinity, a novelty penalty for already-seen items, and a diversity term preventing single-topic collapse.

### 12.2 The cold-start problem — handled with disclosure

There will be no real interaction data. Options in order of integrity:

1. Generate synthetic watch histories from plausible persona models, **clearly labelled as synthetic** in the README and in a debug panel
2. Ship a content-only ranker for new users; document that collaborative signal activates at N interactions
3. Recruit 15–20 real users from the cohort for a two-week signal window

Execute 1 and 2 as the baseline. Execute 3 if time allows.

**Never present synthetic results as real user data.** The disclosure is the professional signal.

### 12.3 Offline evaluation

Hold out the final 20% of each synthetic user's history. Report recall@20 and NDCG@20 against a popularity baseline. If the model does not beat popularity, say so and analyse why. A documented negative result is a stronger portfolio entry than an unverified claim.

---

## 13. Roadmap

Each phase has a hard definition of done. Do not begin the next phase until the current one passes its gate.

| Phase | Weeks | Deliverable | Gate |
|---|---|---|---|
| **0 — Foundations** | 1 | Repo, schema, auth, design tokens, CI, staging deploy | A logged-in user sees an empty shell on a public URL |
| **1 — Media spine** | 2 | Upload → transcode → HLS → custom player | One video plays adaptively with working seek and resume |
| **2 — Core surfaces** | 3–4 | Home, Video page, Channel, Comments | A visitor can browse, watch, and comment. **Design system locked — no new visual decisions after this gate** |
| **3 — Identity surfaces** | 5 | Subscriptions, History, Watch Later, Playlists | All four built on the shared list abstraction, not four one-offs |
| **4 — Referenced ingest** | 6 | Nightly metadata sync, quota ledger, capability-aware UI | 1,500+ Class B videos in the feed; unavailable states designed |
| **5 — Pipeline** | 7–8 | Transcription, chunking, embedding, chapter detection | 50 hours indexed; stage machine survives forced failure injection |
| **6 — AI layer** | 9 | Summariser, ask-video, semantic search | Citation-seek works end to end; refusal behaviour verified |
| **7 — Evaluation** | 10 | Labelled eval set, published metrics | Numbers and methodology in the README |
| **8 — Shorts** | 10 | Vertical snap feed with preloading | No stutter on a mid-range Android device |
| **9 — Recsys** | 11 | Candidate generation, ranker, offline eval | Beats popularity baseline, or the failure is analysed |
| **10 — Ship** | 12 | AI playlists, notifications, polish, demo video, writeups | Public URL, three-minute demo, architecture writeup |

**The only genuine parallelism available:** the transcription backfill runs unattended. Start it at the opening of week 7 and build UI while it processes. Everything else is sequential.

**The Shorts implementation note:** a vertical feed feels broken unless the next item is already buffered. Use CSS scroll-snap for the track, an intersection observer for play/pause, preload manifests for index +1 and +2, and destroy players beyond ±3. Get this wrong and five video elements will fight for bandwidth.

---

## 14. Environments and cost

| Concern | Approach |
|---|---|
| Environments | Local · staging (auto-deploy from main) · production (tagged releases) |
| Web hosting | Vercel |
| API and workers | Render or Fly.io — long-running processes required, so not serverless |
| Database | Supabase Postgres with pgvector |
| Media | Bunny Stream |
| Queue | Redis |
| Secrets | Platform secret managers. Nothing in the repository, ever |
| Observability | Structured logs, error tracking, and a pipeline dashboard showing video counts per stage |

**Monthly envelope:** media ~$4 · database free tier · hosting $0–7 · LLM inference on free tiers with a hard enforced cap. **Target: under $10.**

Publish the cost breakdown in the README. Cost consciousness is a 2026 hiring signal and almost no portfolio project demonstrates it.

---

## 15. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Transcription backlog overruns the timeline | High | High | Cap the owned library at 50 hours; batch on free GPU in week 7 |
| Third-party quota exhaustion during ingest | Medium | Medium | Nightly batch only; uploads-playlist reads at 1 unit; explicit ledger with fail-closed |
| Shorts performance on mid-range devices | High | Medium | Preload ±2, destroy beyond ±3, test on real budget hardware in week 8 |
| Recommendation model unconvincing without users | High | Medium | Synthetic data with explicit disclosure plus offline eval against baseline |
| Citation timestamps drift | Medium | High | Word-level ASR; manual spot-check of 50 citations in week 9 |
| Scope creep into moderation or monetisation | High | High | Written exclusion list in the README, revisited at every phase gate |
| Design system decided late | Medium | High | Locked at the week 4 gate; no new visual decisions afterwards |
| Coursework collision | High | High | Weekly phase gates. If two consecutive gates slip, invoke the cut list |

### 15.1 Pre-agreed cut list

If two weeks behind, cut in this order:

1. AI playlist generation
2. Notifications
3. Shorts

**Never cut the evaluation phase.** It is the highest value-per-hour item in the plan.

---

## 16. Portfolio packaging

The build is half the value. Plan the artifacts from week 1.

| Artifact | Content |
|---|---|
| **README** — the primary deliverable | Problem, architecture diagram, capability matrix for the two content classes, eval results, cost breakdown, explicit limitations, "what I would do next" |
| **Architecture writeup** | Standalone document on the hybrid content model and the stage machine. This is the technical writing sample |
| **Three-minute demo video** | Upload → processing → watching → asking a question → clicking a citation → semantic search finding a moment. Show the product, not the codebase |
| **Three posts, spaced across the final fortnight** | (1) the media pipeline, (2) the eval results, (3) the recsys honesty problem. The third will outperform the other two |

---

## 17. Decisions required before week 1

| # | Decision | Why it blocks |
|---|---|---|
| 1 | Which 20–30 curated channels for Class B ingest? | A themed catalogue reads far better than a random one; determines the ingest config |
| 2 | Which seed corpus for Class A? | Domain coherence matters more than volume — it is what makes semantic search demos land |
| 3 | Arabic in scope, or English-only v1? | Bilingual is a genuine regional differentiator but adds roughly two weeks across transcription, retrieval, and UI |
| 4 | Real users in week 11, or synthetic only? | Recruiting needs lead time; decide now |
| 5 | Product name and domain | The design direction cannot be locked without a name |

---

## 18. Working agreement for the implementing agent

1. **Phase gates are binding.** Do not begin a phase until the previous gate passes. Report gate status explicitly at the end of each phase.
2. **Direction before implementation.** The `frontend-design` plan is written and reviewed before any component is generated or built.
3. **The design system is frozen at the week 4 gate.** After that, no new colours, type scales, or spacing values.
4. **Surface assumptions rather than inventing.** Where this plan is ambiguous, state the assumption and proceed; do not silently choose.
5. **Make surgical changes.** Prefer the smallest change that satisfies the requirement. Do not refactor adjacent code opportunistically.
6. **Every phase ends with the quality gate run**, not with a promise to run it later.
7. **The exclusion list in §3.2 is not negotiable** without an explicit decision recorded in this document.
8. **When a shortcut is taken, document it in the README limitations section** rather than leaving it implicit.

---

*End of plan.*
