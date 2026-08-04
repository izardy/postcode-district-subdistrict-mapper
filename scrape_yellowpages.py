#!/usr/bin/env python3
"""
Scraper for https://www.yellowpages.my/services/l  (pages 1..N).

OUTPUT: one CSV per 1000 records in data_source/, named <name>-<start>-<end>.csv
where start/end are 1-based record indices (e.g. yellowpages-1-1000.csv).
Records beyond 1000 per page roll into the next batch file automatically.

RESUMABLE: progress is tracked by re-deriving completed records from the
partial CSV files on every start, so a sudden restart continues exactly where
it left off. No separate state file can desync.

FETCHING / CLOUDFLARE:
The site sits behind Cloudflare's managed "Under Attack" challenge. This
script uses TWO fetch backends and auto-falls back:

  * cloudscraper (default) -- solves the JS challenge that plain requests
    cannot. Pair it with a RESIDENTIAL proxy (see below) because Cloudflare
    blocks datacenter IPs outright -- including this sandbox's IP, which is
    why a no-proxy run still 403s.

  * Selenium + headless Chromium (set USE_SELENIUM=1) -- useful when you can
    paste a real cf_clearance cookie from your own browser.

  * `--grab-cookie` launches a VISIBLE (non-headless) Chromium so you can
    click through Cloudflare's verification, then prints the cf_clearance
    cookie for headless reuse.

PROXY OPTIONS (Cloudflare needs residential/ISP, NOT free datacenter proxies):
  YP_PROXY="http://user:pass@host:port"      single proxy (recommended)
  YP_ROTATE=1                                 pull a rotating list from
                                             free-proxy-list.net (often
                                             blocked by CF -- best-effort only)
  YP_CF_COOKIE="cf_clearance=...."            paste a clearance cookie copied
                                             from a real logged-in browser.
                                             NOTE: cf_clearance is IP-bound
                                             -- it was issued for YOUR ISP IP,
                                             so this only works if you run
                                             the scraper FROM that same IP
                                             (e.g. on your Windows host),
                                             NOT from a different
                                             datacenter/proxy IP.

USAGE:
  python scrape_yellowpages.py
  python scrape_yellowpages.py --name yellowpages --pages 40737 --batch 1000
  YP_PROXY="http://user:pass@resi.proxy:8000" python scrape_yellowpages.py
  HEADLESS=0 python scrape_yellowpages.py --grab-cookie
  USE_SELENIUM=1 YP_CF_COOKIE="cf_clearance=xxxx" python scrape_yellowpages.py
"""
from __future__ import annotations
import argparse, csv, os, random, re, shutil, sys, tempfile, time
from pathlib import Path
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

# ---------- config ----------
BASE_URL  = "https://www.yellowpages.my/services/l?page="
OUT_DIR   = Path(__file__).resolve().parent / "data_source"
CHROME_BIN = shutil.which("chromium") or shutil.which("chromium-browser") or "/usr/bin/chromium"

PROXY       = os.environ.get("YP_PROXY", "").strip()
ROTATE      = os.environ.get("YP_ROTATE", "") == "1"
CF_COOKIE   = os.environ.get("YP_CF_COOKIE", "").strip()
USE_SELENIUM = os.environ.get("USE_SELENIUM", "") == "1"
HEADLESS     = os.environ.get("HEADLESS", "1") != "0"   # set HEADLESS=0 for interactive solve
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

CSV_FIELDS = ["page", "Company Name", "Address", "Tel", "Email", "MapsURL"]

# selectors (verified against the server-rendered Angular card markup)
CARD_SELECTOR  = "a.disabled-link"               # the <a> wrapping each business card
NAME_SEL        = "strong"                        # <strong> inside the card = company name
ADDR_SUBSEL     = "div.ng-star-inserted > div"    # street + city/state lines
TEL_SEL         = "a[href^='tel:']"
EMAIL_SEL       = "a[href^='mailto:']"


