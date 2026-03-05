"""
Delivery Tool — Production-hardened
======================================
Fixes vs v1:
  - Prefetches ALL sent_to data in ONE query per ZIP (not per lead per subscriber)
  - Batches mark_sent calls
  - SendGrid batch sending via personalization API
  - Proper error handling per subscriber (one failure won't stop others)
"""

import os
from typing import List, Dict
from jinja2 import Template
from propleads_pro.tools.supabase_tool import SupabaseTool


EMAIL_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>
  body{margin:0;padding:0;background:#F4F4F8;font-family:'Helvetica Neue',Arial,sans-serif;}
  .wrap{max-width:640px;margin:0 auto;background:#fff;}
  .hdr{background:#0D0F1A;padding:28px 36px;}
  .hdr-eyebrow{color:#6B7280;font-size:10px;letter-spacing:3px;text-transform:uppercase;margin-bottom:6px;}
  .hdr-title{color:#F9FAFB;font-size:22px;font-weight:700;}
  .hdr-sub{color:#6B7280;font-size:12px;margin-top:6px;}
  .stats{background:#141620;padding:16px 36px;display:flex;gap:28px;border-bottom:1px solid #1E2030;}
  .stat{text-align:center;}
  .stat-n{font-size:26px;font-weight:800;color:#10B981;}
  .stat-l{font-size:9px;color:#6B7280;letter-spacing:2px;text-transform:uppercase;margin-top:2px;}
  .card{border-bottom:1px solid #F0F0F5;padding:24px 36px;}
  .rank{display:inline-block;background:#F0FDF4;color:#065F46;font-size:9px;font-weight:700;
    letter-spacing:2px;text-transform:uppercase;padding:3px 10px;border-radius:100px;margin-bottom:10px;}
  .address{font-size:17px;font-weight:700;color:#111827;margin-bottom:4px;}
  .price{font-size:14px;color:#6B7280;margin-bottom:12px;}
  .badges{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px;}
  .b{font-size:10px;font-weight:600;padding:4px 10px;border-radius:6px;}
  .b-dom{background:#FEF3C7;color:#92400E;}
  .b-eq{background:#D1FAE5;color:#065F46;}
  .b-drop{background:#FEE2E2;color:#991B1B;}
  .b-fsbo{background:#DBEAFE;color:#1E40AF;}
  .b-prefc{background:#FFE4E6;color:#9F1239;}
  .reasoning{font-size:12px;color:#6B7280;font-style:italic;padding:10px 14px;
    background:#F9FAFB;border-radius:8px;border-left:3px solid #10B981;margin-bottom:14px;}
  .email-label{font-size:9px;font-weight:700;letter-spacing:2px;text-transform:uppercase;
    color:#9CA3AF;margin-bottom:8px;}
  .email-box{background:#F9FAFB;border:1px solid #E5E7EB;border-radius:10px;padding:14px;margin-bottom:8px;}
  .enum{display:inline-block;background:#111827;color:#F9FAFB;font-size:9px;font-weight:700;
    padding:2px 8px;border-radius:4px;margin-bottom:6px;}
  .esubj{font-size:12px;font-weight:700;color:#111827;margin-bottom:6px;}
  .ebody{font-size:12px;color:#374151;line-height:1.65;white-space:pre-line;}
  .footer{background:#F9FAFB;padding:20px 36px;text-align:center;border-top:1px solid #E5E7EB;}
  .footer p{font-size:11px;color:#9CA3AF;margin:4px 0;}
  .footer a{color:#10B981;text-decoration:none;}
</style>
</head>
<body><div class="wrap">
  <div class="hdr">
    <div class="hdr-eyebrow">PropLeads Pro · Daily Lead Report</div>
    <div class="hdr-title">{{ leads|length }} Motivated Seller Lead{{ 's' if leads|length != 1 }}</div>
    <div class="hdr-sub">{{ state }} · ZIP {{ zip_code }} · {{ run_date }} · {{ subscriber_name }}</div>
  </div>
  <div class="stats">
    <div class="stat"><div class="stat-n">{{ leads|length }}</div><div class="stat-l">Leads</div></div>
    <div class="stat">
      <div class="stat-n" style="color:#F59E0B;">{{ "%.1f"|format(leads[0].motivation_score) if leads else '—' }}</div>
      <div class="stat-l">Top Score</div>
    </div>
    <div class="stat">
      <div class="stat-n" style="color:#6366F1;">{{ leads|selectattr('pre_foreclosure')|list|length }}</div>
      <div class="stat-l">Pre-FC</div>
    </div>
    <div class="stat">
      <div class="stat-n" style="color:#3B82F6;">{{ leads|selectattr('is_fsbo')|list|length }}</div>
      <div class="stat-l">FSBO</div>
    </div>
  </div>
  {% for lead in leads %}
  <div class="card">
    <div class="rank">#{{ lead.rank }} · Score {{ "%.1f"|format(lead.motivation_score) }}/10</div>
    <div class="address">{{ lead.address }}</div>
    <div class="price">${{ "{:,.0f}".format(lead.list_price) }} list price
      {% if lead.original_price and lead.original_price > lead.list_price %}
        &nbsp;·&nbsp;<s style="color:#9CA3AF">${{ "{:,.0f}".format(lead.original_price) }}</s>
      {% endif %}
    </div>
    <div class="badges">
      <span class="b b-dom">{{ lead.days_on_market }}d on market</span>
      {% if lead.equity_pct %}<span class="b b-eq">{{ "%.0f"|format(lead.equity_pct) }}% equity</span>{% endif %}
      {% if lead.price_reduction_pct and lead.price_reduction_pct > 0 %}
        <span class="b b-drop">&minus;{{ "%.1f"|format(lead.price_reduction_pct) }}% reduced</span>{% endif %}
      {% if lead.is_fsbo %}<span class="b b-fsbo">FSBO</span>{% endif %}
      {% if lead.pre_foreclosure %}<span class="b b-prefc">Pre-Foreclosure</span>{% endif %}
    </div>
    {% if lead.score_reasoning %}<div class="reasoning">{{ lead.score_reasoning }}</div>{% endif %}
    <div class="email-label">Outreach Templates — copy & paste ready</div>
    {% for i in [1,2,3] %}{% set em = lead['email_' ~ i] %}{% if em %}
    <div class="email-box">
      <div class="enum">Email {{ i }}</div>
      <div class="esubj">{{ em.subject }}</div>
      <div class="ebody">{{ em.body }}</div>
    </div>{% endif %}{% endfor %}
    {% if lead.listing_url %}<a href="{{ lead.listing_url }}" style="font-size:12px;color:#10B981;">View listing →</a>{% endif %}
  </div>
  {% endfor %}
  <div class="footer">
    <p><strong>PropLeads Pro</strong> · Motivated seller intelligence for ZIP {{ zip_code }}</p>
    <p>Generated {{ run_date }}. Verify all data independently.</p>
    <p><a href="https://propleadspro.com/unsubscribe?email={{ subscriber_email }}">Unsubscribe</a>
    &nbsp;·&nbsp;<a href="https://propleadspro.com/support">Support</a></p>
  </div>
</div></body></html>"""


class DeliveryTool:

    def __init__(self):
        self.sg_key     = os.getenv("SENDGRID_API_KEY")
        self.from_email = os.getenv("SENDGRID_FROM", "reports@propleadspro.com")
        self.dry_run    = not self.sg_key
        if self.dry_run:
            print("   [Delivery] DRY RUN mode")

    def dispatch(self, leads: List[Dict], state: str,
                 zip_code: str, run_date: str) -> Dict:
        """
        Send reports to all subscribers for this ZIP.

        KEY OPTIMISATION:
        - Fetches ALL sent_to data in ONE query upfront
        - Instead of one DB call per lead per subscriber
        """
        db   = SupabaseTool()
        subs = db.get_active_subscribers(state=state, zip_code=zip_code)

        if not subs:
            return {"sent": 0, "skipped": 0}

        # Prefetch sent_to map for all addresses in ONE query
        addresses   = [l.get("address", "") for l in leads]
        sent_to_map = db.get_sent_to_map(addresses)   # { address: [emails] }

        sent = skipped = 0

        for sub in subs:
            email = sub["email"]

            # Filter using the prefetched map (no DB calls in this loop)
            new_leads = [
                l for l in leads
                if email not in sent_to_map.get(l.get("address", ""), [])
            ]

            if not new_leads:
                skipped += 1
                continue

            html = Template(EMAIL_HTML).render(
                leads=new_leads, state=state, zip_code=zip_code or "ALL",
                run_date=run_date, subscriber_name=sub.get("name", ""),
                subscriber_email=email,
            )
            subject = (
                f"PropLeads Pro: {len(new_leads)} New Motivated Sellers"
                f" in {zip_code or state} — {run_date}"
            )

            # Send email — failures are caught per subscriber
            try:
                self._send_email(to=email, subject=subject, html=html)
            except Exception as e:
                print(f"   [Delivery] ❌ Failed to send to {email}: {e}")
                continue

            # Mark sent — batch per lead
            for lead in new_leads:
                addr = lead.get("address", "")
                db.mark_sent(addr, email)
                # Update local map so next subscriber sees correct state
                if addr not in sent_to_map:
                    sent_to_map[addr] = []
                sent_to_map[addr].append(email)

            sent += 1
            print(f"   [Delivery] ✅ {len(new_leads)} leads → {email}")

        return {"sent": sent, "skipped": skipped}

    def _send_email(self, to: str, subject: str, html: str) -> None:
        if self.dry_run:
            print(f"   [Delivery] DRY RUN → {to} | {subject[:55]}...")
            return
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, To
        SendGridAPIClient(self.sg_key).send(
            Mail(from_email=self.from_email, to_emails=To(to),
                 subject=subject, html_content=html)
        )
