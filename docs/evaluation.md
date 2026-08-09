# Evaluation

Plan ref: §11.2. §15.1 says never cut this phase; §2 calls the published
benchmark the proof of the intelligence layer.

---

## The honest headline

**Loupe does not yet have a benchmark.**

What it has is a working evaluation harness, tested metric implementations, a
hand-labelled golden set, and a real result from running them. What it does not
have is a corpus worth benchmarking: the owned talks point at a test stream
with no speech, so the transcripts are fixture output.

That distinction is the whole point of this document. A table of numbers
computed over invented transcripts would be arithmetically correct, would look
exactly like a benchmark, and would mean nothing. It would be the single most
misleading artefact this repository could contain.

So the numbers below are labelled for what they are, and the ones that cannot
be meaningful yet are absent rather than filled in.

## What is and is not measurable on the current corpus

| Metric | Status | Why |
|---|---|---|
| Refusal accuracy | **Meaningful** | An out-of-scope question is out of scope whatever the corpus. The refuse/answer decision is genuinely under test. |
| Citation timestamp accuracy | **Meaningful** | Expected timestamps are read from real chunk boundaries. This measures whether a citation lands where it claims — the §11.1 property everything rests on — and is corpus-independent. |
| Faithfulness | **Meaningful but uninformative** | Extractive answering quotes its sources, so this is ~1.0 by construction. It is a regression guard, not a quality measure. |
| Retrieval precision@5 | **Partially meaningful** | Questions paraphrase rather than quote, so retrieval does semantic work. But fixture vocabulary is small and repetitive, which makes it easier than real speech. |
| Cross-video comparison | **Not measurable** | Every fixture transcript is identical. The category exists and is empty rather than filled with cases that would score well and prove nothing. |
| Non-English | **Out of scope** | §17 decision 3 chose English only. |

## Results — fixture corpus, 24 cases

Golden set `fixture-v1`, answerer `extractive-v1`, embeddings `bge-m3`,
timestamp tolerance ±5s.

```
refusal accuracy              0.792
refusal rate                  0.375
false answer rate             0.357   ← the one that matters
citation timestamp accuracy   0.600
faithfulness (lexical)        0.995
```

By category:

```
factual         10/10 decided correctly
out_of_scope     5/6
adversarial      4/8   ← the failure
```

### What this says

**The refusal threshold is too permissive.** Five of fourteen questions that
should have been refused were answered. §11.1 names this exact failure — "a
confident wrong answer about video content is the failure mode that gets
noticed in a demo" — and the harness found it on the first run.

**The failures are concentrated in the adversarial category**, which is what
that category exists to detect. Questions that sound like this talk but are
not in it — "which optimiser does the speaker recommend", "what dataset was
used for pretraining" — retrieve passages that are topically close enough to
clear a 0.42 threshold. Out-of-scope questions about sourdough score 0.33 and
are refused correctly; domain-adjacent ones are the hard case.

**Citation accuracy of 0.60 is not good.** Two in five answered questions cited
a moment more than five seconds from where a human said the answer was. On
fixture text this is partly an artefact — the transcript repeats similar
content, so several chunks are near-equally plausible — but it is not
dismissible, and it is the metric §11.1 says the credibility of the whole layer
depends on.

### Threshold sweep

Recomputed from recorded scores, so it costs nothing:

| Threshold | Accuracy | False answers | False refusals |
|---|---|---|---|
| 0.34 | 0.500 | 12 | 0 |
| 0.38 | 0.625 | 9 | 0 |
| **0.42** | **0.792** | **5** | **0** |
| 0.46 | 0.958 | 1 | 0 |
| 0.50 | 1.000 | 0 | 0 |
| 0.54 | 0.917 | 0 | 2 |
| 0.58 | 0.750 | 0 | 6 |

**The threshold has deliberately not been changed to 0.50.**

It would produce a perfect score, and that is the reason not to do it. Picking
the value that maximises a 24-case fixture score is fitting the threshold to
the fixture, not tuning the system — the published number would improve and the
product would be no more trustworthy. §11.2 is explicit that a golden set must
stay stable so non-deterministic output does not produce false regressions;
the same logic forbids tuning against it.

The threshold is a decision for a real corpus. What the sweep establishes is
that the decision is consequential and that there is a value where the two
error types trade off — which is worth more than a tuned number.

## Methodology

§11.2 asks for this note specifically, and says it is worth more in a technical
interview than another five hundred lines of feature code.

**LLM-as-judge is not used, and when it is, it will be pinned and reported.**
Published work documents measurable biases in LLM judges: position bias,
verbosity bias, and self-preference for a judge's own family of models. Any
judged score here would carry those without a way to separate them from the
result. The faithfulness number above is a reproducible lexical floor for that
reason; a judged score would be reported alongside it, never instead of it,
with the judge model and version pinned.

**Tolerance bands, not exact thresholds.** A citation is correct within ±5s.
The "right" moment for a statement is itself fuzzy — a labeller marking where
an idea begins disagrees with themselves by a second or two on a second pass —
so demanding exactness would measure labeller precision rather than system
accuracy.

**A stable golden set.** The set is versioned and its cases are not edited in
response to results. A set that changes when the system changes cannot detect
a regression.

**A golden set is bound to its corpus.** Every label encodes a claim about a
specific transcript. The set records which corpus it was authored against and
the runner *refuses to score* against a different one — because nothing about
a mismatched run looks wrong, and "remember not to do that" is not a safeguard.

**Errors are counted, not dropped.** A case that raised is reported as an error
rather than excluded, so a partially failed run cannot look like a clean one.

**The dangerous failure is reported separately.** Accuracy hides false answers:
a system that answers everything scores well on a mostly-answerable set while
doing the one thing that discredits it. False answer rate is published on its
own line.

## What would make this a benchmark

1. **Real audio.** CC-licensed conference talks for the owned corpus, run
   through WhisperX (`uv sync --extra asr`). Everything else already works.
2. **Re-labelling.** `fixture-v1` becomes invalid the moment real transcripts
   land — enforced, not remembered. A new set is authored by reading the real
   transcripts.
3. **Scale.** §11.2 asks for 100 triples across 20 videos. This set has 24
   across effectively one, because all fixture transcripts are identical.
4. **A threshold decision** made against that corpus rather than this one.

## Reproducing

```bash
cd services/eval
DATABASE_URL=postgres://localhost:5432/loupe_dev \
AI_URL=http://localhost:8031 \
uv run python -m app.run goldens/fixture-v1.json
```

The run refuses with exit code 2 if the loaded corpus does not match the set.
