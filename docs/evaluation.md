# Evaluation

Plan ref: §11.2. §15.1 says never cut this phase; §2 calls the published
benchmark the proof of the intelligence layer.

---

## The honest headline

**Loupe still does not have a benchmark. It now has real transcripts, and they
found a real defect.**

The corpus used to be a test stream with no speech in it, so every transcript
was fixture output and every transcript was identical. That is fixed: six talks
are spoken aloud, transcribed by whisper-large-v3-turbo, chunked and embedded
like anything else. The pipeline runs end to end on audio, and the numbers
below describe something that happened.

What they still are not is a benchmark, for two reasons that have not moved.
The speech is synthesised, so it is far cleaner than any recording of a real
room. And six talks is a small corpus, on which retrieval scores flatter
themselves.

So the numbers are labelled for what they are, and the fixture results are left
below for comparison rather than deleted.

The most useful thing in this document is that citation accuracy went *down*
when the corpus got real — from 0.600 to 0.053 — because the fixture metric had
been confirming a tautology, and the drop exposed a defect in what a citation
actually pointed at. Fixing it took the score to 0.421. An evaluation that only
ever moves upward is not measuring anything.

## What is and is not measurable on the current corpus

| Metric | Status | Why |
|---|---|---|
| Refusal accuracy | **Meaningful** | An out-of-scope question is out of scope whatever the corpus. The refuse/answer decision is genuinely under test. |
| Word error rate | **Meaningful, and newly possible** | The talks are spoken from written scripts, so the ground truth is exact. This is the only place in the repository where recognition quality is measured rather than assumed. Optimistic: the speech is synthesised. |
| Cross-video comparison | **Meaningful, and newly possible** | Six distinct topics, several deliberately mentioning each other in passing. Four cases is too few to conclude from, but the category is no longer empty by construction. |
| Faithfulness | **Meaningful but uninformative** | Extractive answering quotes its sources, so this is ~1.0 by construction. It is a regression guard, not a quality measure. |
| Retrieval precision@5 | **Partially meaningful** | Questions are written from the topics rather than from the text, so retrieval does semantic work. But six documents is a small field to be precise within. |
| Citation timestamp accuracy | **Meaningful, and it found a defect** | Expected timestamps are anchored on the sentence that answers the question, not on chunk boundaries as the fixture set used. That change took the score from 0.600 to 0.053 and exposed citations pointing at the top of a three-minute passage. Now 0.421 after the fix. |
| Non-English | **Out of scope** | §17 decision 3 chose English only. |

## Results — real speech, 29 cases

Golden set `corpus-v1`, corpus `groq-whisper`, answerer `extractive-v1`,
embeddings `bge-m3`, timestamp tolerance ±5s. Six talks, 1,316 words of script,
transcribed by whisper-large-v3-turbo.

Eight talks — six short, two long enough to chunk more than once — 3,273 words
of script, 36 cases.

```
refusal accuracy              0.889    was 0.792 on fixtures
refusal rate                  0.472
false answer rate             0.000    was 0.357   ← the one that mattered
citation timestamp accuracy   0.421    was 0.600 on fixtures, which was a tautology
faithfulness (lexical)        0.988
word error rate               0.048    not previously measurable
```

By category:

```
factual         15/19 decided correctly
out_of_scope     5/5
adversarial      8/8    was 4/8
cross_video      4/4    was undefined
```

### The false answer rate went to zero, and the corpus is why

The fixture run answered five of fourteen questions it should have refused. The
same threshold, unchanged, now refuses all thirteen.

That is not a fix. Nothing about the refusal logic changed. It is what happens
when a corpus stops being one document repeated: fixture transcripts were
near-identical, so every question retrieved something scoring highly and the
threshold had no distance to work with. Six genuinely different talks give it
some.

Worth stating plainly, because the entire improvement is attributable to data —
and the same threshold over two thousand talks may be wrong again, in the other
direction.

### Cross-video comparison exists now

The fixture set defined this category as empty, because every transcript was the
same text. Four cases, all correct. Each asks which talk is *about* a topic that
another talk mentions in passing: `roofline` and `kv-cache` both discuss memory,
`continuous-batching` and `speculative-decoding` both discuss batching. So
retrieval has to separate subject from mention.

Four cases is far too few to conclude anything. It is reported because the
category went from impossible to possible, not because 4/4 means much.

### The citation metric found a real defect, and it has been fixed

This is what the whole document exists for, so it is worth the space.

