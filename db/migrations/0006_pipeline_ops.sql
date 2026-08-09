-- 0006 — pipeline and ingest operations
-- Plan refs: §5.1 (idempotency everywhere), §4.2 (quota ledger), §10.3 (cost ceiling)
--
-- These tables are not in §6, but §5.1 and §4.2 require them to exist from week 1.
-- Both are architectural principles the plan says to lock in early rather than
-- retrofit, so they ship with the Phase 0 schema.

-- §5.1: every pipeline job keyed on (video_id, stage, version). The pipeline will
-- be re-run many times during development; the unique key is what makes that free.
CREATE TABLE pipeline_jobs (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id     uuid NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  stage        processing_status NOT NULL,
  version      integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  attempts     integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  started_at   timestamptz,
  finished_at  timestamptz,
  error        text,
  created_at   timestamptz NOT NULL DEFAULT now(),

  -- The idempotency key. A re-run with the same triple is a no-op, not a duplicate.
  UNIQUE (video_id, stage, version)
);

CREATE INDEX pipeline_jobs_pending_idx
  ON pipeline_jobs (stage, created_at) WHERE finished_at IS NULL;

-- §4.2 rule 2: maintain an explicit quota ledger. Log consumption per run and fail
-- closed when the budget is exhausted. §15 lists quota exhaustion as a live risk,
-- and the mitigation is this table plus a fail-closed check in the ingest worker.
CREATE TABLE ingest_quota_ledger (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_date      date NOT NULL,
  provider      text NOT NULL,
  operation     text NOT NULL,
  units_spent   integer NOT NULL CHECK (units_spent >= 0),
  items_fetched integer NOT NULL DEFAULT 0 CHECK (items_fetched >= 0),
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ingest_quota_ledger_day_idx ON ingest_quota_ledger (provider, run_date);

-- §10.3 cost ceiling: a hard monthly cap on transcription minutes enforced inside
-- the worker "not by discipline — by code". The worker reads this before it starts
-- a job and refuses when the month's budget is spent.
CREATE TABLE transcription_budget (
  month           date PRIMARY KEY,
  minutes_cap     integer NOT NULL CHECK (minutes_cap >= 0),
  minutes_spent   integer NOT NULL DEFAULT 0 CHECK (minutes_spent >= 0),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT transcription_budget_within_cap CHECK (minutes_spent <= minutes_cap)
);