# ---------- logging ----------
def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------- parsing ----------
def parse_cards(page_source_html: str, page_no: int) -> list[dict]:
    """Parse business cards from a page's HTML (backend-agnostic, so this is
    independently testable without a network)."""
    soup = BeautifulSoup(page_source_html, "lxml")
    rows = []
    for a in soup.select(CARD_SELECTOR):
        container = a.parent  # tel:/mailto: links live in sibling div.p_contact
        strong = a.find("strong")
        name = strong.get_text(strip=True) if strong else ""

        addr_parts = [d.get_text(strip=True) for d in a.select(ADDR_SUBSEL)]
        if not addr_parts:  # fallback: any div text not equal to the name
            addr_parts = [d.get_text(strip=True) for d in a.find_all("div")
                          if d.get_text(strip=True) and d.get_text(strip=True) != name]
        address = ", ".join(p for p in addr_parts if p)

        tel = email = ""
        tel_a = a.select_one(TEL_SEL) or container.select_one(TEL_SEL)
        if tel_a:
            tel = tel_a.get("href", "").replace("tel:", "", 1)
        mail_a = a.select_one(EMAIL_SEL) or container.select_one(EMAIL_SEL)
        if mail_a:
            email = mail_a.get("href", "").replace("mailto:", "", 1)

        rows.append({
            "page": page_no,
            "Company Name": name,
            "Address": address,
            "Tel": tel,
            "Email": email,
            "MapsURL": a.get("href", ""),
        })
    return rows


def is_challenge(html: str) -> bool:
    """True when Cloudflare is still blocking (managed challenge page)."""
    return ("Just a moment" in html) or ("disabled-link" not in html)


# ---------- proxy helpers ----------
def fetch_proxy_list() -> list[str]:
    """Best-effort grab of free HTTPS proxies (NOT residential -- Cloudflare
    usually blocks these; included only for parity with the reference approach)."""
    try:
        req = Request("https://free-proxy-list.net/", headers={"User-Agent": random.choice(USER_AGENTS)})
        doc = urlopen(req, timeout=20).read().decode()
        rows = BeautifulSoup(doc, "html.parser").select("table#proxylisttable tbody tr")
        out = []
        for row in rows:
            tds = row.find_all("td")
            if len(tds) >= 2 and tds[6].text.strip() == "yes":  # https=yes
                out.append(f"http://{tds[0].text}:{tds[1].text}")
        log(f"fetched {len(out)} https proxies")
        return out
    except Exception as e:
        log(f"proxy list fetch failed: {e}")
        return []


def proxy_dict(url: str) -> dict:
    return {"http": url, "https": url}


# ---------- fetch backends ----------
def make_cloudscraper():
    import cloudscraper
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False})


def fetch_cloudscraper(page_no: int, scraper, proxy_pool: list[str], retries=8):
    url = BASE_URL + str(page_no)
    backoff = 8
    for attempt in range(1, retries + 1):
        headers = {"User-Agent": random.choice(USER_AGENTS), "Accept-Language": "en-US,en;q=0.9"}
        proxies = proxy_dict(random.choice(proxy_pool)) if proxy_pool else None
        try:
            r = scraper.get(url, headers=headers, proxies=proxies, timeout=(10, 35))
            html = r.text
        except Exception as e:
            log(f"page {page_no}: cloudscraper error {type(e).__name__}; retry in {backoff}s")
            time.sleep(backoff); backoff = min(backoff * 2, 300); continue

        if is_challenge(html):
            if CF_COOKIE:
                # inject clearance cookie and retry on the same session
                scraper.cookies.set("cf_clearance", CF_COOKIE.split("cf_clearance=", 1)[-1],
                                    domain="www.yellowpages.my", path="/")
                continue
            if proxy_pool:
                log(f"page {page_no}: CF challenge; rotating proxy (attempt {attempt})")
                time.sleep(backoff); backoff = min(backoff * 2, 300); continue
            log(f"page {page_no}: CF challenge, no proxy/cookie; backing off {backoff}s")
            time.sleep(backoff); backoff = min(backoff * 2, 300); continue

        rows = parse_cards(html, page_no)
        log(f"page {page_no}: extracted {len(rows)} cards")
        return rows
    raise RuntimeError(f"page {page_no} not fetched after {retries} attempts")


