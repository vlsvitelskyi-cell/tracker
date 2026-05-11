# Fanvue Withdrawal Tracker — Project Summary

## What was built

A system for tracking and fairly splitting Fanvue model earnings between two partners (Valerii and Vladislav), consisting of three interconnected parts.

---

## Part 1 — Withdrawal Tracker (Web App)

**URL:** https://vlsvitelskyi-cell.github.io/tracker/fanvue_tracker.html

**Tech:** HTML/JS hosted on GitHub Pages + Supabase (real-time database)

### Features
- Shows EUR balance for both partners with a blue/green progress bar
- "Remaining to withdraw" in USD calculated from monthly shares minus already withdrawn
- Splits withdrawals fairly: accounts for different expenses per person using formula `(total + vExp - vlExp) / 2`
- Auto-suggests fair EUR split when confirming a withdrawal, adjustable manually
- Shows Revolut expected rate (1 USD = 1/1.17 EUR) and loss vs market rate
- Withdrawal history with avg rate and total losses
- Real-time sync between both users via Supabase (green "live" dot)
- Google Sheets auto-sync on page open

### Monthly Revenue sync
- Reads from Google Sheets `Data` tab via CSV endpoint
- Auto-syncs on page load if URL is saved
- Manual sync button as fallback

---

## Part 2 — Google Sheets Setup

**File:** https://docs.google.com/spreadsheets/d/1lqVFC9dh4v5OeRoW7EumtWFGNvBntSw_3MPiVfThIII

### Structure
- Monthly sheets: `march'26`, `april'26`, `may'26`, etc.
  - Column F: date of transaction
  - Column G: amount (USD)
- `Data` tab: summary row per month for the tracker
  - Columns: `month_name | fanvue | tg | paypal | vExp | vlExp`
  - Pulls values from each monthly sheet via formulas

### Apps Script (Web App)
Deployed as a Web App that accepts POST requests from the scraper.

**Logic:**
1. Receives `{ secret, transactions: [{date, amount}] }`
2. Determines sheet name from transaction date (e.g. `may'26`)
3. Counts how many times each date+amount combo already exists in column F+G
4. Adds only the missing difference (prevents duplicates even with same-price subscriptions)
5. Copies date format from the row above to match existing style

**Secret:** `fvt-2026-x7k9m3p`

---

## Part 3 — Fanvue Daily Scraper

**Repo:** https://github.com/vlsvitelskyi-cell/tracker

### Files
- `scraper.py` — Playwright script that logs into Fanvue and extracts transactions
- `.github/workflows/scraper.yml` — GitHub Actions workflow

### How it works
1. Runs daily at **20:55 UTC = 23:55 Kyiv (UTC+3 summer)**
2. Loads Fanvue cookies from GitHub Secret (bypasses Cloudflare login block)
3. Opens `https://www.fanvue.com/earnings`
4. Scrolls to load all transactions
5. Filters only today's non-zero transactions
6. POSTs to Google Apps Script URL
7. Apps Script writes to the correct monthly sheet

### GitHub Secrets required
| Secret | Value |
|--------|-------|
| `FANVUE_COOKIES` | Exported JSON cookies from Chrome (expires every 1-2 months) |
| `APPS_SCRIPT_URL` | Google Apps Script web app URL |
| `APPS_SCRIPT_SECRET` | `fvt-2026-x7k9m3p` |

---

## Monthly maintenance checklist

At the start of each month:
1. Duplicate the previous month's sheet in Google Sheets (right-click tab → Duplicate)
2. Rename it to `june'26`, `july'26`, etc.
3. Clear the data rows (keep structure and headers)
4. Add a new row in the `Data` tab with formulas pointing to the new sheet
5. In the tracker, click `+ Month` or it will auto-appear after next Sync

---

## Infrastructure

| Service | Purpose | Cost |
|---------|---------|------|
| GitHub Pages | Hosts the tracker HTML | Free |
| GitHub Actions | Runs the daily scraper | Free |
| Supabase | Real-time database for withdrawals | Free tier |
| Google Sheets | Monthly revenue data source | Free |
| Google Apps Script | Receives and writes Fanvue data | Free |

---

## Supabase

**Project:** Withdrawal_tracker  
**URL:** https://bhrwrrosvmjuprkpjush.supabase.co  
**Table:** `withdrawals`  
**Key:** Legacy anon key (stored in tracker HTML)

Real-time enabled via:
```sql
alter publication supabase_realtime add table withdrawals;
```

---

## Known limitations

- Fanvue cookies expire every 1-2 months — update `FANVUE_COOKIES` secret when scraper emails a failure notification
- GitHub Actions scheduled runs can be delayed or skipped on inactive repos
- TG and PayPal revenue must still be entered manually in Google Sheets
- Scraper runs at 23:55 — transactions after midnight are captured the next day's run
- New month sheet must be created manually before the 1st of each month
