import asyncio
import json
import os
import sys
import requests
from datetime import date, datetime
from playwright.async_api import async_playwright

FANVUE_EMAIL    = os.environ['FANVUE_EMAIL']
FANVUE_PASSWORD = os.environ['FANVUE_PASSWORD']
APPS_SCRIPT_URL = os.environ['APPS_SCRIPT_URL']
APPS_SCRIPT_SECRET = os.environ['APPS_SCRIPT_SECRET']

async def scrape():
    today = date.today()
    transactions = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage',
                  '--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/124.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 900},
            locale='en-US',
            timezone_id='Europe/Paris',
        )
        await context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )

        page = await context.new_page()

        # --- Login ---
        print("Logging in to Fanvue...")
        await page.goto('https://fanvue.com/sign-in', wait_until='networkidle')
        await page.wait_for_timeout(4000)

        # Screenshot for debug
        await page.screenshot(path='login_page.png')
        print("Screenshot saved: login_page.png")
        print(f"Page URL: {page.url}")
        print(f"Page title: {await page.title()}")

        # Try multiple selectors for email field
        email_selectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[placeholder*="email" i]',
            'input[autocomplete="email"]',
            'input[id*="email" i]',
        ]
        email_found = False
        for sel in email_selectors:
            try:
                await page.wait_for_selector(sel, timeout=5000)
                await page.fill(sel, FANVUE_EMAIL)
                print(f"Email filled using selector: {sel}")
                email_found = True
                break
            except Exception:
                continue

        if not email_found:
            # Print all inputs on the page for debugging
            inputs = await page.evaluate('''() => {
                return Array.from(document.querySelectorAll('input')).map(i => ({
                    type: i.type, name: i.name, id: i.id,
                    placeholder: i.placeholder, autocomplete: i.autocomplete
                }));
            }''')
            print(f"Available inputs on page: {inputs}")
            await browser.close()
            sys.exit(1)

        await page.wait_for_timeout(400)

        # Try multiple selectors for password field
        pass_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[placeholder*="password" i]',
        ]
        for sel in pass_selectors:
            try:
                await page.wait_for_selector(sel, timeout=5000)
                await page.fill(sel, FANVUE_PASSWORD)
                print(f"Password filled using selector: {sel}")
                break
            except Exception:
                continue

        await page.wait_for_timeout(400)
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(7000)

        current_url = page.url
        print(f"After login URL: {current_url}")
        if 'sign-in' in current_url:
            print("ERROR: Login failed. Check credentials.")
            await browser.close()
            return []

        # --- Go to earnings ---
        print("Loading earnings page...")
        await page.goto('https://fanvue.com/payouts', wait_until='domcontentloaded')
        await page.wait_for_timeout(4000)

        # Scroll to load all transactions
        for _ in range(3):
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(1500)

        # --- Extract transactions ---
        raw = await page.evaluate('''() => {
            const results = [];
            let currentDate = null;

            // Walk all leaf text nodes to find date headers and amounts
            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_TEXT,
                null,
                false
            );

            let node;
            while ((node = walker.nextNode())) {
                const text = node.textContent.trim();
                if (!text) continue;

                // Date header: "May 10, 2026"
                if (/^[A-Z][a-z]+ \\d{1,2}, \\d{4}$/.test(text)) {
                    currentDate = text;
                    continue;
                }

                // Amount: "$8.00"  (standalone dollar amount)
                const m = text.match(/^\\$([0-9]+\\.[0-9]{2})$/);
                if (m && currentDate) {
                    const amount = parseFloat(m[1]);
                    if (amount > 0) {
                        results.push({ date_str: currentDate, amount: amount });
                    }
                }
            }
            return results;
        }''')

        print(f"Raw entries found on page: {len(raw)}")

        for item in raw:
            try:
                tx_date = datetime.strptime(item['date_str'], '%B %d, %Y').date()
                if tx_date == today:
                    transactions.append({
                        'date': tx_date.isoformat(),
                        'amount': item['amount']
                    })
            except Exception as ex:
                print(f"Date parse error: {ex}")

        print(f"Today's non-zero transactions: {len(transactions)}")
        for t in transactions:
            print(f"  {t['date']}  ${t['amount']}")

        await browser.close()

    return transactions


async def main():
    transactions = await scrape()

    if not transactions:
        print("Nothing to send today.")
        return

    print(f"\nSending {len(transactions)} transactions to Google Sheets...")
    try:
        resp = requests.post(
            APPS_SCRIPT_URL,
            json={'secret': APPS_SCRIPT_SECRET, 'transactions': transactions},
            timeout=30
        )
        print(f"Response {resp.status_code}: {resp.text}")
    except Exception as ex:
        print(f"Request error: {ex}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