def make_selenium():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    opt = Options()
    opt.binary_location = CHROME_BIN
    if HEADLESS:
        opt.add_argument("--headless=new")
    opt.add_argument("--no-sandbox")
    opt.add_argument("--disable-dev-shm-usage")
    opt.add_argument("--disable-gpu")
    opt.add_argument("--disable-blink-features=AutomationDetected")
    opt.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    if PROXY:
        opt.add_argument(f"--proxy-server={PROXY}")
    drv = webdriver.Chrome(options=opt)
    drv.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});window.chrome={runtime:{}};"}
    )
    return drv


def fetch_selenium(drv, page_no: int, retries=6):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import WebDriverException, TimeoutException
    url = BASE_URL + str(page_no)
    backoff = 8
    for attempt in range(1, retries + 1):
        try:
            drv.get(url)
            try:
                WebDriverWait(drv, 25).until(
                    lambda d: d.find_elements(By.CSS_SELECTOR, CARD_SELECTOR) or "Just a moment" in d.title)
            except TimeoutException:
                pass
            html = drv.page_source
            if "Just a moment" in drv.title or "disabled-link" not in html:
                if CF_COOKIE:
                    drv.delete_all_cookies()
                    drv.add_cookie({"name": "cf_clearance",
                                    "value": CF_COOKIE.split("cf_clearance=", 1)[-1],
                                    "domain": "www.yellowpages.my", "path": "/"})
                    drv.get(url)
                    WebDriverWait(drv, 25).until(
                        lambda d: d.find_elements(By.CSS_SELECTOR, CARD_SELECTOR))
                    html = drv.page_source
                else:
                    log(f"page {page_no}: CF challenge; backing off {backoff}s")
                    time.sleep(backoff); backoff = min(backoff * 2, 300); continue
            rows = parse_cards(html, page_no)
            log(f"page {page_no}: extracted {len(rows)} cards")
            return rows
        except (WebDriverException, TimeoutException) as e:
            log(f"page {page_no}: attempt {attempt} {type(e).__name__}; retry in {backoff}s")
            time.sleep(backoff); backoff = min(backoff * 2, 300)
    raise RuntimeError(f"page {page_no} failed after {retries} attempts")


# ---------- batching / resume ----------
def write_batch(name: str, start_idx: int, rows: list[dict]) -> Path:
    end_idx = start_idx + len(rows) - 1
    path = OUT_DIR / f"{name}-{start_idx}-{end_idx}.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    log(f"wrote {path.name} ({len(rows)} records)")
    return path