The fixture set scored 0.600 and, in its own words, read its expected
timestamps "from real chunk boundaries". A citation returned the chunk's start
time. So the metric was checking that a citation equals the chunk start, which
is true by construction — it confirmed a tautology and reported it as 0.600.

`corpus-v1` anchors expected timestamps on the sentence that actually answers
the question, resolved against real word timings. Under that, citation accuracy
was **0.053**. Chasing it found the defect: §11.1 promises a citation lets you
jump to *the moment*, and what the system returned was the top of a
three-minute passage. The word-level timestamps needed to do better had been a
hard requirement since §10.2 and were never read.

Fixed in three steps, each measured:

```
citing the chunk start                     0.053
+ picking the sentence by word overlap     0.263
+ picking the sentence by embedding        0.421
```

The middle step was not enough on its own, and the reason is worth recording:
nine of nineteen citations landed six to fourteen seconds out, which is one or
two sentences. Sentences inside one passage are all about the same subject and
differ by shades that shared vocabulary does not capture. Embedding them
against the question — one extra call, on vectors already being computed —
nearly doubled the score.

**0.421 is not good, and it is honest.** A ±5s tolerance is roughly one
sentence of speech, so a citation that picks the sentence *before* the right
one already fails. The remaining errors are five cases more than thirty
seconds out, where the wrong passage was cited rather than the wrong sentence
within it, and four questions refused outright.

### Four answerable questions were refused, and the threshold is now too strict

The fixture run concluded the threshold was too permissive. On real speech the
opposite is true. The sweep:

```
threshold   accuracy   false answers   false refusals
0.34         0.806          7               0
0.38         0.944          2               0
0.42         0.889          0               4     ← current
0.50         0.806          0               7
```

0.38 maximises accuracy. 0.42 is kept anyway, because §11.1 is explicit that a
confident wrong answer is the failure that matters, and 0.42 is the lowest
threshold with none of them. That is a product decision, not a metric to
maximise, and it costs four refusals of questions the corpus does answer.

The cause is the discipline the corpus itself recommends: questions written
from the topic rather than from the transcript share less vocabulary with it,
so similarity is lower. Writing questions honestly makes retrieval look worse,
which is the point of writing them honestly.

### What is still not measured

The audio is synthesised with macOS `say`. It is clean: no accents, no
crosstalk, no room, no disfluencies, no speaker changes, no microphone at the
back of a lecture theatre. Every one of those hurts recognition and retrieval,
and none is present. A 4.8% word error rate on clean synthesised speech says
little about the same pipeline on a real recording.

Some of that 4.8% is not error at all — the scripts spell numbers out and the
transcriber writes digits, so "four thousand ninety six" against "4096" counts
as four substitutions. The true recognition error is lower than the figure, and
the figure is still an upper bound on real audio. Both things are true.

Six talks is also a small corpus, and precision over six documents is generous
by construction — as the talk about fooling yourself when evaluating retrieval,
which is in the corpus, says.

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

Real corpus, from nothing:

```bash
# 1. six talks, spoken aloud and uploaded  (needs `say`, ffmpeg, the media service)
DATABASE_URL=... MEDIA_SERVICE_URL=... INTERNAL_TOKEN=... \
  uv run python db/seed/corpus/build.py

# 2. transcode, transcribe, chunk, embed  (needs GROQ_API_KEY for real ASR)
cd services/pipeline && DATABASE_URL=... GROQ_API_KEY=... USE_REAL_MODELS=true \
  uv run python -m app.run

# 3. re-derive the golden set's timestamps from the transcripts that resulted
cd services/eval && DATABASE_URL=... uv run python goldens/build_corpus_v1.py

# 4. score
DATABASE_URL=... AI_URL=http://localhost:8031 \
  uv run python -m app.run goldens/corpus-v1.json
```

Step 3 matters: the golden set's expected timestamps are resolved against the
actual word timings, so a re-transcription with a different model re-anchors
the set rather than scoring against stale positions.

`USE_REAL_MODELS=true` needs the `embeddings` extra. Without it the pipeline
embeds with a hashing fallback while the AI service queries with bge-m3, and
the ask endpoint refuses to compare them — correctly, since the similarity
would be meaningless. That refusal is what caught it here.

The fixture set, for comparison:

```bash
cd services/eval
DATABASE_URL=postgres://localhost:5432/loupe_dev \
AI_URL=http://localhost:8031 \
uv run python -m app.run goldens/fixture-v1.json
```

The run refuses with exit code 2 if the loaded corpus does not match the set.
