"""
Real Reddit browser poster via old.reddit.com.

Uses the same triangle-waypoint + cubic Bezier + Gaussian noise mouse
algorithm as playwright_agent.py, but navigates real Reddit instead of
the local simulation server.

old.reddit.com is used because its DOM is stable and straightforward
(plain HTML form), unlike the new React-based UI which uses shadow DOM
and contenteditable elements that change constantly.

Usage:
  # Standard Playwright (headless Chromium):
  python sim/bot/reddit_browser_agent.py --sub test --posts 1

  # Visible browser (watch it navigate):
  python sim/bot/reddit_browser_agent.py --sub test --posts 1 --visible

  # CloakBrowser (stealth Chromium binary, harder to fingerprint):
  python sim/bot/reddit_browser_agent.py --sub test --posts 1 --stealth --visible

  # Dry-run (navigate + type but don't click submit):
  python sim/bot/reddit_browser_agent.py --sub MMA --posts 1 --visible --dry-run

Credentials: sim/bot/.env
  REDDIT_USERNAME=your_username
  REDDIT_PASSWORD=your_password
"""
import argparse
import math
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── load .env ─────────────────────────────────────────────────────────────────

def _load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

BASE = "https://old.reddit.com"


# ── Gaussian primitives ────────────────────────────────────────────────────────

def g(mu, sigma, lo=None, hi=None):
    v = random.gauss(mu, sigma)
    if lo is not None: v = max(lo, v)
    if hi is not None: v = min(hi, v)
    return v


# ── Triangle waypoints + Bezier (same algorithm as playwright_agent) ──────────

def _bezier(t, pts):
    p = list(pts)
    while len(p) > 1:
        p = [(p[i][0]*(1-t)+p[i+1][0]*t, p[i][1]*(1-t)+p[i+1][1]*t)
             for i in range(len(p)-1)]
    return p[0]


def _triangle_waypoints(x0, y0, x1, y1, n=None):
    dist = math.hypot(x1-x0, y1-y0) or 1.0
    if n is None:
        n = random.choices([0,1,2], weights=[0.2,0.5,0.3])[0] if dist > 80 \
            else random.choices([0,1], weights=[0.5,0.5])[0]
    waypoints = [(x0, y0)]
    dx, dy = x1-x0, y1-y0
    px, py = -dy/dist, dx/dist
    for t in sorted(random.uniform(0.2, 0.8) for _ in range(n)):
        sigma  = dist * g(0.15, 0.05, lo=0.05, hi=0.35)
        offset = random.gauss(0, sigma)
        waypoints.append((x0+dx*t + px*offset, y0+dy*t + py*offset))
    waypoints.append((x1, y1))
    return waypoints


def _move_segment(page, x0, y0, x1, y1):
    dist  = math.hypot(x1-x0, y1-y0)
    steps = max(12, int(dist/6))
    jit   = max(10.0, dist*0.2)
    t1 = g(0.30, 0.08, lo=0.15, hi=0.45)
    t2 = g(0.70, 0.08, lo=0.55, hi=0.85)
    ctrl = [
        (x0, y0),
        (x0+(x1-x0)*t1+g(0,jit), y0+(y1-y0)*t1+g(0,jit)),
        (x0+(x1-x0)*t2+g(0,jit), y0+(y1-y0)*t2+g(0,jit)),
        (x1, y1),
    ]
    for i in range(steps+1):
        t = i/steps
        bx, by = _bezier(t, ctrl)
        page.mouse.move(bx+g(0,1.2), by+g(0,1.2))
        speed = 0.5 + 0.5*math.sin(math.pi*t)
        time.sleep(g(0.004, 0.0015, lo=0.001) / (speed+0.1))


def move_mouse(page, x, y):
    cx = page.evaluate("() => window._mx || 400")
    cy = page.evaluate("() => window._my || 300")
    waypoints = _triangle_waypoints(cx, cy, x, y)
    for i in range(len(waypoints)-1):
        ax, ay = waypoints[i]
        bx, by = waypoints[i+1]
        _move_segment(page, ax, ay, bx, by)
        if i < len(waypoints)-2:
            time.sleep(g(0.04, 0.02, lo=0.01))
    page.evaluate(f"() => {{ window._mx={x}; window._my={y}; }}")


