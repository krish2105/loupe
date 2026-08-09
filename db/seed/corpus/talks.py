"""
Six talks with real speech in them.

The evaluation has never had a corpus. `docs/evaluation.md` says so in its first
line — the owned catalogue pointed at a test stream with no audio, so every
transcript was fixture output and every transcript was identical, which made
cross-video comparison not merely bad but undefined.

These are synthesised with macOS `say` from written scripts. That is a real
step and a limited one, and both halves matter:

  Real     — actual audio, actual speech recognition, actual word timings,
             six genuinely different topics with different vocabulary. The
             pipeline runs end to end on it and the numbers describe something.

  Limited  — synthesised speech is clean. No accents, no crosstalk, no room,
             no disfluencies, no speaker changes, no microphone six feet away.
             A conference recording has all of those and every one of them
             hurts. Results here are an upper bound, not an estimate.

The scripts are written to be retrievable rather than merely plausible: each
covers a distinct topic with its own vocabulary, and several deliberately
mention neighbouring ideas in passing, so that retrieval has to distinguish
"the talk about X" from "the talk that mentions X once".

Ground truth is the script itself, which is what makes word error rate
measurable here and nowhere else in this repository.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Talk:
    slug: str
    title: str
    description: str
    #: Spoken verbatim. Also the ground truth for word error rate.
    script: str


TALKS: list[Talk] = [
    Talk(
        slug="kv-cache",
        title="What the KV cache actually stores",
        description="Why generation gets cheaper after the first token, and what it costs in memory.",
        script="""
        Every time a transformer generates a token, it attends over everything
        that came before. Done naively, that means recomputing the keys and
        values for the entire prompt at every single step, which is enormously
        wasteful because those keys and values do not change. The key value
        cache stores them. After the first forward pass you keep the keys and
        values for every position, and each new token only has to compute its
        own. That turns a quadratic amount of recomputation into a linear
        amount of memory reads. The cost is memory. For a model with thirty two
        layers and a hidden size of four thousand ninety six, holding a cache
        for one sequence of two thousand tokens takes well over a gigabyte in
        half precision. Multiply that by the number of concurrent requests and
        the cache, not the weights, becomes the thing that limits how many
        users you can serve. This is why paged attention matters. Instead of
        allocating one contiguous block per sequence, you allocate fixed size
        pages and let sequences share them, exactly like virtual memory in an
        operating system. Fragmentation drops, utilisation rises, and you fit
        more concurrent sequences on the same card. People often ask whether
        quantising the cache helps. It does, and eight bit caches are common
        now, but the quality loss shows up first in long contexts where small
        errors accumulate across many attention steps.
        """,
    ),
    Talk(
        slug="quantisation",
        title="Quantisation without the cliff",
        description="Where precision can be dropped safely, and where the model falls off a cliff.",
        script="""
        Quantisation means storing weights in fewer bits than they were trained
        in. A model trained in sixteen bit floating point can often run in eight
        bit integers with no measurable loss, and that halves both the memory
        footprint and the bandwidth needed to read the weights. Since inference
        for a single sequence is almost entirely bandwidth bound, halving the
        bytes read roughly halves the time per token. Four bits is where it
        becomes interesting. Naive rounding to four bits destroys the model.
        The reason is outliers. A small number of channels carry activations
        with magnitudes orders of magnitude larger than the rest, and a uniform
        quantisation grid stretched to cover them leaves almost no resolution
        for everything else. The techniques that work all handle outliers
        specially. Group wise scaling gives each block of weights its own
        scale factor. Mixed precision keeps the outlier channels in higher
        precision and quantises the rest. Rotation based methods apply an
        orthogonal transform first, which spreads the outliers across channels
        so that no single one dominates. The evaluation trap here is
        perplexity. A four bit model can show almost identical perplexity to
        its sixteen bit original and still fail badly on tasks requiring
        multi step reasoning, because perplexity averages over every token and
        the failures concentrate in the few tokens that carry the reasoning.
        Measure on the task you care about.
        """,
    ),
    Talk(
        slug="speculative-decoding",
        title="Speculative decoding in production",
        description="Draft models, acceptance rates, and when speculation costs more than it saves.",
        script="""
        Generation is sequential and each token needs a full forward pass, so
        the large model spends most of its time waiting on memory rather than
        computing. Speculative decoding exploits that idle arithmetic. A small
        draft model proposes several tokens ahead. The large model then
        verifies all of them in a single forward pass, because verifying a
        sequence in parallel costs almost the same as generating one token.
        Every proposed token the large model agrees with is free. The number
        that decides whether this helps is the acceptance rate. If the draft
        model proposes four tokens and three are accepted on average, you get
        roughly three tokens for the price of one, minus the cost of running
        the draft. If acceptance falls below about forty percent, the draft
        model's own cost exceeds what it saves and you are better off without
        it. Acceptance depends on how well the draft model matches the target
        distribution, which is why drafts distilled from the target work far
        better than a small model trained independently. There is a subtlety
        people miss. Speculation helps latency for a single stream and helps
        far less under heavy batching, because a busy server is already compute
        bound and there is no idle arithmetic left to exploit. Measure it at
        the batch size you actually serve, not at batch size one.
        """,
    ),
    Talk(
        slug="continuous-batching",
        title="Continuous batching and why static batching wastes a GPU",
        description="Scheduling requests that finish at different times.",
        script="""
        The obvious way to batch inference requests is to collect a fixed
        number, run them together, and return the results. This is called
        static batching and it wastes an enormous amount of a graphics
        processor. The reason is that generation lengths vary wildly. If one
        request in a batch of thirty two produces a thousand tokens and the
        rest produce fifty, the whole batch occupies the device until the
        longest one finishes, and thirty one slots sit idle doing nothing.
        Continuous batching fixes this by working at the level of individual
        decoding steps rather than whole requests. After every step, finished
        sequences leave the batch and waiting requests join it immediately.
        The batch composition changes constantly and the device stays full.
        Reported throughput improvements are typically between two and four
        times on realistic traffic, and the gain is larger the more variable
        the output lengths are. The complexity moves into the scheduler.
        It has to decide admission when memory is scarce, and the constraint
        is almost always the key value cache rather than the weights. It also
        has to handle preemption, because a sequence that grows longer than
        predicted may need to be evicted and recomputed later. Getting that
        wrong produces latency spikes that are invisible in average throughput
        and extremely visible to whoever is waiting.
        """,
    ),
    Talk(
        slug="roofline",
        title="The roofline model, applied to inference",
        description="Arithmetic intensity, and why a faster card sometimes changes nothing.",
        script="""
        The roofline model asks one question about a computation. Is it limited
        by how fast the hardware can do arithmetic, or by how fast it can move
        data. You compute arithmetic intensity, which is the number of
        floating point operations performed per byte read from memory, and
        compare it against the ratio of the machine's peak compute to its
        memory bandwidth. Below that ratio you are memory bound and adding
        compute changes nothing. Above it you are compute bound and adding
        bandwidth changes nothing. Transformer inference at batch size one is
        firmly memory bound. Generating a single token reads every weight in
        the model exactly once and performs about two floating point operations
        per weight, giving an arithmetic intensity of roughly two. Modern
        accelerators need intensities in the hundreds before compute becomes
        the limit. This explains an experiment that surprises people. Moving a
        single stream workload to a card with three times the arithmetic
        throughput but only slightly more bandwidth produces almost no
        improvement, because the arithmetic was never the constraint. Batching
        is what changes the regime. With a batch of sixty four, each weight
        read serves sixty four sequences, intensity rises by that factor, and
        the workload crosses into compute bound territory where the faster card
        finally earns its price.
        """,
    ),
    Talk(
        slug="retrieval-eval",
        title="Retrieval evaluation, and how to fool yourself",
        description="Why offline retrieval numbers are usually better than they deserve to be.",
        script="""
        Retrieval systems are unusually easy to evaluate badly. The most common
        mistake is writing the evaluation questions after reading the documents.
        If you look at a passage and then write a question about it, you will
        reuse its vocabulary without noticing, and you end up measuring lexical
        overlap while believing you are measuring semantic retrieval. The fix
        is to write questions from the topic rather than the text, ideally by
        someone who has not read the passages. The second mistake is a corpus
        that is too small or too uniform. If every document discusses the same
        subject in the same words, retrieval looks excellent because there is
        nothing to confuse it with, and the number collapses the moment real
        variety arrives. A useful corpus contains near misses, documents that
        mention the target topic without being about it. The third mistake is
        reporting precision at five on a corpus of six documents, where a
        random ranking scores well. The metric that survives all three is a
        held out set with negatives that were chosen adversarially, scored by
        someone who did not build the index. Report the number of queries as
        well as the score, because a precision computed over twelve questions
        carries an error bar wide enough to hide almost any regression.
        """,
    ),
]
