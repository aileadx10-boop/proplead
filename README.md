# PropLeads Pro 🏠

Automated motivated seller lead generation for real estate investors.
Every morning at 6am ET, 4 AI agents hunt, analyze, score, and write
outreach emails for the top 5 motivated sellers in your ZIP code.
Delivered straight to your inbox.

---

## What's in This Repo

```
propleads-pro/
│
├── src/propleads_pro/          ← the AI crew (Python)
│   ├── config/
│   │   ├── agents.yaml         ← edit agent prompts here
│   │   └── tasks.yaml          ← edit task instructions here
│   ├── crew.py                 ← wires agents + tasks together
│   ├── main.py                 ← flow orchestrator (runs the crew)
│   └── tools/
│       ├── attom_tool.py       ← real estate data (mock if no key)
│       ├── supabase_tool.py    ← database operations
│       └── delivery_tool.py   ← sends emails via SendGrid
│
├── railway/
│   └── server.py               ← Flask server (runs on Railway)
│
├── api/
│   ├── paddle-webhook.ts       ← receives payment events from Paddle
│   ├── trigger-crew.ts         ← Vercel Cron calls this every morning
│   └── zip-check.ts            ← landing page slot counter
│
├── supabase/
│   └── schema.sql              ← paste into Supabase SQL Editor
│
├── vercel.json                 ← cron schedule + function config
├── pyproject.toml              ← Python dependencies
├── Procfile                    ← Railway start command
├── runtime.txt                 ← Python version for Railway
└── .env.example                ← copy to .env and fill in keys
```

---

## Setup Order (follow this exactly)

### 1. Supabase — the database (20 min)
1. Go to [supabase.com](https://supabase.com) → New Project → name: `propleads-pro`
2. SQL Editor → paste `supabase/schema.sql` → Run
3. Settings → API → copy `Project URL` and `service_role` key

### 2. GitHub — upload this repo (10 min)
1. Go to [github.com](https://github.com) → New repository → `propleads-pro` → Private
2. Upload all files from this folder → Commit

### 3. API Keys (30 min)
| Key | Where | Cost |
|-----|-------|------|
| `OPENAI_API_KEY` | platform.openai.com | $10 credit |
| `SERPER_API_KEY` | serper.dev | Free (2500 searches) |
| `SENDGRID_API_KEY` | sendgrid.com | Free (100/day) |
| `ATTOM_API_KEY` | api.developer.attomdata.com | Skip for now → uses mock data |

### 4. Railway — runs the AI crew (20 min)
1. Go to [railway.app](https://railway.app) → Login with GitHub
2. New Project → Deploy from GitHub → select `propleads-pro`
3. Variables tab → add all keys from `.env.example`
4. Settings → Networking → Generate Domain → copy the URL

### 5. Vercel — hosts the website (20 min)
1. Go to [vercel.com](https://vercel.com) → Login with GitHub
2. New Project → import `propleads-pro` → Deploy
3. Settings → Environment Variables → add all keys
4. Upgrade to Pro ($20/mo) — required for Cron to work

### 6. Paddle — takes payments (1-3 days approval)
1. Go to [paddle.com](https://paddle.com) → Sign up → wait for approval
2. Catalog → Products → New → $397/month subscription
3. Developer → Notifications → add webhook URL: `https://your-vercel-url/api/paddle-webhook`

---

## Test Locally (no API keys needed)

```bash
# Install
pip install crewai[tools]

# Test run — uses mock data, no real emails sent
python -m propleads_pro.main --state TX --zip 78701
```

Expected output:
```
====================================================
  PropLeads Pro
  State: TX  |  ZIP: 78701
====================================================
[01-04] 🤖 Running 4-agent crew...
[AttomTool] MOCK MODE — returning 3 sample leads
✓ Crew done — 5 leads ready
[Supabase] DRY RUN: would save 5 leads
[Delivery] DRY RUN → test@example.com
✅ RUN COMPLETE
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```
OPENAI_API_KEY=sk-proj-...
SERPER_API_KEY=...
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGci...
SENDGRID_API_KEY=SG....
SENDGRID_FROM=reports@yourdomain.com
RAILWAY_WEBHOOK_URL=https://your-app.up.railway.app/run
RAILWAY_SECRET=any-password-you-choose
CRON_SECRET=any-password-you-choose
PADDLE_WEBHOOK_SECRET=pdl_ntfy_...
PADDLE_PRODUCT_ID=pro_01...
```

---

## Revenue Model

- **$397/month** per ZIP code subscriber
- **5 subscribers max** per ZIP (scarcity marketing)
- Break-even: **1 subscriber** covers all infrastructure costs (~$185/mo)
- Target: 10 subscribers = **$3,970/month** recurring

---

## Architecture

```
Every day at 6am ET:

Vercel Cron
    ↓  POST /api/trigger-crew
    ↓
Railway Server (always on)
    ↓  runs PropLeadsFlow
    ↓
  [Agent 1] Lead Hunter      → ATTOM + Serper  → 15-25 raw leads
  [Agent 2] Property Analyzer → Serper + Scrape → equity + comps
  [Agent 3] Motivation Scorer → pure reasoning  → top 5 leads scored
  [Agent 4] Outreach Composer → pure generation → 3 emails per lead
    ↓
  Supabase (save + dedup)
    ↓
  SendGrid → subscriber inbox
```

---

## Support

Questions? Open an issue or email support@propleadspro.com