def gaussian_click(page, selector, sigma=3.0, timeout=8000):
    el  = page.locator(selector).first
    el.wait_for(state="visible", timeout=timeout)
    box = el.bounding_box()
    if not box:
        el.click()
        return
    cx = box["x"] + box["width"]/2  + g(0, sigma)
    cy = box["y"] + box["height"]/2 + g(0, sigma)
    move_mouse(page, cx, cy)
    hold = int(g(90, 35, lo=40, hi=320))
    page.mouse.down()
    time.sleep(hold/1000)
    page.mouse.up()


def gaussian_type(page, selector, text, timeout=8000):
    gaussian_click(page, selector, timeout=timeout)
    time.sleep(g(0.35, 0.12, lo=0.15))
    for char in text:
        page.keyboard.type(char)
        delay = g(0.09, 0.04, lo=0.03, hi=0.45)
        if random.random() < 0.05:
            delay += g(0.55, 0.25, lo=0.25)
        time.sleep(delay)


# ── Post bank ─────────────────────────────────────────────────────────────────

_POSTS = {
    "test": [
        ("Testing automated post — please ignore",
         "This is a research test post. Part of an academic study on bot detection."),
        ("API and browser posting comparison test",
         "Testing a browser-based submission flow. No action needed."),
    ],
    "MMA": [
        ("Jon Jones vs Stipe — who wins the rematch?",
         "Jones by decision, Stipe's chin can't survive 5 rounds of Jon's pace. "
         "What do you think?"),
        ("Best KO finish of the decade?",
         "Velasquez vs Brock still hits different. Pure fury and speed on display."),
        ("Is wrestling still the most important base in MMA?",
         "With how BJJ has evolved I'd argue striking matters more now. "
         "The guard work we're seeing in 2024 would have been elite 10 years ago."),
        ("Izzy's striking variety is genuinely insane",
         "Seven different striking styles in one fighter. "
         "Genuinely unprecedented in MMA history. The Muay Thai switch was the wildest."),
        ("Poirier's legacy after retirement",
         "Top 5 LW all time imo. That body shot against McGregor was pure art. "
         "Dustin earned every bit of respect he gets."),
    ],
}

def _pick_post(sub):
    bank = _POSTS.get(sub, _POSTS["test"])
    return random.choice(bank)


# ── Reddit navigation ──────────────────────────────────────────────────────────

def _is_logged_in(page):
    try:
        page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=15000)
        time.sleep(g(1.5, 0.5, lo=0.8))
        # old Reddit shows username in top-right when logged in
        user_link = page.locator("#header-bottom-right .user a").first
        text = user_link.inner_text(timeout=3000)
        return bool(text.strip())
    except Exception:
        return False


def _login(page, username, password):
    print("[LOGIN] Navigating to login page...")
    page.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=15000)
    time.sleep(g(2.0, 0.6, lo=1.2))

    # Scroll a bit before interacting
    page.mouse.wheel(0, int(g(80, 30, lo=20)))
    time.sleep(g(0.8, 0.3, lo=0.3))

    print("[LOGIN] Typing username...")
    gaussian_type(page, "input[name='user']", username)
    time.sleep(g(0.5, 0.2, lo=0.2))

    print("[LOGIN] Typing password...")
    gaussian_type(page, "input[name='passwd']", password)
    time.sleep(g(0.8, 0.3, lo=0.4))

    # Re-read before submitting
    time.sleep(g(1.2, 0.5, lo=0.6))

    print("[LOGIN] Clicking login button...")
    gaussian_click(page, "button[type='submit']", sigma=4.0)
    time.sleep(g(3.0, 0.8, lo=2.0))

    # Verify login succeeded
    try:
        user_link = page.locator("#header-bottom-right .user a").first
        logged_user = user_link.inner_text(timeout=5000).strip()
        if logged_user:
            print(f"[LOGIN] Logged in as u/{logged_user}")
            return True
    except Exception:
        pass

    print("[LOGIN] Login may have failed — check credentials or CAPTCHA")
    return False


