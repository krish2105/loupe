# Recommendations — offline evaluation

Plan ref: §12. Gate: *beats the popularity baseline on recall@20 and NDCG@20,
or the failure is analysed.*

**The model loses to the popularity baseline. This is the analysis.**

---

## Result

Five synthetic personas, 3,065-video catalogue, final 20% of each history held
out by time.

| | recall@20 | NDCG@20 |
|---|---|---|
| Two-stage model | **0.000** | **0.000** |
| Model, diversity disabled | 0.000 | 0.000 |
| Popularity baseline | **0.020** | 0.019 |

Diagnostics:

```
candidate recall (stage-one ceiling)      0.182
top-20 drawn from preferred channels      model 0.033  ·  baseline 0.000
training rows                             818
```

## Why it fails

Four causes, in order of how much they matter.

### 1. The task is close to impossible as constructed

3,065 videos, roughly eight held-out items per user, twenty slots. Random
guessing scores about 0.005. The baseline's 0.020 is four times random, and
still nearly zero.

Every number in this table is in the noise. The model losing 0.000 to 0.020 is
one lucky hit for one user out of five, not a meaningful gap — and that cuts
both ways. If the model had scored 0.030 it would have "beaten the baseline"
on the same amount of evidence, and reporting that as a win would have been
wrong.

### 2. The generator is stochastic, so there is a hard ceiling

Personas do not pick a deterministic favourite. They draw from a weighted
distribution over the whole catalogue — affinity, plus popularity bias, plus an
exploration rate.

A *perfect* model of a persona recovers that distribution. It still cannot know
which specific eight items were drawn from it. The achievable recall@20 is
therefore far below 1.0 and nobody computed what it actually is, which is its
own criticism of this evaluation.

### 3. Stage one only reaches 18% of the held-out items

Candidate recall is the ceiling on stage two: anything generation misses,
ranking cannot recover. At 0.182, five sixths of the targets were never
eligible.

The cause is the catalogue's shape. 3,000 of 3,065 videos are fixture-generated
Class B rows whose descriptions are identical by construction, so TF-IDF
content similarity has almost nothing to separate them, and the title-keyword
topics are noisy. Content neighbours — §12.1's first and most important
candidate source — are close to useless on this data.

### 4. 818 training rows from five users

A gradient-boosted model with six features and 818 rows, four fifths of them
sampled negatives, has very little to learn. §12.2's third option — recruiting
15–20 real users — exists precisely because this is not enough, and it was
declined for good reason at the time.

## What was ruled out

**The diversity penalty.** The obvious suspect: 0.18 per channel repeat against
scores in [0, 0.9] would effectively round-robin channels and destroy
personalisation. The ablation says no — with diversity disabled the score is
identical at 0.000. Worth recording, because it was the hypothesis that looked
most likely before it was tested.

## What does work

The model personalises, weakly. 3.3% of its top-20 comes from each persona's
preferred channels against 0.0% for the baseline. That is a small effect on a
weak signal, but it is directionally correct and the baseline has none of it —
so the features carry *some* information and the pipeline is wired correctly
end to end.

The pipeline itself runs: candidate generation returns its 500-item target,
training completes, ranking produces an ordering, and the three §6.4 tables
that had been defined since Phase 0 and never written to are now populated
(200 topic affinities, 30,650 similarity edges, 1,000 feed candidates).

## What this evaluation cannot tell you

This is the part that matters most.

**A win here would not have meant the recommendations are good.** The personas
pick by rules. A model trained on their output learns those rules. Beating a
popularity baseline on synthetic data demonstrates that features, training,
ranking, and evaluation are wired together correctly — a systems check — and
demonstrates nothing whatsoever about whether a person would want the results.

§12.2 says never present synthetic results as real user data. The same logic
applies to a synthetic-data *score*: it is not evidence of quality, and it would
have been just as wrong to claim it if the number had gone the other way.

So the honest summary is not "the model is bad". It is: **this evaluation could
not have told us whether the model is good, and it says so.**

## What would make this meaningful

1. **Real interaction data**, §12.2's third option — 15–20 people over two
   weeks. Nothing else replaces it.
2. **A real corpus.** Content similarity is the strongest candidate source and
   it is crippled by fixture rows with identical descriptions.
3. **A computed ceiling.** Simulate a perfect model of the generator and report
   its recall. Without that number, no score here can be interpreted.
4. **A larger holdout, or a smaller catalogue.** Eight targets in three thousand
   items puts every metric in the noise.

## Not done: tuning until it wins

The threshold sweep in Phase 7 established the principle and it applies here.
Raising the candidate target, dropping the diversity penalty, or shrinking the
evaluation catalogue would all move the number. None would make the
recommendations better, and the resulting figure would describe the tuning
rather than the system.

§12.3 anticipated this outcome: *"If the model does not beat popularity, say so
and analyse why. A documented negative result is a stronger portfolio entry than
an unverified claim."*

## Reproducing

```bash
cd services/recsys
DATABASE_URL=postgres://localhost:5432/loupe_dev uv run python -m app.run
DATABASE_URL=... uv run python -m app.run --write   # also persists §6.4 tables
```

Every generated event is written with `is_synthetic = true`, and the accounts
are handled `synthetic-*`, so synthetic data is identifiable by column and by
name rather than by remembering.
