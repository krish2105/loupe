# Decisions

The five decisions §17 requires before week 1, plus one the plan did not
anticipate. Recorded here rather than in conversation so the reasoning survives.

| # | Decision | Answer | Consequence |
|---|---|---|---|
| 1 | Class B curated channels | AI / ML engineering | The referenced catalogue mirrors what the project itself demonstrates. Also the densest source of CC-licensed Class A material, which keeps decisions 1 and 2 coherent. |
| 2 | Class A seed corpus | CC-licensed conference talks | Single clear speaker, dense retrievable content, natural topic shifts that make chapter detection meaningful, permissive licensing. ~100 talks to reach the §15 cap of 50 hours. |
| 3 | Language | English only, v1 | Drops the §10.3 cross-language demonstration and reduces §11.2's five eval categories to four. Recorded as a limitation below. |
| 4 | Recsys data | Synthetic only, disclosed | Executes §12.2 options 1 and 2. `watch_events.is_synthetic` makes the distinction queryable, not just a README claim. §12.3 offline evaluation still applies. |
| 5 | Product name | **Loupe** | A magnifier you look through to resolve hidden detail. Chosen over four alternatives because it is the only one that hands the design system a motif — the lens becomes the Mark. `loupe.video` appeared unregistered on a DNS check; **not yet verified or purchased.** |
| — | Theme (not in §17) | Both, designed independently | §7.2 says dark-first and never an inverted light theme; the build also needs a light/dark toggle. Resolved by designing two themes with opposite referents — a warm room and a cool lit surface — so the accent changes behaviour between them rather than merely changing value. |

## Consequences carried forward

**Eval set is four categories, not five.** §11.2 specifies factual lookup,
cross-video comparison, out-of-scope refusal, adversarial, and non-English.
English-only removes the last. The set stays at 100 hand-labelled triples,
redistributed across the remaining four. This belongs in the README limitations
section per §18.8.

**No cross-language retrieval demonstration.** §10.3 calls this a memorable
moment in a walkthrough. It is forfeited. `bge-m3` remains multilingual, so the
capability is latent and could be shown later at the cost of a few Arabic
videos plus RTL layout work.

**Domain unverified.** A DNS query showing no nameservers is strong evidence a
domain is unregistered, but not proof — registered-and-undelegated looks
identical. Confirm at a registrar before it goes into CI or a README badge.

## Open

- Media provider. §5.2 selected Bunny Stream; a re-evaluation was requested.
  See [`adr/0001-media-provider.md`](adr/0001-media-provider.md). Due at the
  Phase 1 gate, not before — Phase 0 touches no media.
- Supabase and Vercel provisioning. Blocks the Phase 0 gate from PARTIAL to PASS.