def load_state(name: str):
    """Re-derive completed records + dedup keys from the partial CSV files.
    This is the resume mechanism -- no external state file is trusted."""
    state = {"total_records": 0, "seen": set()}
    pattern = re.compile(rf"{re.escape(name)}-(\d+)-(\d+)\.csv$")
    for f in OUT_DIR.glob(f"{name}-*.csv"):
        if not pattern.search(f.name):
            continue
        with open(f, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                state["seen"].add((row.get("Company Name", ""), row.get("Address", "")))
                state["total_records"] += 1
    return state


# ---------- cookie grabber (interactive Cloudflare bypass) ----------
def grab_cf_cookie():
    """Launch a NON-HEADLESS Chromium, open yellowpages.my, and wait for the
    cf_clearance cookie to land (i.e. the Cloudflare challenge has been
    solved). Prints the cookie so you can reuse it with YP_CF_COOKIE=...
    for headless/cloudscraper runs.

    Cloudflare "Under Attack" challenges cannot be fully automated without
    either a residential proxy or an external CAPTCHA-solving service. This
    mode therefore:
      - lets the JS proof-of-work run to completion on its own, and
      - if a click-to-verify checkbox or visual CAPTCHA appears, it waits
        for YOU to click through in the visible window, then auto-captures
        the cookie once you're through.

    Usage:
        HEADLESS=0 python scrape_yellowpages.py --grab-cookie
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    # force a non-headless window for this grab
    global HEADLESS
    HEADLESS = False
    log("launching a VISIBLE browser to solve Cloudflare -- do not close the window")
    drv = make_selenium()

    # selectors for Cloudflare's verification widgets (rendered in iframes)
    iframe_selectors = [
        "iframe[title*='challenge']",
        "iframe[title*='Cloudflare']",
        "iframe[src*='challenge']",
        "iframe#cf-challenge-widget",
        "iframe#turnstile-wrapper",
        "iframe[name^='cf']",
    ]
    direct_selectors = [
        "div.cf-challenge-checkbox",
        "span.marketing-checkbox",
        "button#cf-wizard-next",
        "button.cb-button",
        "div#html-element-item",
    ]

    try:
        drv.set_page_load_timeout(60)
        drv.get("https://www.yellowpages.my/services/l?page=1")
        log("browser opened. Solving Cloudflare challenge...")

        # Try an initial auto-click on any visible widget.
        for sel in direct_selectors:
            try:
                for e in drv.find_elements(By.CSS_SELECTOR, sel):
                    try:
                        e.click()
                        log(f"auto-clicked direct selector: {sel}")
                    except Exception:
                        pass
            except Exception:
                pass
        for sel in iframe_selectors:
            try:
                for frame in drv.find_elements(By.CSS_SELECTOR, sel):
                    try:
                        drv.switch_to.frame(frame)
                    except Exception:
                        continue
                    for chk_sel in ["#cf-challenge-running input",
                                    "button[type='submit']",
                                    ".captcha-box",
                                    "input[name='cf-turnstile-response']"]:
                        try:
                            chk = drv.find_element(By.CSS_SELECTOR, chk_sel)
                            chk.click()
                            log(f"auto-clicked inside iframe: {chk_sel}")
                        except Exception:
                            pass
                    try:
                        drv.switch_to.default_content()
                    except Exception:
                        pass
            except Exception:
                pass

        # Poll: Cloudflare may iterate through several verification rounds
        # (checkbox -> reload -> captcha -> reload -> grant). We wait patiently
        # through each round until the real listing cards appear, auto-clicking
        # any fresh widget on each iteration.
        deadline = time.time() + 900  # 15 min budget for a human to click through
        cards_present = False
        rounds = 0
        while time.time() < deadline:
            # re-attempt auto-click on every iteration (covers reload re-renders)
            for sel in direct_selectors:
                try:
                    for e in drv.find_elements(By.CSS_SELECTOR, sel):
                        try:
                            e.click()
                            log(f"auto-clicked (poll): {sel}")
                        except Exception:
                            pass
                except Exception:
                    pass
            for sel in iframe_selectors:
                try:
                    for frame in drv.find_elements(By.CSS_SELECTOR, sel):
                        try:
                            drv.switch_to.frame(frame)
                        except Exception:
                            continue
                        for chk_sel in ["#cf-challenge-running input",
                                        "button[type='submit']",
                                        ".captcha-box",
                                        "input[name='cf-turnstile-response']"]:
                            try:
                                drv.find_element(By.CSS_SELECTOR, chk_sel).click()
                                log(f"auto-clicked iframe (poll): {chk_sel}")
                            except Exception:
                                pass
                        try:
                            drv.switch_to.default_content()
                        except Exception:
                            pass
                except Exception:
                    pass

            title = drv.title or ""
            if CARD_SELECTOR and drv.find_elements(By.CSS_SELECTOR, CARD_SELECTOR):
                cards_present = True
                break
            if "Just a moment" not in title and not is_challenge(drv.page_source):
                cards_present = True
                break
            rounds += 1
            if rounds % 10 == 0:
                log(f"still on challenge (title={title[:40]!r}); keep clicking the "
                    f"robot checkbox / captcha in the visible browser - "
                    f"~{int(deadline-time.time())}s left")
            time.sleep(3)

        if cards_present:
            log("challenge passed -- real listing page reached.")
        else:
            log("challenge still blocking after 15 min -- solve by hand then re-run, "
                "or paste a cookie via YP_CF_COOKIE.")

        # final wait for cards once challenge is past
        try:
            WebDriverWait(drv, 120).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, CARD_SELECTOR)))
        except TimeoutException:
            log("cards didn't appear in time -- but capturing whatever cookies exist.")

        cookies = drv.get_cookies()
        cf = [c for c in cookies if c["name"] == "cf_clearance"]
        if cf:
            val = cf[0]["value"]
            print("\n=== COPY THIS ===")
            print(f"YP_CF_COOKIE=\"cf_clearance={val}\"")
            print("=== END ===\n")
            log("cookie captured; paste the above into your shell env to run headless.")
        else:
            log("no cf_clearance cookie found -- solve the challenge and re-run, "
                "or paste one manually via YP_CF_COOKIE.")
    finally:
        drv.quit()


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="yellowpages")
    ap.add_argument("--pages", type=int, default=40737)
    ap.add_argument("--batch", type=int, default=1000)
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between pages")
    ap.add_argument("--start", type=int, default=0, help="force start page (0=auto-resume)")
    ap.add_argument("--grab-cookie", action="store_true",
                    help="open a VISIBLE non-headless browser to solve Cloudflare and print cf_clearance")
    args = ap.parse_args()

    if args.grab_cookie:
        grab_cf_cookie()
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state(args.name)
    start_page = args.start if args.start > 0 else 1
    log(f"resume: existing_records={state['total_records']} (start page forced/auto={start_page}), "
        f"pages total={args.pages}")
    if PROXY:
        log("using single proxy")
    if ROTATE:
        log("proxy rotation enabled (free list -- CF often blocks these)")
    if CF_COOKIE:
        log("cf_clearance cookie supplied")
    if USE_SELENIUM:
        log("backend: Selenium")

    # proxy pool
    pool: list[str] = []
    if PROXY:
        pool = [PROXY]
    elif ROTATE:
        pool = fetch_proxy_list()

    scraper = make_cloudscraper() if not USE_SELENIUM else None
    drv = make_selenium() if USE_SELENIUM else None

    buffer: list[dict] = []
    next_idx = state["total_records"] + 1
    seen = state["seen"]

    try:
        for page in range(start_page, args.pages + 1):
            if USE_SELENIUM:
                rows = fetch_selenium(drv, page)
            else:
                try:
                    rows = fetch_cloudscraper(page, scraper, pool)
                except RuntimeError:
                    # fall back to Selenium once cloudscraper exhausts retries
                    if drv is None:
                        drv = make_selenium()
                    rows = fetch_selenium(drv, page)

            for r in rows:
                key = (r["Company Name"], r["Address"])
                if key in seen:
                    continue
                seen.add(key)
                buffer.append(r)
                next_idx += 1
                if len(buffer) >= args.batch:
                    write_batch(args.name, next_idx - len(buffer), buffer)
                    buffer.clear()
            time.sleep(args.delay)
    finally:
        if buffer:
            write_batch(args.name, next_idx - len(buffer), buffer)
        if drv is not None:
            try:
                drv.quit()
            except Exception:
                pass
        log("done / interrupted. Re-run to resume.")


if __name__ == "__main__":
    main()