def _submit_post(page, sub, title, body, dry_run=False):
    url = f"{BASE}/r/{sub}/submit?type=self"
    print(f"[POST] Navigating to r/{sub}/submit...")
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    time.sleep(g(1.5, 0.5, lo=0.8))

    # Scroll down slightly
    page.mouse.wheel(0, int(g(100, 40, lo=30)))
    time.sleep(g(1.0, 0.4, lo=0.4))

    print(f"[POST] Typing title ({len(title)} chars)...")
    gaussian_type(page, "input[name='title']", title)
    time.sleep(g(0.7, 0.25, lo=0.25))

    print(f"[POST] Typing body ({len(body)} chars)...")
    gaussian_type(page, "textarea[name='text']", body)
    time.sleep(g(1.0, 0.4, lo=0.5))

    # Re-read pause
    reread = g(2.5, 0.9, lo=1.2)
    print(f"[POST] Re-reading for {reread:.1f}s...")
    time.sleep(reread)

    if dry_run:
        print(f"[DRY-RUN] Would click submit now — skipping.")
        return None

    print("[POST] Clicking submit...")
    gaussian_click(page, "button.submit[type='submit']", sigma=4.0)
    time.sleep(g(3.0, 0.8, lo=2.0))

    # After submit, Reddit redirects to the new post's page
    current = page.url
    if "/comments/" in current or sub.lower() in current.lower():
        print(f"[POST] Submitted! URL: {current}")
        return current
    else:
        print(f"[POST] Unexpected URL after submit: {current}")
        return current


# ── Stats ─────────────────────────────────────────────────────────────────────

@dataclass
class Stats:
    sent:    int = 0
    success: int = 0
    failed:  int = 0
    urls:    list = field(default_factory=list)


# ── Runner ────────────────────────────────────────────────────────────────────

def run(sub="test", n=1, headless=True, stealth=False, dry_run=False):
    username = os.environ.get("REDDIT_USERNAME")
    password = os.environ.get("REDDIT_PASSWORD")
    if not username or not password:
        raise EnvironmentError(
            "Set REDDIT_USERNAME and REDDIT_PASSWORD in sim/bot/.env"
        )

    stats = Stats()
    mode_str = ("CloakBrowser" if stealth else "Playwright") + (" [DRY-RUN]" if dry_run else "")

    print(f"\n{'='*60}")
    print(f"  Reddit Browser Agent | r/{sub} | posts={n} | {mode_str}")
    print(f"  Target: {BASE}")
    print(f"{'='*60}\n")

    if stealth:
        from cloakbrowser import launch
        browser = launch(
            headless=headless,
            args=["--no-sandbox", "--disable-notifications"],
        )
        ctx = browser.new_context(
            viewport={"width": random.randint(1280,1920), "height": random.randint(768,1080)},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = ctx.new_page()
        page.add_init_script("window._mx=400; window._my=300;")

        try:
            _login(page, username, password)
            for i in range(n):
                title, body = _pick_post(sub)
                print(f"\n[{i+1}/{n}] {title[:55]}")
                url = _submit_post(page, sub, title, body, dry_run=dry_run)
                stats.sent += 1
                if url:
                    stats.success += 1
                    stats.urls.append(url)
                else:
                    stats.failed += 1
                if i < n-1:
                    wait = g(20.0, 7.0, lo=10.0)
                    print(f"    [wait] {wait:.1f}s...")
                    time.sleep(wait)
        finally:
            browser.close()

    else:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            ctx = browser.new_context(
                viewport={"width": random.randint(1280,1920), "height": random.randint(768,1080)},
                user_agent=random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
                ]),
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            page = ctx.new_page()
            page.add_init_script("window._mx=400; window._my=300;")

            try:
                _login(page, username, password)
                for i in range(n):
                    title, body = _pick_post(sub)
                    print(f"\n[{i+1}/{n}] {title[:55]}")
                    url = _submit_post(page, sub, title, body, dry_run=dry_run)
                    stats.sent += 1
                    if url:
                        stats.success += 1
                        stats.urls.append(url)
                    else:
                        stats.failed += 1
                    if i < n-1:
                        wait = g(20.0, 7.0, lo=10.0)
                        print(f"    [wait] {wait:.1f}s...")
                        time.sleep(wait)
            finally:
                browser.close()

    print(f"\n{'-'*60}")
    print(f"  Results: {stats.success} success / {stats.failed} failed / {stats.sent} sent")
    for url in stats.urls:
        print(f"  {url}")
    print(f"{'-'*60}\n")
    return stats


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real Reddit browser poster")
    parser.add_argument("--sub",      default="test",
                        help="Subreddit to post in (default: test)")
    parser.add_argument("--posts",    type=int, default=1)
    parser.add_argument("--visible",  action="store_true",
                        help="Show browser window")
    parser.add_argument("--stealth",  action="store_true",
                        help="Use CloakBrowser instead of Playwright")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Type everything but don't click submit")
    args = parser.parse_args()

    run(
        sub=args.sub,
        n=args.posts,
        headless=not args.visible,
        stealth=args.stealth,
        dry_run=args.dry_run,
    )
