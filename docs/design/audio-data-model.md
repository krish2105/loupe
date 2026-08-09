# Audio mode: one content model or two?

The decision that is expensive to reverse. Modelled against the real surfaces
before committing, as asked.

**Conclusion: extend `videos` with a `content_kind` enum. Do not build parallel
track/album/artist tables.**

The catalogue choice made this decisive rather than close, and that is the
interesting part.

---

## Why the catalogue choice settled it

Most of the case for a separate music schema is music-specific metadata that
has nowhere sensible to live on a video row:

| Music concept | Needs its own home? |
|---|---|
| Track number, disc number | Yes |
| Album artist vs track artist | Yes |
| Featured artists | Yes, a join table |
| ISRC, BPM, musical key | Yes |
| Compilations, various artists | Yes |

**Spoken audio has none of these.** A podcast has a show, episodes in order,
and a publication date. That is a channel, videos, and `published_at` — which
already exist and already work.

Had the catalogue been CC music, the argument would have been genuinely close.
It is not, so it is not.

## Surface by surface

Each real surface, and what it needs from the model.

| Surface | Under `content_kind` | Verdict |
|---|---|---|
| Now playing | title, channel, artwork, duration, position | All present |
| Queue | ordered list of content ids | `playlist_items.position` already does this |
| Show page | channel + its uploads, newest first | The channel page, unchanged |
| Episode page | the video page with the player swapped | One branch on `content_kind` |
| Library | saved items, playlists, history | The collection abstraction, unchanged |
| Radio from a seed | neighbours of a piece of content | `video_similarity`, already in §6.4 |
| Time-synced transcript | chunks with word timings | `transcript_chunks`, unchanged |
| Search inside | vector search over chunks | Unchanged |
| Downloads | which content is cached | One new small table |

Nine surfaces. Eight need no schema change at all.

## Where it does strain

Two places, both small, both listed rather than glossed:

**Episode numbering.** Podcasts have seasons and episode numbers, and
`published_at` ordering is not always the same thing — a re-released episode
sorts wrongly. One nullable `sequence jsonb` or a pair of nullable integer
columns fixes it.

**Artwork per episode.** Shows have art; episodes sometimes have their own.
`channels.avatar_url` covers the show. Episode-level art would need a column,
and can wait until something actually has one.

Neither justifies a parallel schema. Both are additive migrations.

## What the alternative would cost

Separate `tracks`/`albums`/`artists` tables would duplicate, for a second
content type:

- the §4 capability matrix and every unavailable state built on it
- the §6.2 collection abstraction — four surfaces would become eight
- the pipeline's stage machine, or a second eligibility path through it
- the retrieval layer, or a second `chunks` table
- every API serialiser and every card component

§6.2's instruction — *"build the abstraction once; get four surfaces"* — has
held for the entire project, and the one time a second shape appeared
(playlists listing lists rather than videos), forcing it through the shared
component was correctly rejected. This is the opposite case: the shape is the
same and only the playback surface differs.

## The migration

```sql
CREATE TYPE content_kind AS ENUM ('video', 'audio');

ALTER TABLE videos
  ADD COLUMN content_kind content_kind NOT NULL DEFAULT 'video';

-- Audio has no visual track, so a Class A audio item still needs an asset but
-- never needs a thumbnail sprite. The existing constraint already allows that.
CREATE INDEX videos_audio_feed_idx
  ON videos (content_kind, published_at DESC NULLS LAST)
  WHERE visibility = 'public';
```

Plus one new table for offline state, which is genuinely new behaviour rather
than a reshaping of existing data:

```sql
CREATE TABLE downloads (
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id    uuid NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  requested_at timestamptz NOT NULL DEFAULT now(),
  bytes       bigint,
  PRIMARY KEY (user_id, video_id)
);
```

`content_kind` defaults to `'video'`, so every existing row is correct without
a backfill and every existing query keeps working unchanged.

## What this does not decide

Whether the audio feed is a separate top-level surface or a filter on the
existing one. That is a design question about how people navigate, not a data
question, and it can be answered from a prototype rather than in advance.
