import asyncio
import json
import os
import sys
import requests
from datetime import date, datetime, timedelta
from playwright.async_api import async_playwright

FANVUE_COOKIES     = os.environ['FANVUE_COOKIES']
APPS_SCRIPT_URL    = os.environ['APPS_SCRIPT_URL']
APPS_SCRIPT_SECRET = os.environ['APPS_SCRIPT_SECRET']

async def scrape():
    today = date.today()
    transactions = []

    try:
        raw_cookies = json.loads(FANVUE_COOKIES)
    except Exception as e:
        print(f"ERROR: Could not parse FANVUE_COOKIES: {e}")
        sys.exit(1)

    pw_cookies = []
    for c in raw_cookies:
        cookie = {
            'name':   c.get('name', ''),
            'value':  c.get('value', ''),
            'domain': c.get('domain', '.fanvue.com'),
            'path':   c.get('path', '/'),
        }
        if c.get('expirationDate'):
            cookie['expires'] = int(c['expirationDate'])
        if 'secure' in c:
            cookie['secure'] = c['secure']
        if 'httpOnly' in c:
            cookie['httpOnly'] = c['httpOnly']
        if 'sameSite' in c:
            val = c['sameSite']
            if val in ('Strict', 'Lax', 'None'):
                cookie['sameSite'] = val
        pw_cookies.append(cookie)

    print(f"Loaded {len(pw_cookies)} cookies")

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

        await context.add_cookies(pw_cookies)
        print("Cookies injected")

        page = await context.new_page()

        print("Loading earnings page...")
        await page.goto('https://www.fanvue.com/earnings',
                        wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(8000)

        current_url = page.url
        print(f"URL after goto: {current_url}")
        await page.screenshot(path='earnings_page.png')
        print("Screenshot saved: earnings_page.png")

        if 'signin' in current_url or 'signup' in current_url:
            print("ERROR: Not logged in - cookies may have expired.")
            await browser.close()
            sys.exit(1)

        # Scroll until yesterday's date header appears
        # This ensures ALL of today's transactions are loaded before extracting
        yesterday = (today - timedelta(days=1)).strftime('%B %-d, %Y')
        print(f"Scrolling until '{yesterday}' appears...")
        max_scrolls = 25
        for i in range(max_scrolls):
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(1500)
            found = await page.evaluate(
                '''(target) => {
                    const walker = document.createTreeWalker(
                        document.body, NodeFilter.SHOW_TEXT, null, false);
                    let node;
                    while ((node = walker.nextNode())) {
                        if (node.textContent.trim() === target) return true;
                    }
                    return false;
                }''',
                yesterday
            )
            if found:
                print(f"Found '{yesterday}' after {i+1} scroll(s) — all today's transactions loaded")
                break
            if i == max_scrolls - 1:
                print(f"Warning: '{yesterday}' not found after {max_scrolls} scrolls, proceeding anyway")

        # Extract transactions
        raw = await page.evaluate('''() => {
            const results = [];
            let currentDate = null;
            const walker = document.createTreeWalker(
                document.body, NodeFilter.SHOW_TEXT, null, false);
            let node;
            while ((node = walker.nextNode())) {
                const text = node.textContent.trim();
                if (!text) continue;
                if (/^[A-Z][a-z]+ \\d{1,2}, \\d{4}$/.test(text)) {
                    currentDate = text;
                    continue;
                }
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

        print(f"Raw entries found: {len(raw)}")
        print(f"Today is: {today}")
        for item in raw:
            print(f"  Found: {item['date_str']} ${item['amount']}")

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

        print(f"Today's transactions: {len(transactions)}")
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
