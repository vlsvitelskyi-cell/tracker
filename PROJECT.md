# Revenue Tracker — Project Summary

## What was built

A system for tracking and fairly splitting Fanvue model earnings between two partners (Valerii and Vladislav). Built to scale into a SaaS product for AI model agencies.

---

## Part 1 — Withdrawal Tracker (Web App)

**URL:** https://vlsvitelskyi-cell.github.io/tracker/fanvue_tracker.html

**Tech:** HTML/JS hosted on GitHub Pages + Supabase (real-time database)

### Features
- Shows EUR balance for both partners with a blue/green progress bar
- "Remaining to withdraw" in USD calculated from total share minus already withdrawn
- Splits withdrawals fairly: accounts for different expenses per person using formula `(total + vExp - vlExp) / 2`
- Auto-suggests fair EUR split when confirming a withdrawal, adjustable manually
- Shows Wise expected rate and FX loss vs market rate
- Withdrawal history with avg rate and total losses
- Real-time sync between both users via Supabase (green "live" dot)
- Manual transaction entry for TG/PayPal directly from the Revenue tab
- New months auto-appear when scraper writes first transaction of the month

### Revenue data source
- Reads from Supabase `transactions` + `expenses` tables directly
- Fanvue transactions written automatically by scraper at 09:00 Kyiv
- TG and PayPal added manually via form on Revenue tab
- Real-time subscription on `transactions` and `expenses` — updates instantly when scraper writes

---

## Part 2 — Supabase Database

**Project:** Withdrawal_tracker
**URL:** https://bhrwrrosvmjuprkpjush.supabase.co
**Anon key:** stored in tracker HTML (public, safe for browser use)

### Schema

| Table | Purpose |
|-------|---------|
| `partners` | Valerii + Vladislav (and future partners) |
| `models` | Fanvue model accounts |
| `agencies` | Future: multi-tenant agency support |
| `transactions` | All revenue (Fanvue scraper + manual TG/PayPal) |
| `expenses` | Per-partner expenses that adjust the split |
| `withdrawals` | Withdrawal requests and confirmations |
| `withdrawal_splits` | Per-partner EUR amounts for each withdrawal |
| `split_configs` | Revenue distribution rules (agency %, model %, operator %) |
| `owner_percentages` | Custom split ratios between partners |
| `operator_shifts` | Future: operator shift tracking for commission calculation |

### Key IDs
| Entity | UUID |
|--------|------|
| Valerii (partner) | `38f3b0ad-648e-4cd7-abc6-573049b7092e` |
| Vladislav (partner) | `cc1482e8-5832-42d1-b65a-bf307400b694` |
| Main model | `7461a252-076f-4e15-9bc9-6557863d9432` |

### Real-time enabled tables
```sql
alter publication supabase_realtime add table withdrawals;
alter publication supabase_realtime add table transactions;
alter publication supabase_realtime add table withdrawal_splits;
```

---

## Part 3 — Fanvue Daily Scraper

**Repo:** https://github.com/vlsvitelskyi-cell/tracker

### Files
- `scraper.py` — Playwright script that logs into Fanvue and extracts transactions
- `.github/workflows/scraper.yml` — GitHub Actions workflow (triggered by cron-job.org)

### How it works
1. Triggered daily at **06:00 UTC = 09:00 Kyiv** via cron-job.org → GitHub Actions dispatch
2. Loads Fanvue cookies from GitHub Secret (bypasses Cloudflare login block)
3. Opens `https://www.fanvue.com/earnings`
4. Scrolls until yesterday's date header appears (loads all recent transactions)
5. Collects transactions from last 3 days (not just today — handles missed runs)
6. Count-based deduplication: checks existing rows in Supabase before inserting
7. Writes new transactions directly to Supabase `transactions` table
8. Sends Telegram summary of yesterday's transactions

### Deduplication logic
For each (date, amount) combo: counts how many times it appears in scraped results vs how many rows already exist in Supabase. Inserts only the difference. Handles legitimate duplicate amounts (two subscribers paying same price on same day).

### GitHub Secrets required
| Secret | Purpose |
|--------|---------|
| `FANVUE_COOKIES` | Exported JSON cookies from Chrome (expires every 1-2 months) |
| `SUPABASE_URL` | `https://bhrwrrosvmjuprkpjush.supabase.co` |
| `SUPABASE_KEY` | Supabase anon key |
| `SUPABASE_MODEL_ID` | `7461a252-076f-4e15-9bc9-6557863d9432` |
| `TELEGRAM_BOT_TOKEN` | Revenue Tracker bot token |
| `TELEGRAM_CHAT_ID` | Chat ID to send daily summary |

### cron-job.org
- **URL:** `https://api.github.com/repos/vlsvitelskyi-cell/tracker/actions/workflows/scraper.yml/dispatches`
- **Schedule:** 06:00 UTC daily (Asia/Nicosia timezone: set to 09:00)
- **Method:** POST with `{"ref": "main"}` and GitHub token in Authorization header

---

## Part 4 — Telegram Bot

Bot name: **Revenue Tracker**
Sends a daily morning summary of yesterday's Fanvue transactions, read directly from Supabase.

Message format:
```
📊 Fanvue 13 May 2026
10 transaction(s) — $166.38 total

  • $39.99
  • $20.00
  ...
```

---

## Monthly maintenance

Nothing required. New months appear automatically when the scraper writes the first transaction of the month. No Google Sheets to update, no manual steps.

---

## Infrastructure

| Service | Purpose | Cost |
|---------|---------|------|
| GitHub Pages | Hosts the tracker HTML | Free |
| GitHub Actions | Runs the daily scraper | Free |
| Supabase | Full database + real-time | Free tier |
| cron-job.org | Daily trigger for scraper | Free |
| Telegram Bot API | Daily revenue notifications | Free |
| Google Sheets | Archive only (no longer active data source) | Free |

---

## Roadmap

### Next: Auth + Roles
- Supabase Auth (email/password)
- Roles: Admin / Partner / Operator
- RLS policies on all tables
- Login UI in the tracker

### Later: Multi-model + Operators
- Multiple Fanvue accounts per agency
- Operator shift scheduling
- Revenue attribution per operator per shift
- Configurable split: agency % + model % + operator % + owner pool

### SaaS
- Multi-tenant (agency isolation via `agency_id`)
- Pricing: setup fee + monthly subscription
- Payment: Paddle or USDT (not Stripe — blocks adult content)

---

## Known limitations

- Fanvue cookies expire every 1-2 months — update `FANVUE_COOKIES` secret when scraper fails
- Scraper date may differ from Fanvue UI by 1 day (UTC vs Kyiv timezone)
- RLS not yet enabled — all tables are public within the anon key scope
- TG and PayPal revenue must be entered manually via the Revenue tab form
