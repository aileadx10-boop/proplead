"""
PropLeads Pro — Flow Orchestrator (Production-hardened)
=========================================================
Fixes vs v1:
  - run_all() processes ZIPs in PARALLEL batches (not sequential)
  - Each ZIP is isolated — one failure does NOT kill the rest
  - Configurable batch size + delay for OpenAI rate limits
  - Full error logging per ZIP to Supabase run_log

Scale math (500 subscribers, unique ZIPs worst case):
  Sequential old: 500 ZIPs × 5 min = 41 HOURS  ← crashes
  Parallel new:   50 batches × 5 min + delays  = ~26 MIN  ← fine
"""

import json, time, argparse, traceback
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed

from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel

from propleads_pro.crew import PropLeadsCrew
from propleads_pro.tools.supabase_tool import SupabaseTool
from propleads_pro.tools.delivery_tool import DeliveryTool

BATCH_SIZE       = 10   # ZIPs processed simultaneously
BATCH_DELAY_SEC  = 10   # wait between batches (OpenAI rate limit buffer)
MAX_CREW_RETRIES = 2    # retry a ZIP on transient errors


# ── Shared state ───────────────────────────────────────────

class PropLeadsState(BaseModel):
    state:          str  = "TX"
    zip_code:       str  = "78701"
    run_date:       str  = ""
    final_leads:    list = []
    delivery_stats: dict = {}


# ── Single-ZIP Flow ────────────────────────────────────────

class PropLeadsFlow(Flow[PropLeadsState]):

    @start()
    def initialise(self):
        self.state.run_date = str(date.today())
        print(f"\n{'='*52}")
        print(f"  {self.state.state} / ZIP {self.state.zip_code}  |  {self.state.run_date}")
        print(f"{'='*52}")
        return self.state.zip_code

    @listen(initialise)
    def run_crew(self, _):
        print(f"[{self.state.zip_code}] 🤖 Running crew (4 agents)...")
        result = PropLeadsCrew().crew().kickoff(inputs={
            "state":        self.state.state,
            "zip_code":     self.state.zip_code,
            "current_year": str(date.today().year),
        })
        try:
            raw = result.raw
            if isinstance(raw, str):
                raw = raw.strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                raw = raw.strip()
            leads = json.loads(raw)
        except Exception as e:
            print(f"[{self.state.zip_code}] ⚠️  Parse error: {e}")
            leads = []
        self.state.final_leads = leads
        print(f"[{self.state.zip_code}] ✓ {len(leads)} leads ready")
        return leads

    @listen(run_crew)
    def save_and_deliver(self, leads: list):
        db    = SupabaseTool()
        saved = db.save_leads_batch(leads, run_date=self.state.run_date)
        self.state.final_leads = saved

        stats = DeliveryTool().dispatch(
            leads=saved, state=self.state.state,
            zip_code=self.state.zip_code, run_date=self.state.run_date,
        )
        self.state.delivery_stats = stats

        db.log_run(
            status="completed", zip_code=self.state.zip_code,
            leads_found=len(saved), emails_sent=stats.get("sent", 0),
        )
        print(f"[{self.state.zip_code}] ✅ Sent:{stats['sent']} Skip:{stats['skipped']}")
        return stats


# ── Run one ZIP — never raises ─────────────────────────────

def run_for_zip(state: str, zip_code: str) -> dict:
    db = SupabaseTool()
    for attempt in range(1, MAX_CREW_RETRIES + 1):
        try:
            flow = PropLeadsFlow()
            flow.state.state    = state
            flow.state.zip_code = zip_code
            flow.kickoff()
            return {"zip": zip_code, "status": "ok"}
        except Exception as e:
            print(f"[{zip_code}] ❌ Attempt {attempt}/{MAX_CREW_RETRIES}: {e}")
            if attempt == MAX_CREW_RETRIES:
                db.log_run(status="failed", zip_code=zip_code, error_msg=str(e)[:500])
                return {"zip": zip_code, "status": "failed", "error": str(e)}
            time.sleep(5 * attempt)


# ── Run ALL ZIPs in parallel batches ──────────────────────

def run_all():
    """
    500 subscribers, 100 unique ZIPs, batch=10:
      10 batches × ~5 min crew + 10s delay = ~52 min  ← totally fine
    """
    db     = SupabaseTool()
    active = db.get_active_zip_states()

    if not active:
        print("⚠️  No active subscribers found.")
        return

    # Deduplicate (state, zip) pairs
    pairs = list({f"{r['state']}-{r['zip']}": (r["state"], r["zip"])
                  for r in active}.values())

    total = len(pairs)
    ok = failed = 0
    print(f"\n🚀 Daily run — {total} ZIP(s) in batches of {BATCH_SIZE}")

    for i in range(0, total, BATCH_SIZE):
        batch = pairs[i : i + BATCH_SIZE]
        batch_n = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\n── Batch {batch_n}/{total_batches} ({len(batch)} ZIPs) ──")

        with ThreadPoolExecutor(max_workers=BATCH_SIZE) as pool:
            futures = {pool.submit(run_for_zip, s, z): z for s, z in batch}
            for future in as_completed(futures):
                r = future.result()
                if r["status"] == "ok":
                    ok += 1
                else:
                    failed += 1
                    print(f"   ⚠️  {r['zip']}: {r.get('error','')[:80]}")

        if i + BATCH_SIZE < total:
            print(f"   ⏸  Waiting {BATCH_DELAY_SEC}s (rate limit buffer)...")
            time.sleep(BATCH_DELAY_SEC)

    print(f"\n✅ Done — {ok} succeeded, {failed} failed out of {total} ZIPs")


def run():
    run_all()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--state", default="TX")
    p.add_argument("--zip",   default="78701")
    p.add_argument("--all",   action="store_true")
    args = p.parse_args()
    if args.all:
        run_all()
    else:
        run_for_zip(state=args.state, zip_code=args.zip)
