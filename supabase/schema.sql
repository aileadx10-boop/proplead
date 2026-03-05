-- ============================================================
-- PropLeads Pro — Supabase Schema
-- Paste this entire file into: Supabase → SQL Editor → Run
-- ============================================================

-- SUBSCRIBERS (one row per paying customer)
CREATE TABLE subscribers (
  id                       UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  email                    TEXT UNIQUE NOT NULL,
  name                     TEXT,
  state                    TEXT NOT NULL,
  zip                      TEXT NOT NULL,
  deal_target              TEXT,
  paddle_subscription_id   TEXT UNIQUE,
  active                   BOOLEAN DEFAULT false,
  created_at               TIMESTAMPTZ DEFAULT NOW(),
  cancelled_at             TIMESTAMPTZ
);
CREATE INDEX idx_subscribers_zip_active ON subscribers(zip, active);

-- LEADS (one row per property, deduped by address)
CREATE TABLE leads (
  id                   UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  address              TEXT UNIQUE NOT NULL,
  city                 TEXT,
  state                TEXT,
  zip                  TEXT,
  list_price           INTEGER,
  original_price       INTEGER,
  days_on_market       INTEGER,
  price_reduction_pct  FLOAT,
  motivation_score     FLOAT,
  score_breakdown      JSONB,
  score_reasoning      TEXT,
  is_fsbo              BOOLEAN DEFAULT false,
  pre_foreclosure      BOOLEAN DEFAULT false,
  estimated_equity_usd INTEGER,
  equity_pct           FLOAT,
  seller_email         TEXT,
  seller_phone         TEXT,
  listing_url          TEXT,
  email_1              JSONB,
  email_2              JSONB,
  email_3              JSONB,
  sent_date            DATE,
  sent_to              TEXT[] DEFAULT ARRAY[]::TEXT[],
  created_at           TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_leads_zip       ON leads(zip);
CREATE INDEX idx_leads_sent_date ON leads(sent_date);
CREATE INDEX idx_leads_score     ON leads(motivation_score DESC);

-- ZIP SLOTS (tracks how many subscribers per ZIP, max 5)
CREATE TABLE zip_slots (
  zip  TEXT PRIMARY KEY,
  used INTEGER DEFAULT 0,
  max  INTEGER DEFAULT 5
);

-- WAITLIST (people waiting for a full ZIP to open up)
CREATE TABLE waitlist (
  id                     UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  email                  TEXT NOT NULL,
  name                   TEXT,
  state                  TEXT,
  zip                    TEXT,
  paddle_subscription_id TEXT,
  notified               BOOLEAN DEFAULT false,
  created_at             TIMESTAMPTZ DEFAULT NOW()
);

-- RUN LOG (records every time the crew runs)
CREATE TABLE run_log (
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  triggered_at TIMESTAMPTZ DEFAULT NOW(),
  status       TEXT,
  source       TEXT,
  leads_found  INTEGER,
  emails_sent  INTEGER,
  error_msg    TEXT
);

-- ── STORED PROCEDURES ─────────────────────────────────────

-- Append subscriber email to a lead's sent_to array (dedup)
CREATE OR REPLACE FUNCTION append_sent_to(p_address TEXT, p_email TEXT)
RETURNS void AS $$
  UPDATE leads
  SET sent_to = array_append(sent_to, p_email)
  WHERE address = p_address
    AND NOT (p_email = ANY(sent_to));
$$ LANGUAGE sql;

-- Increment ZIP slot counter when someone subscribes
CREATE OR REPLACE FUNCTION increment_zip_used(p_zip TEXT)
RETURNS void AS $$
  INSERT INTO zip_slots(zip, used)
  VALUES (p_zip, 1)
  ON CONFLICT(zip)
  DO UPDATE SET used = zip_slots.used + 1;
$$ LANGUAGE sql;

-- Decrement ZIP slot counter when someone cancels
CREATE OR REPLACE FUNCTION decrement_zip_used(p_zip TEXT)
RETURNS void AS $$
  UPDATE zip_slots
  SET used = GREATEST(0, used - 1)
  WHERE zip = p_zip;
$$ LANGUAGE sql;

-- ── ROW LEVEL SECURITY ─────────────────────────────────────
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads       ENABLE ROW LEVEL SECURITY;
-- Note: the service_role key bypasses RLS — always use that on the server
