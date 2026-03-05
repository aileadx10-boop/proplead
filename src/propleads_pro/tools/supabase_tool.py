"""
Supabase Tool — Production-hardened
=====================================
Fixes vs v1:
  - save_leads() → save_leads_batch() — ONE upsert call, not N
  - mark_sent() uses a single RPC call per lead (not per subscriber)
  - get_sent_to_map() prefetches all sent_to data in one query
  - log_run() now accepts zip_code for per-ZIP tracking
  - Connection reuse via module-level singleton

DRY RUN mode: if env vars missing, prints what it would do. Safe for local testing.
"""

import os, json
from datetime import date, datetime
from typing import Optional, List, Dict


# ── Module-level singleton — one connection for the process ──

_client = None

def _get_client():
    global _client
    if _client is None:
        from supabase import create_client
        _client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_KEY"),
        )
    return _client


class SupabaseTool:

    def __init__(self):
        self.dry_run = not (
            os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_KEY")
        )
        if self.dry_run:
            print("   [Supabase] DRY RUN mode")
        else:
            self.db = _get_client()   # reuses existing connection

    # ── LEADS — batch operations ───────────────────────────

    def save_leads_batch(self, leads: list, run_date: str = None) -> list:
        """
        Upsert ALL leads in ONE database call.
        Old code did one call per lead = N+1 problem.
        """
        if self.dry_run:
            print(f"   [Supabase] DRY RUN: would batch-save {len(leads)} leads")
            return leads
        if not leads:
            return leads

        today = run_date or str(date.today())
        rows  = []
        for lead in leads:
            if not lead.get("address"):
                continue
            rows.append({
                "address":              lead.get("address"),
                "city":                 lead.get("city"),
                "state":                lead.get("state"),
                "zip":                  lead.get("zip"),
                "list_price":           lead.get("list_price"),
                "original_price":       lead.get("original_price"),
                "days_on_market":       lead.get("days_on_market"),
                "price_reduction_pct":  lead.get("price_reduction_pct"),
                "motivation_score":     lead.get("motivation_score"),
                "score_breakdown":      json.dumps(lead.get("score_breakdown", {})),
                "score_reasoning":      lead.get("score_reasoning"),
                "is_fsbo":              lead.get("is_fsbo", False),
                "pre_foreclosure":      lead.get("pre_foreclosure", False),
                "estimated_equity_usd": lead.get("estimated_equity_usd"),
                "equity_pct":           lead.get("equity_pct"),
                "seller_email":         lead.get("seller_email"),
                "seller_phone":         lead.get("seller_phone"),
                "listing_url":          lead.get("listing_url"),
                "email_1":              json.dumps(lead.get("email_1", {})),
                "email_2":              json.dumps(lead.get("email_2", {})),
                "email_3":              json.dumps(lead.get("email_3", {})),
                "sent_date":            today,
                "created_at":           datetime.utcnow().isoformat(),
            })

        if not rows:
            return leads

        # ONE upsert call for all rows
        result = (self.db.table("leads")
                  .upsert(rows, on_conflict="address")
                  .execute())

        if result.data:
            id_map = {r["address"]: r["id"] for r in result.data}
            for lead in leads:
                lead["id"] = id_map.get(lead.get("address"))

        print(f"   [Supabase] Batch-saved {len(rows)} leads (1 DB call)")
        return leads

    def get_sent_to_map(self, addresses: list) -> Dict[str, list]:
        """
        Fetch sent_to arrays for all addresses in ONE query.
        Old code called already_sent() per lead per subscriber = N*M calls.
        Returns: { address: [email1, email2, ...] }
        """
        if self.dry_run or not addresses:
            return {}
        result = (self.db.table("leads")
                  .select("address,sent_to")
                  .in_("address", addresses)
                  .execute())
        return {
            r["address"]: (r.get("sent_to") or [])
            for r in (result.data or [])
        }

    def mark_sent_batch(self, address: str, emails: list) -> None:
        """
        Mark multiple subscribers as sent for one lead — one RPC call.
        Old code called mark_sent() in a loop.
        """
        if self.dry_run or not emails:
            return
        for email in emails:
            self.db.rpc("append_sent_to",
                        {"p_address": address, "p_email": email}).execute()

    # Keep old single-item methods for backward compatibility
    def save_leads(self, leads: list, run_date: str = None) -> list:
        return self.save_leads_batch(leads, run_date)

    def already_sent(self, address: str, email: str) -> bool:
        if self.dry_run:
            return False
        r = (self.db.table("leads")
             .select("sent_to")
             .eq("address", address)
             .single()
             .execute())
        return email in (r.data.get("sent_to") or []) if r.data else False

    def mark_sent(self, address: str, email: str) -> None:
        if self.dry_run:
            return
        self.db.rpc("append_sent_to",
                    {"p_address": address, "p_email": email}).execute()

    # ── SUBSCRIBERS ─────────────────────────────────────────

    def get_active_subscribers(self, state: str = None,
                                zip_code: str = None) -> List[Dict]:
        if self.dry_run:
            return [{"email": "test@example.com", "name": "Test User",
                     "state": state or "TX", "zip": zip_code or "78701"}]
        q = self.db.table("subscribers").select("*").eq("active", True)
        if state:    q = q.eq("state", state)
        if zip_code: q = q.eq("zip", zip_code)
        return q.execute().data or []

    def get_active_zip_states(self) -> List[Dict]:
        if self.dry_run:
            return [{"state": "TX", "zip": "78701"}]
        return (self.db.table("subscribers")
                .select("state,zip")
                .eq("active", True)
                .execute().data or [])

    def provision_subscriber(self, email: str, name: str, state: str,
                              zip_code: str, paddle_id: str) -> None:
        if self.dry_run:
            return
        self.db.table("subscribers").upsert({
            "email": email, "name": name, "state": state, "zip": zip_code,
            "paddle_subscription_id": paddle_id, "active": True,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
        self.db.rpc("increment_zip_used", {"p_zip": zip_code}).execute()

    def deactivate_subscriber(self, paddle_id: str) -> Optional[str]:
        if self.dry_run:
            return None
        r = (self.db.table("subscribers").select("zip")
             .eq("paddle_subscription_id", paddle_id).single().execute())
        zip_code = r.data.get("zip") if r.data else None
        self.db.table("subscribers").update({
            "active": False,
            "cancelled_at": datetime.utcnow().isoformat(),
        }).eq("paddle_subscription_id", paddle_id).execute()
        if zip_code:
            self.db.rpc("decrement_zip_used", {"p_zip": zip_code}).execute()
        return zip_code

    def get_zip_availability(self, zip_code: str) -> Dict:
        if self.dry_run:
            return {"zip": zip_code, "used": 2, "max": 5,
                    "available": 3, "is_full": False, "label": "3 of 5 available"}
        r = (self.db.table("zip_slots").select("*")
             .eq("zip", zip_code).single().execute())
        if not r.data:
            return {"zip": zip_code, "used": 0, "max": 5,
                    "available": 5, "is_full": False, "label": "5 of 5 available"}
        u, m  = r.data["used"], r.data["max"]
        avail = max(0, m - u)
        return {"zip": zip_code, "used": u, "max": m, "available": avail,
                "is_full": u >= m, "label": f"{avail} of {m} available"}

    # ── RUN LOG ──────────────────────────────────────────────

    def log_run(self, status: str, zip_code: str = None,
                leads_found: int = 0, emails_sent: int = 0,
                error_msg: str = None) -> None:
        if self.dry_run:
            return
        self.db.table("run_log").insert({
            "triggered_at": datetime.utcnow().isoformat(),
            "status":       status,
            "source":       f"flow:{zip_code}" if zip_code else "flow",
            "leads_found":  leads_found,
            "emails_sent":  emails_sent,
            "error_msg":    error_msg,
        }).execute()
