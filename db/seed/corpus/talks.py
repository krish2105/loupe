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

    # ------------------------------------------------------------------ long
    # The six above are 210 to 230 words each, which is shorter than the
    # chunker's 300-token minimum — so each became a single chunk, every
    # citation pointed at t=0, and citation timestamp accuracy measured corpus
    # length rather than citation logic. These two are long enough to chunk
    # several times, which is what makes that metric mean anything.
    Talk(
        slug="serving-architecture",
        title="Serving a language model, end to end",
        description="Everything between an HTTP request and a token coming back.",
        script="""
        Let us walk through what happens between a request arriving and a token
        coming back, because most of the interesting engineering lives in
        places people do not look. The request arrives at a load balancer and
        is routed to a replica. Already there is a decision here that people
        get wrong. Routing purely by least connections is bad for language
        model serving, because a replica holding twenty short requests is far
        less loaded than one holding two very long ones, and connection counts
        cannot see that. Routing on estimated remaining tokens works much
        better, and estimating that is itself a small prediction problem.
        Once the request reaches a replica it enters the scheduler queue. The
        scheduler decides admission, and the binding constraint is almost never
        the model weights. It is the key value cache. Weights are a fixed cost
        paid once at startup; the cache grows with every concurrent sequence
        and with the length of each one. A scheduler that admits requests
        without modelling cache growth will accept work it cannot finish and
        then have to evict something, which wastes everything computed so far.
        Prefill comes next. The entire prompt is processed in one forward pass,
        and unlike generation this step is compute bound rather than memory
        bound, because every token in the prompt is processed in parallel. A
        long prompt therefore occupies the device for a meaningful block of
        time, and if you are not careful it stalls every other request that
        wanted to generate a token during that window. This is why chunked
        prefill exists. You break a long prompt into pieces and interleave
        them with decoding steps from other sequences, which costs a little
        total throughput and dramatically improves latency for everyone else.
        Then generation begins, one token at a time, each requiring a full pass
        over the weights. This is where the memory bandwidth wall dominates.
        The arithmetic per token is trivial and the data movement is enormous,
        which is why batching helps so much: a batch of sixty four sequences
        reads the weights once and serves sixty four tokens, so the cost per
        token falls by nearly that factor until you run out of cache.
        Sampling happens on every step and is easy to get wrong. Temperature,
        top k, and nucleus sampling are usually applied on the device, but a
        naive implementation synchronises with the host on every token to check
        stopping conditions, and that synchronisation can cost more than the
        sampling itself. Keeping stop detection on the device matters more than
        people expect. Finally the token is streamed back. Server sent events
        are the usual transport, and the subtlety is that a token is not
        necessarily a character boundary. Emitting raw token text can split a
        multi byte character in half and produce a replacement glyph in
        somebody's browser, so you buffer until the bytes are valid.
        The lesson across all of this is that throughput and latency are
        different objectives and improving one commonly harms the other.
        Larger batches raise throughput and raise time to first token. Chunked
        prefill lowers tail latency and lowers total throughput slightly. There
        is no configuration that is best at everything, only one that is best
        for the traffic you actually have, which is why measuring your own
        traffic beats copying somebody else's configuration.

        Let us talk about what to measure, because the wrong dashboard hides
        every problem worth finding. Average latency is nearly useless here.
        The distribution is heavily skewed, so a mean sits comfortably while a
        meaningful fraction of users wait several times longer. Report the
        ninety fifth and ninety ninth percentiles, and report time to first
        token separately from time between tokens, because they have different
        causes and different fixes. Time to first token is dominated by queue
        wait and prefill. Time between tokens is dominated by batch size and
        memory bandwidth. Averaging them into one number guarantees you cannot
        tell which one broke.
        Queue depth deserves a dashboard of its own. If it is consistently
        near zero you are over provisioned and paying for hardware that idles.
        If it grows without bound you are under provisioned and every latency
        number you report is about to get worse in a way that looks sudden but
        was entirely predictable. The useful signal is not the depth itself but
        whether it is trending, and over what window.
        Cache utilisation is the third thing to watch, and the one most often
        missing. A replica at ninety five percent cache occupancy is one long
        request away from evicting somebody, and evictions are invisible in
        throughput while being extremely visible to whoever got evicted. Track
        occupancy, track eviction count, and alert on the second one long
        before it becomes common.
        Now failure modes, which is where production differs from a benchmark.
        The first is the slow client. A client that reads the stream slowly
        applies back pressure all the way to the scheduler, and if the
        implementation blocks on writing to the socket, one slow reader can
        stall a batch that has nothing else to do with its time. The fix is to
        buffer per connection and drop clients that fall too far behind, which
        feels rude and is correct.
        The second is the request that never ends. Models occasionally fall
        into repetition loops and will happily generate until they hit a limit
        you had better have set. A maximum token count per request is not
        optional, and neither is a wall clock timeout, because a token limit
        alone does not bound the time when the server is heavily loaded.
        The third is the thundering herd after a restart. When a replica comes
        back, load balancers route to it eagerly because it looks unloaded, and
        it receives a burst that fills its cache before it has warmed anything.
        A short ramp on new replicas costs almost nothing and prevents a
        restart from causing a second outage.
        The fourth is silent degradation, which is the worst of them, because
        nothing alerts. A model loaded with a slightly wrong configuration, or
        a quantised variant swapped in during a deploy, will serve every
        request successfully and produce measurably worse answers. Latency is
        fine, error rate is zero, and quality has fallen off a cliff. The only
        defence is a small continuous evaluation running against production,
        which almost nobody builds until the first time this happens to them.
        """,
    ),
    Talk(
        slug="attention-variants",
        title="Attention variants, and which ones survived",
        description="Multi-query, grouped-query, sliding window, and what each one costs.",
        script="""
        Standard multi head attention gives every head its own set of queries,
        keys, and values. That is what the original transformer described and
        it works, but at inference time it has an expensive property: the key
        value cache scales with the number of heads. With thirty two heads you
        store thirty two sets of keys and values for every position, and as we
        have discussed, that cache is usually what limits concurrency.
        Multi query attention was the first serious response. Keep separate
        query projections for every head, but share a single key and value
        projection across all of them. The cache shrinks by a factor equal to
        the head count, which is enormous. The cost is quality: sharing keys
        and values across every head removes representational capacity, and
        models trained this way are measurably worse on tasks requiring precise
        retrieval from the context.
        Grouped query attention is the compromise that actually won. Instead of
        one shared key value pair or one per head, you use a small number of
        groups, typically eight. Heads within a group share keys and values.
        The cache shrinks by four times or more while quality stays within
        noise of full multi head attention. Almost every widely deployed open
        model now uses this, which is a reasonable definition of having won.
        Sliding window attention attacks a different axis. Rather than reducing
        the cache per position, it reduces the number of positions attended to,
        by restricting each token to a fixed window of recent context. Memory
        then grows with the window rather than with the sequence, so very long
        contexts become affordable. The obvious objection is that information
        outside the window is lost, and the answer is that stacked layers give
        an effective receptive field much larger than the window itself,
        because each layer can move information one window further along. In
        practice models interleave sliding window layers with a few full
        attention layers, which keeps long range dependencies available where
        they matter.
        There is a fourth idea worth knowing, which is compressing the cache
        into a lower dimensional latent representation and reconstructing keys
        and values on the fly. This trades a little arithmetic for a large
        memory saving, and because inference is memory bound that trade is
        usually favourable. It is newer and less universally adopted, but the
        direction is clearly right.
        The pattern across all four is the same. Every one of them spends
        quality, arithmetic, or context reach in order to buy memory, because
        memory is the constraint that binds. If you remember only one thing
        from this section, make it that: at inference time you are almost never
        short of compute, and the architecture choices that matter are the ones
        that shrink what you have to store.

        It is worth being concrete about the memory arithmetic, because the
        numbers are what make the design choices obvious. Consider a model with
        thirty two layers, thirty two attention heads, and a head dimension of
        one hundred and twenty eight. With full multi head attention, each
        position stores two tensors, keys and values, of size thirty two heads
        times one hundred and twenty eight dimensions, in every one of thirty
        two layers. In half precision that is about half a megabyte per token.
        A context of four thousand tokens therefore costs roughly two
        gigabytes, for a single sequence. Serve thirty concurrent users and the
        cache alone wants sixty gigabytes, which exceeds the memory of most
        single accelerators before the weights are counted at all.
        Now apply grouped query attention with eight groups instead of thirty
        two heads. The key and value tensors shrink by a factor of four, so the
        same four thousand token context costs half a gigabyte rather than two,
        and thirty concurrent users need fifteen gigabytes rather than sixty.
        That is the difference between one accelerator and four, and it is why
        this particular architectural choice spread so quickly through models
        that were otherwise quite different from one another.
        The quality question is what took longer to settle. Early results
        suggested multi query attention cost around one percent on standard
        benchmarks, which sounds tolerable until you notice the losses
        concentrate in exactly the tasks people care about, namely retrieving
        specific facts from long contexts. Grouped query attention with eight
        groups sits within measurement noise of full attention on the same
        tasks, which is the whole reason it became the default rather than the
        more aggressive option.
        There is a practical detail that catches people converting models. The
        number of groups must divide the number of heads, and the conversion
        from a full attention checkpoint is not simply dropping heads. Mean
        pooling the key and value projections within each group, then briefly
        fine tuning, recovers most of the quality. Naive truncation does not,
        and produces a model that appears to load correctly and generates
        fluent nonsense on anything requiring precision.
        Finally, a word about what none of these variants fix. Every one of
        them reduces the cost of attending to context. None of them reduces the
        cost of the feed forward layers, which are typically two thirds of the
        parameters and therefore two thirds of the bandwidth per token. If your
        workload is short prompts and long generations, attention is not your
        problem and optimising it will disappoint you. Measure where the time
        actually goes before choosing which of these to adopt, because the
        right answer depends on a shape of traffic that varies enormously
        between applications.
        """,
    ),

    # ------------------------------------------------------------------ long
    # The six above are 210 to 230 words each, which is shorter than the
    # chunker's 300-token minimum — so each became a single chunk, every
    # citation pointed at t=0, and citation timestamp accuracy measured corpus
    # length rather than citation logic. These two are long enough to chunk
    # several times, which is what makes that metric mean anything.,
]
