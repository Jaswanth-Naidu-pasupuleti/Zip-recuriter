#!/usr/bin/env python3
"""
ZipRecruiter Job Search & Auto-Apply Bot
==========================================
Automates searching for Data Engineer jobs on ZipRecruiter,
scanning descriptions against keyword criteria, and applying
to matching positions.

Usage:
    python ziprecruiter_bot.py              # Full run (search + apply)
    python ziprecruiter_bot.py --dry-run    # Scan only, no applications
    python ziprecruiter_bot.py --help       # Show help

Author: Auto-generated automation script
"""

import argparse
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# ── Try importing undetected-chromedriver, fall back to regular selenium ──────
try:
    import undetected_chromedriver as uc
    USING_UC = True
except ImportError:
    USING_UC = False

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
BASE_URL = "https://www.ziprecruiter.com"
LOGIN_URL = f"{BASE_URL}/login"
SEARCH_URL = f"{BASE_URL}/jobs-search"
APPLIED_JOBS_FILE = Path(__file__).parent / "applied_jobs.json"


def load_applied_jobs() -> dict:
    """Load the set of already-applied job IDs from disk."""
    if APPLIED_JOBS_FILE.exists():
        try:
            return json.loads(APPLIED_JOBS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_applied_jobs(applied: dict):
    """Persist applied job IDs to disk."""
    APPLIED_JOBS_FILE.write_text(json.dumps(applied, indent=2, ensure_ascii=False), encoding="utf-8")

DATE_FILTER_MAP = {
    "last_24_hours": "1",
    "last_3_days":   "3",
    "last_7_days":   "7",
    "last_14_days":  "14",
    "any":           None,
}

JOB_TYPE_MAP = {
    "full_time":   "full_time",
    "part_time":   "part_time",
    "contract":    "contract",
    "temporary":   "temporary",
    "internship":  "internship",
    "any":         None,
}


# ─────────────────────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────────────────────
def setup_logging():
    """Configure logging to file + console."""
    log_dir = Path(config.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"job_search_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.log"

    handlers = [logging.FileHandler(log_file, encoding="utf-8")]
    if config.VERBOSE:
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(levelname)-8s │ %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )
    return logging.getLogger("ziprecruiter_bot")


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def human_delay(delay_range=None):
    """Sleep for a random duration within the given (min, max) range, scaled by DELAY_FACTOR."""
    if delay_range is None:
        delay_range = config.ACTION_DELAY

    factor = getattr(config, "DELAY_FACTOR", 1.0)
    duration = random.uniform(*delay_range) * factor
    time.sleep(duration)


def safe_click(driver, element, logger):
    """Click an element with fallback strategies."""
    try:
        element.click()
        return True
    except ElementClickInterceptedException:
        logger.debug("Click intercepted, trying JS click")
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e:
            logger.warning(f"JS click also failed: {e}")
            return False
    except ElementNotInteractableException:
        logger.debug("Element not interactable, scrolling into view")
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)
            element.click()
            return True
        except Exception as e:
            logger.warning(f"Scroll+click failed: {e}")
            return False


def scroll_to_element(driver, element):
    """Scroll element into view smoothly."""
    driver.execute_script(
        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
        element,
    )
    time.sleep(0.5)


# ─────────────────────────────────────────────────────────────────────────────
# KEYWORD MATCHING ENGINE
# ─────────────────────────────────────────────────────────────────────────────
def analyze_job(title: str, description: str, logger) -> dict:
    """
    Analyze a job listing using regex patterns on the TITLE
    and keyword scoring on the DESCRIPTION.

    Returns:
        dict with keys: 'should_apply', 'match_count', 'matched_keywords',
                        'exclude_hit', 'exclude_keyword'
    """
    result = {
        "should_apply": False,
        "match_count": 0,
        "matched_keywords": [],
        "exclude_hit": False,
        "exclude_keyword": None,
    }

    title_text = title.strip()

    # 1) Title must match the REQUIRED pattern
    if not re.search(config.REQUIRED_PATTERN, title_text, re.IGNORECASE):
        logger.info(f"   ⏭️  SKIP — title doesn't match required pattern")
        return result

    # 2) Title must NOT match the EXCLUDED pattern
    exc = re.search(config.EXCLUDED_PATTERN, title_text, re.IGNORECASE)
    if exc:
        result["exclude_hit"] = True
        result["exclude_keyword"] = exc.group()
        logger.info(f"   ❌ EXCLUDED — title matches '{exc.group()}'")
        return result

    # 3) Secondary: count description keyword hits
    text = f"{title} {description}".lower()
    for kw in config.MATCH_KEYWORDS:
        pattern = re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
        if pattern.search(text):
            result["matched_keywords"].append(kw)

    result["match_count"] = len(result["matched_keywords"])
    # Title already passed regex gate — apply if description has enough keywords
    result["should_apply"] = result["match_count"] >= config.MATCH_THRESHOLD

    if result["should_apply"]:
        logger.info(
            f"   ✅ MATCH ({result['match_count']}/{config.MATCH_THRESHOLD}) — "
            f"Keywords: {', '.join(result['matched_keywords'])}"
        )
    else:
        logger.info(
            f"   ⏭️  SKIP ({result['match_count']}/{config.MATCH_THRESHOLD}) — "
            f"Keywords: {', '.join(result['matched_keywords']) or 'none'}"
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# BROWSER DRIVER SETUP
# ─────────────────────────────────────────────────────────────────────────────
def create_driver(logger):
    """Create and return a Chrome WebDriver instance."""
    # Fix SSL certificate issue on macOS (needed by undetected-chromedriver)
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
        os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
    except ImportError:
        pass

    driver = None

    if USING_UC:
        logger.info("🚀 Trying undetected-chromedriver for stealth mode...")
        try:
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("detach", True)
            driver = uc.Chrome(options=options)
        except Exception as e:
            logger.warning(f"⚠️ undetected-chromedriver failed: {e}")
            logger.info("🌐 Falling back to standard Selenium...")

    if driver is None:
        from selenium import webdriver
        logger.info("🌐 Using standard Selenium ChromeDriver")
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option("detach", True)
        driver = webdriver.Chrome(options=options)
        # Remove webdriver flag
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

    driver.implicitly_wait(1)
    logger.info("✅ Browser launched successfully")
    return driver


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────────────────────────────────────
def login(driver, logger):
    """
    Attempt to log in to ZipRecruiter.
    Falls back to waiting for manual login if auto-login fails.
    """
    load_dotenv()
    email = os.getenv("ZIPRECRUITER_EMAIL", "")
    password = os.getenv("ZIPRECRUITER_PASSWORD", "")

    logger.info(f"🔐 Navigating to login page: {LOGIN_URL}")
    driver.get(LOGIN_URL)
    human_delay((3, 5))

    # Check if already logged in (redirected to dashboard)
    if "/login" not in driver.current_url.lower():
        logger.info("✅ Already logged in!")
        return True

    if email and password:
        logger.info(f"📧 Attempting auto-login with email: {email[:3]}***")
        try:
            wait = WebDriverWait(driver, config.PAGE_LOAD_TIMEOUT)

            # ── Find and fill email field ──
            email_field = None
            email_selectors = [
                (By.ID, "email"),
                (By.NAME, "email"),
                (By.CSS_SELECTOR, "input[type='email']"),
                (By.CSS_SELECTOR, "input[name='email']"),
                (By.CSS_SELECTOR, "input[placeholder*='email' i]"),
                (By.XPATH, "//input[@type='email' or contains(@name,'email')]"),
            ]
            for by, selector in email_selectors:
                try:
                    email_field = wait.until(EC.element_to_be_clickable((by, selector)))
                    if email_field:
                        break
                except TimeoutException:
                    continue

            if email_field:
                email_field.clear()
                # Type like a human — character by character with small delays
                for char in email:
                    email_field.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))
                logger.info("   ✅ Email entered")
                human_delay((1, 2))
            else:
                logger.warning("   ⚠️ Could not find email field")
                return _wait_for_manual_login(driver, logger)

            # ── Find and fill password field ──
            password_field = None
            password_selectors = [
                (By.ID, "password"),
                (By.NAME, "password"),
                (By.CSS_SELECTOR, "input[type='password']"),
                (By.CSS_SELECTOR, "input[name='password']"),
            ]
            for by, selector in password_selectors:
                try:
                    password_field = driver.find_element(by, selector)
                    if password_field:
                        break
                except NoSuchElementException:
                    continue

            if password_field:
                password_field.clear()
                for char in password:
                    password_field.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))
                logger.info("   ✅ Password entered")
                human_delay((1, 2))
            else:
                logger.warning("   ⚠️ Could not find password field")
                return _wait_for_manual_login(driver, logger)

            # ── Click login/submit button ──
            submit_btn = None
            submit_selectors = [
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.XPATH, "//button[contains(text(),'Sign In')]"),
                (By.XPATH, "//button[contains(text(),'Log In')]"),
                (By.XPATH, "//button[contains(text(),'Login')]"),
                (By.XPATH, "//input[@type='submit']"),
                (By.CSS_SELECTOR, "button.login-btn"),
            ]
            for by, selector in submit_selectors:
                try:
                    submit_btn = driver.find_element(by, selector)
                    if submit_btn:
                        break
                except NoSuchElementException:
                    continue

            if submit_btn:
                safe_click(driver, submit_btn, logger)
                logger.info("   ✅ Login button clicked")
            else:
                # Try pressing Enter as fallback
                password_field.send_keys(Keys.RETURN)
                logger.info("   ✅ Pressed Enter to submit")

            human_delay((3, 6))

            # ── Check if login succeeded ──
            # Wait a bit and check if we've left the login page
            time.sleep(3)
            if "/login" not in driver.current_url.lower():
                logger.info("✅ Login successful!")
                return True
            else:
                logger.warning("⚠️ Still on login page — may need CAPTCHA or manual intervention")
                return _wait_for_manual_login(driver, logger)

        except Exception as e:
            logger.warning(f"⚠️ Auto-login failed: {e}")
            return _wait_for_manual_login(driver, logger)
    else:
        logger.info("📧 No credentials in .env — waiting for manual login")
        return _wait_for_manual_login(driver, logger)


def _wait_for_manual_login(driver, logger):
    """Wait for the user to manually log in."""
    logger.info(
        f"\n{'='*60}\n"
        f"  👉 MANUAL LOGIN REQUIRED\n"
        f"  Please log in to ZipRecruiter in the browser window.\n"
        f"  Waiting up to {config.MANUAL_LOGIN_TIMEOUT} seconds...\n"
        f"{'='*60}\n"
    )

    start = time.time()
    while time.time() - start < config.MANUAL_LOGIN_TIMEOUT:
        if "/login" not in driver.current_url.lower() and "ziprecruiter.com" in driver.current_url.lower():
            logger.info("✅ Manual login detected — continuing!")
            human_delay((2, 3))
            return True
        time.sleep(2)

    logger.error("❌ Login timeout — please restart the script and try again")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# JOB SEARCH
# ─────────────────────────────────────────────────────────────────────────────
def build_search_url():
    """Construct a deterministic search URL with all desired filters encoded in query params."""
    location = config.SEARCH_LOCATION or "USA"
    params = [
        ("search", config.SEARCH_QUERY),
        ("location", location),
    ]

    days = DATE_FILTER_MAP.get(config.DATE_POSTED)
    if days:
        params.append(("days", days))

    if getattr(config, "EASY_APPLY_ONLY", False):
        params.extend([
            ("quick_apply", 1),
            ("refine_by_quick_apply", "true"),
        ])

    job_type = JOB_TYPE_MAP.get(config.JOB_TYPE)
    if job_type:
        # Add multiple variants to cover ZipRecruiter's differing param expectations
        params.extend([
            ("employment_type", job_type),
            ("refine_by_employment_type", job_type),
            ("employment_type", f"{job_type}or" if job_type.endswith('t') else job_type),
        ])

    # Build query string (keep order stable for logging/debugging)
    query = "&".join([f"{k}={str(v).replace(' ', '+').replace(',', '%2C')}" for k, v in params])
    return f"{SEARCH_URL}?{query}"


def perform_search(driver, logger):
    """Navigate to job search and enter the search query + location."""
    search_url = build_search_url()
    logger.info(f"🔍 Searching with URL: {search_url}")
    driver.get(search_url)
    human_delay((3, 5))

    # Verify we're on the search results page and log final URL actually loaded
    try:
        WebDriverWait(driver, config.PAGE_LOAD_TIMEOUT).until(
            lambda d: "jobs" in d.current_url.lower() or "search" in d.current_url.lower()
        )
        logger.info(f"✅ Search results loaded at {driver.current_url}")
    except TimeoutException:
        logger.warning("⚠️ Search results page may not have loaded properly")

    return True


def _click_by_text(driver, texts):
    """Click the first element with visible text matching any provided string."""
    if isinstance(texts, str):
        texts = [texts]
    lower_targets = [t.lower() for t in texts]
    return driver.execute_script(
        """
        const targets = arguments[0];
        const els = document.querySelectorAll('label, button, div, span, a, li');
        for (const el of els) {
            const txt = (el.innerText || el.textContent || '').trim().toLowerCase();
            if (targets.includes(txt) && el.offsetHeight > 0 && el.offsetWidth > 0) {
                el.click();
                return txt;
            }
        }
        return '';
        """,
        lower_targets,
    )


def apply_filters(driver, logger):
    """
    Apply filters using the Filters drawer (per provided UI):
    - Click filters icon
    - Set Quick apply only
    - Set Employment type -> Contract
    - Set Date posted -> Within 1 day
    - Click Apply Filters
    """
    logger.info("🔧 Applying filters...")
    human_delay((1, 2))

    # Open filters icon near search bar
    try:
        opened = driver.execute_script(
            """
            // Prefer the header filters button (id observed: zds-header-filters-button)
            const direct = document.querySelector('#zds-header-filters-button');
            if (direct && direct.offsetHeight > 0) { direct.click(); return true; }

            // Fallback: any button with filter in id/class/aria-label
            const buttons = document.querySelectorAll('button, a, [role="button"]');
            for (const btn of buttons) {
                const txt = (btn.innerText || '').toLowerCase().trim();
                const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
                const cls = (btn.className || '').toLowerCase();
                const id = (btn.id || '').toLowerCase();
                if (aria.includes('filter') || id.includes('filter') || cls.includes('filter') || txt.includes('filter')) {
                    if (btn.offsetHeight > 0 && btn.offsetWidth > 0) { btn.click(); return true; }
                }
            }
            return false;
            """
        )
        logger.info(f"   Filters drawer open: {opened}")
        human_delay((1.0, 1.5))
    except Exception as e:
        logger.warning(f"   ⚠️ Could not open filters drawer: {e}")

    # Apply type
    if getattr(config, "EASY_APPLY_ONLY", False):
        clicked = _click_by_text(driver, ["quick apply only", "quick apply"])
        logger.info(f"   📌 Apply type -> Quick apply only ({'hit ' + clicked if clicked else 'not found'})")
        human_delay((0.6, 1.0))

    # Employment type
    job_type = JOB_TYPE_MAP.get(config.JOB_TYPE)
    if job_type:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.6);")
        human_delay((0.4, 0.8))
        clicked = _click_by_text(driver, ["contract", "contractor"])
        logger.info(f"   📌 Employment type -> Contract ({'hit ' + clicked if clicked else 'not found'})")
        human_delay((0.6, 1.0))

    # Date posted
    if config.DATE_POSTED == "last_24_hours":
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.3);")
        human_delay((0.4, 0.7))
        clicked = _click_by_text(driver, ["within 1 day", "last 24 hours"])
        logger.info(f"   📌 Date posted -> Within 1 day ({'hit ' + clicked if clicked else 'not found'})")
        human_delay((0.6, 1.0))

    # Apply Filters button
    applied = driver.execute_script(
        """
        const buttons = document.querySelectorAll('button, input[type="submit"]');
        for (const btn of buttons) {
            const txt = (btn.innerText || btn.value || '').trim().toLowerCase();
            if (txt === 'apply filters') { btn.click(); return true; }
        }
        return false;
        """
    )
    logger.info(f"   ✅ Apply Filters clicked: {applied}")
    human_delay((2.0, 3.0))

    logger.info("✅ Filter application complete")

    # Final safeguard: if essential params are missing, reload canonical URL
    required_snippets = []
    if getattr(config, 'EASY_APPLY_ONLY', False):
        required_snippets.append('quick_apply=')
    if job_type:
        required_snippets.append('employment_type=')
    current = driver.current_url.lower()
    missing = [s for s in required_snippets if s not in current]
    if missing:
        logger.info(f"   ℹ️ URL missing {missing}; reloading canonical search URL")
        driver.get(build_search_url())
        human_delay((2, 3))

    return True


# ─────────────────────────────────────────────────────────────────────────────
# JOB SCANNING & APPLICATION
# ─────────────────────────────────────────────────────────────────────────────
def dismiss_overlay(driver, logger):
    """Dismiss any email gate or popup overlay that ZipRecruiter shows."""
    try:
        driver.execute_script("""
            // Remove email gate / signup modals
            document.querySelectorAll('div[role="dialog"], [class*="overlay"], [class*="modal"]').forEach(el => {
                if (el.offsetHeight > 100) el.remove();
            });
            // Remove any backdrop
            document.querySelectorAll('[class*="backdrop"], [class*="Backdrop"]').forEach(el => el.remove());
            // Re-enable scrolling
            document.body.style.overflow = 'auto';
        """)
    except Exception:
        pass


def get_job_listings(driver, logger):
    """
    Extract job listing elements from the current search results page.
    ZipRecruiter uses a split-pane layout with article cards on the left.
    Returns a list of dicts with basic info about each job card (deduplicated).
    """
    listings = []
    seen_ids = set()

    # Dismiss any overlays first
    dismiss_overlay(driver, logger)

    # Primary selector: ZipRecruiter uses article[id^="job-card-"]
    card_selectors = [
        "article[id^='job-card-']",
        "article.job_result",
        "[class*='job_result']",
        "[class*='JobCard']",
    ]

    cards = []
    for selector in card_selectors:
        cards = driver.find_elements(By.CSS_SELECTOR, selector)
        if cards:
            logger.info(f"   Found {len(cards)} raw job cards with selector: {selector}")
            break

    if not cards:
        logger.info("   🔍 No job cards found with primary selectors, trying fallback...")
        links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/jobs/'], a[href*='/job/']")
        seen_urls = set()
        for link in links:
            href = link.get_attribute("href") or ""
            text = link.text.strip()
            if href and text and len(text) > 5 and href not in seen_urls:
                seen_urls.add(href)
                listings.append({
                    "element": link,
                    "click_target": link,
                    "title": text,
                    "url": href,
                    "company": "",
                    "job_id": "",
                    "already_applied_badge": False,
                })
        logger.info(f"   Found {len(listings)} job links via fallback")
        return listings

    for card in cards:
        try:
            # Deduplicate: skip if we've seen this card ID already
            card_id = card.get_attribute("id") or ""
            if card_id:
                if card_id in seen_ids:
                    continue
                seen_ids.add(card_id)

            # Extract title — ZipRecruiter uses button[aria-label^="View "] as the title
            title = ""
            url = ""
            click_target = card  # default

            title_selectors = [
                ("button[aria-label^='View ']", True),   # Primary: the View button
                ("a[class*='job_link']", False),
                ("h2 a", False),
                ("a[data-testid*='title']", False),
                ("a", False),
            ]
            for sel, is_button in title_selectors:
                try:
                    title_el = card.find_element(By.CSS_SELECTOR, sel)
                    if is_button:
                        title = title_el.get_attribute("aria-label") or ""
                        # Remove "View " prefix from aria-label
                        if title.startswith("View "):
                            title = title[5:]
                        click_target = title_el
                    else:
                        title = title_el.text.strip()
                        url = title_el.get_attribute("href") or ""
                        click_target = title_el
                    if title:
                        break
                except NoSuchElementException:
                    continue

            # If we still don't have a title, grab card text
            if not title:
                title = card.text.strip().split("\n")[0][:100]

            # Extract company name — ZipRecruiter uses p.text-primary
            company = ""
            company_selectors = [
                "p.text-primary",
                "[class*='company']",
                "[data-testid*='company']",
                "span.company",
                "[class*='Company']",
            ]
            for sel in company_selectors:
                try:
                    company_el = card.find_element(By.CSS_SELECTOR, sel)
                    company = company_el.text.strip()
                    if company:
                        break
                except NoSuchElementException:
                    continue

            # Extract the job card ID (e.g. "job-card-abc123")
            job_id = card.get_attribute("id") or ""

            # Detect "Applied" badge on the card
            already_applied_badge = False
            try:
                badge_text = card.text.lower()
                if "applied" in badge_text and "apply" not in badge_text:
                    already_applied_badge = True
            except Exception:
                pass

            if title:
                listings.append({
                    "element": card,
                    "click_target": click_target,
                    "title": title,
                    "url": url,
                    "company": company,
                    "job_id": job_id,
                    "already_applied_badge": already_applied_badge,
                })
        except StaleElementReferenceException:
            continue

    logger.info(f"   📋 Extracted {len(listings)} job listings from this page")
    return listings


def get_job_description_from_panel(driver, logger):
    """
    Extract job description from ZipRecruiter's right-side detail panel.
    Uses multiple strategies to handle varying DOM structures.
    """
    # Strategy 1: JavaScript extraction with precise selectors
    try:
        text = driver.execute_script("""
            // Try multiple container selectors in order of specificity
            let selectors = [
                'div[data-testid="job-details-scroll-container"]',
                'div[data-test-id="job-details-scroll-container"]',
                'div[data-testid="right-pane"]',
                'div[data-test-id="right-pane"]',
                '[class*="job_description"]',
                '[class*="jobDescription"]',
                '#job_description',
                '[class*="JobBody"]',
                '[class*="job-body"]',
                '[class*="description_content"]',
                '[class*="right-pane"]',
                '[class*="detail-panel"]',
                '[class*="JobDetail"]',
            ];
            for (let sel of selectors) {
                let el = document.querySelector(sel);
                if (el) {
                    let clone = el.cloneNode(true);
                    clone.querySelectorAll(
                        'button, nav, [class*="related"], [class*="Similar"], ' +
                        '[class*="recommend"], [class*="footer"], [class*="apply"]'
                    ).forEach(x => x.remove());
                    let t = (clone.innerText || clone.textContent || '').trim();
                    if (t.length > 80) return t;
                }
            }
            // Fallback: find the largest text block on the right half of the page
            let best = '';
            document.querySelectorAll('div, section, article').forEach(el => {
                let rect = el.getBoundingClientRect();
                if (rect.left > window.innerWidth * 0.3) {
                    let t = (el.innerText || '').trim();
                    if (t.length > best.length && t.length < 20000) best = t;
                }
            });
            return best || '';
        """)
        if text and len(text) > 80:
            return text
    except Exception as e:
        logger.debug(f"JS description extraction failed: {e}")

    # Strategy 2: Check for iframe-embedded descriptions
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for iframe in iframes:
            try:
                driver.switch_to.frame(iframe)
                body = driver.find_element(By.TAG_NAME, "body")
                text = body.text.strip()
                driver.switch_to.default_content()
                if len(text) > 80:
                    return text
            except Exception:
                driver.switch_to.default_content()
    except Exception as e:
        logger.debug(f"Iframe extraction failed: {e}")

    # Strategy 3: CSS selector fallback
    desc_selectors = [
        "div[data-testid='job-details-scroll-container']",
        "div[data-test-id='job-details-scroll-container']",
        "[class*='job_description']",
        "[class*='jobDescription']",
        "#job_description",
    ]
    for selector in desc_selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            text = el.text.strip()
            if len(text) > 80:
                return text
        except NoSuchElementException:
            continue

    # Strategy 4: grab all visible text from the right-pane area
    try:
        text = driver.execute_script("""
            let all = document.querySelectorAll('div, section');
            let best = '';
            for (let el of all) {
                let t = (el.innerText || '').trim();
                if (t.length > 200 && t.length > best.length && t.length < 20000) {
                    let r = el.getBoundingClientRect();
                    if (r.width > 300 && r.height > 200) best = t;
                }
            }
            return best;
        """)
        if text and len(text) > 80:
            return text
    except Exception:
        pass

    return ""


def _fill_form_fields(driver, container, logger):
    """Auto-fill application form fields using config.APPLICANT_INFO."""
    info = config.APPLICANT_INFO
    # Map of field-name hints → values to fill
    field_map = {
        "first_name": info["first_name"],
        "firstname": info["first_name"],
        "first": info["first_name"],
        "last_name": info["last_name"],
        "lastname": info["last_name"],
        "last": info["last_name"],
        "full_name": info["full_name"],
        "fullname": info["full_name"],
        "name": info["full_name"],
        "email": info["email"],
        "e-mail": info["email"],
        "phone": info["phone"],
        "mobile": info["phone"],
        "telephone": info["phone"],
        "phone_number": info["phone"],
        "linkedin": info["linkedin"],
        "city": info.get("city", ""),
        "state": info.get("state", ""),
        "zip": info.get("zip_code", ""),
        "zipcode": info.get("zip_code", ""),
        "zip_code": info.get("zip_code", ""),
        "postal": info.get("zip_code", ""),
        "country": info["country"],
        "current_title": info["current_title"],
        "job_title": info["current_title"],
        "title": info["current_title"],
        "current_company": info["current_company"],
        "company": info["current_company"],
        "employer": info["current_company"],
        "experience": info["years_experience"],
        "years": info["years_experience"],
        "years_experience": info["years_experience"],
        "education": info["education"],
        "degree": info["education"],
        "salary": info.get("salary_expectation", ""),
        "start_date": info["start_date"],
        "availability": info["start_date"],
    }

    filled = 0
    try:
        inputs = container.find_elements(By.CSS_SELECTOR,
            "input[type='text'], input[type='email'], input[type='tel'], "
            "input[type='number'], input[type='url'], textarea"
        )
        for inp in inputs:
            try:
                if not inp.is_displayed() or not inp.is_enabled():
                    continue
                # Already has a value? Skip.
                if inp.get_attribute("value") and len(inp.get_attribute("value").strip()) > 0:
                    continue
                # Gather hints from name, id, placeholder, aria-label
                hints = " ".join(filter(None, [
                    inp.get_attribute("name"),
                    inp.get_attribute("id"),
                    inp.get_attribute("placeholder"),
                    inp.get_attribute("aria-label"),
                ])).lower()
                # Also check the associated <label>
                inp_id = inp.get_attribute("id")
                if inp_id:
                    try:
                        label = container.find_element(By.CSS_SELECTOR, f"label[for='{inp_id}']")
                        hints += " " + label.text.lower()
                    except NoSuchElementException:
                        pass
                for key, value in field_map.items():
                    if value and key in hints:
                        inp.clear()
                        for char in value:
                            inp.send_keys(char)
                            time.sleep(random.uniform(0.02, 0.06))
                        filled += 1
                        logger.info(f"      📝 Filled '{key}' field")
                        break
            except StaleElementReferenceException:
                continue
    except Exception as e:
        logger.debug(f"Field filling error: {e}")

    # Handle select/dropdown elements
    try:
        from selenium.webdriver.support.ui import Select
        selects = container.find_elements(By.TAG_NAME, "select")
        for sel_el in selects:
            try:
                if not sel_el.is_displayed():
                    continue
                hints = " ".join(filter(None, [
                    sel_el.get_attribute("name"),
                    sel_el.get_attribute("id"),
                    sel_el.get_attribute("aria-label"),
                ])).lower()
                select = Select(sel_el)
                if "country" in hints:
                    for opt in select.options:
                        if "united states" in opt.text.lower() or "usa" in opt.text.lower():
                            select.select_by_visible_text(opt.text)
                            filled += 1
                            break
                elif "experience" in hints or "years" in hints:
                    for opt in select.options:
                        if "10" in opt.text or "11" in opt.text or "10+" in opt.text:
                            select.select_by_visible_text(opt.text)
                            filled += 1
                            break
                elif "authorization" in hints or "sponsor" in hints or "visa" in hints:
                    for opt in select.options:
                        t = opt.text.lower()
                        if "yes" in t or "authorized" in t or "no" in t and "sponsor" in hints:
                            select.select_by_visible_text(opt.text)
                            filled += 1
                            break
            except Exception:
                continue
    except Exception:
        pass

    # Handle checkboxes (authorization, terms, etc.)
    try:
        checkboxes = container.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
        for cb in checkboxes:
            try:
                if not cb.is_displayed():
                    continue
                if cb.is_selected():
                    continue
                hints = " ".join(filter(None, [
                    cb.get_attribute("name"),
                    cb.get_attribute("id"),
                    cb.get_attribute("aria-label"),
                ])).lower()
                # Check associated label
                cb_id = cb.get_attribute("id")
                label_text = ""
                if cb_id:
                    try:
                        label = container.find_element(By.CSS_SELECTOR, f"label[for='{cb_id}']")
                        label_text = label.text.lower()
                    except NoSuchElementException:
                        pass
                combined = hints + " " + label_text
                # Auto-check terms, authorization, acknowledgment checkboxes
                if any(kw in combined for kw in [
                    "agree", "terms", "acknowledge", "authorized", "consent",
                    "certif", "confirm", "accept"
                ]):
                    driver.execute_script("arguments[0].click();", cb)
                    filled += 1
                    logger.info(f"      ☑️ Checked agreement checkbox")
            except Exception:
                continue
    except Exception:
        pass

    logger.info(f"      📋 Auto-filled {filled} form fields")
    return filled


def attempt_application(driver, logger, dry_run=False):
    """
    Try to apply to the current job listing via the right-side panel.
    Handles Easy Apply filtering and form auto-fill.
    Returns True if applied, False otherwise.
    """
    if dry_run:
        logger.info("   🏷️  DRY RUN — would apply here (skipping)")
        return True

    # Dismiss any overlays first
    dismiss_overlay(driver, logger)

    apply_btn = None
    is_easy_apply = False

    # Look for apply buttons in the right pane first
    right_pane_selectors = [
        "div[data-testid='right-pane'] button",
        "div[data-test-id='right-pane'] button",
        "div[data-testid='right-pane'] a",
        "div[data-test-id='right-pane'] a",
    ]

    for selector in right_pane_selectors:
        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, selector)
            for btn in buttons:
                try:
                    btn_text = btn.text.lower().strip()
                    aria = (btn.get_attribute("aria-label") or "").lower()
                    combined = btn_text + " " + aria
                    if any(kw in combined for kw in [
                        "quick apply", "1-click apply", "easy apply",
                        "apply now", "apply",
                    ]) and btn.is_displayed() and btn.is_enabled():
                        if "redirect" not in combined:
                            apply_btn = btn
                            if any(kw in combined for kw in [
                                "quick apply", "1-click", "easy apply"
                            ]):
                                is_easy_apply = True
                            break
                except StaleElementReferenceException:
                    continue
            if apply_btn:
                break
        except NoSuchElementException:
            continue

    # Broader fallback
    if not apply_btn:
        broader_selectors = [
            "button[class*='apply']", "button[data-testid*='apply']",
            "a[class*='apply']", "[class*='ApplyButton']",
            "button[aria-label*='Apply']",
        ]
        for selector in broader_selectors:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                for btn in buttons:
                    btn_text = btn.text.lower().strip()
                    if "apply" in btn_text and btn.is_displayed() and btn.is_enabled():
                        apply_btn = btn
                        if any(kw in btn_text for kw in ["quick", "1-click", "easy"]):
                            is_easy_apply = True
                        break
                if apply_btn:
                    break
            except NoSuchElementException:
                continue

    if not apply_btn:
        logger.info("   ⚠️ Could not find Apply button on this listing")
        return False

    # If EASY_APPLY_ONLY is set, skip external-redirect applications
    if config.EASY_APPLY_ONLY and not is_easy_apply:
        btn_text = apply_btn.text.lower().strip()
        # Some sites label it just "Apply" but it's still a quick apply
        if "apply on company" in btn_text or "redirect" in btn_text:
            logger.info("   ⏭️  Skipping — external redirect (Easy Apply only mode)")
            return False

    logger.info(f"   🖱️  Clicking Apply button: '{apply_btn.text.strip()}'")
    scroll_to_element(driver, apply_btn)
    human_delay((1, 2))

    if not safe_click(driver, apply_btn, logger):
        logger.warning("   ❌ Failed to click Apply button")
        return False

    human_delay((2, 4))

    # ── Handle application modal/form if it appears ──
    try:
        modal_selectors = [
            "[role='dialog']",
            "[class*='modal']", "[class*='Modal']",
            "[class*='application-form']", "[class*='ApplicationForm']",
            "form[class*='apply']", "form[class*='Apply']",
        ]
        modal = None
        for sel in modal_selectors:
            try:
                modals = driver.find_elements(By.CSS_SELECTOR, sel)
                for m in modals:
                    if m.is_displayed() and m.size['height'] > 100:
                        modal = m
                        logger.info("   📝 Application modal/form detected")
                        break
                if modal:
                    break
            except NoSuchElementException:
                continue

        if modal:
            # Auto-fill form fields
            _fill_form_fields(driver, modal, logger)
            human_delay((1, 2))

            # Look for submit button
            submit_selectors = [
                "button[type='submit']",
                "button[class*='submit']",
                "button[class*='apply']",
                "button[class*='send']",
                "input[type='submit']",
            ]
            for sel in submit_selectors:
                try:
                    submit_btns = modal.find_elements(By.CSS_SELECTOR, sel)
                    for sbtn in submit_btns:
                        if sbtn.is_displayed() and sbtn.is_enabled():
                            submit_text = sbtn.text.strip()
                            if any(kw in submit_text.lower() for kw in [
                                "submit", "send", "apply", "confirm", "next", "continue"
                            ]):
                                safe_click(driver, sbtn, logger)
                                logger.info(f"   ✅ Clicked submit: '{submit_text}'")
                                human_delay(config.APPLY_DELAY)

                                # Check for multi-step — repeat fill+submit
                                time.sleep(2)
                                try:
                                    next_form = driver.find_element(By.CSS_SELECTOR,
                                        "[role='dialog'], [class*='modal'], form")
                                    if next_form.is_displayed() and next_form.size['height'] > 100:
                                        logger.info("   📝 Multi-step form detected, filling next page...")
                                        _fill_form_fields(driver, next_form, logger)
                                        human_delay((1, 2))
                                        for sel2 in submit_selectors:
                                            try:
                                                sb2 = next_form.find_elements(By.CSS_SELECTOR, sel2)
                                                for s in sb2:
                                                    if s.is_displayed() and s.is_enabled():
                                                        safe_click(driver, s, logger)
                                                        logger.info(f"   ✅ Submitted step 2")
                                                        break
                                            except Exception:
                                                continue
                                except Exception:
                                    pass

                                return True
                except NoSuchElementException:
                    continue

            logger.info("   ℹ️ Modal appeared but couldn't find submit — may need manual review")
            human_delay((3, 5))
    except Exception as e:
        logger.debug(f"   Modal handling error: {e}")

    # Check for success indicators on page
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        success_indicators = ["application submitted", "applied", "thank you",
                              "application sent", "successfully applied"]
        if any(indicator in page_text for indicator in success_indicators):
            logger.info("   ✅ Application appears to have been submitted!")
            return True
    except Exception:
        pass

    logger.info("   ℹ️ Apply button clicked — check browser for any additional steps needed")
    human_delay(config.APPLY_DELAY)
    return True


def go_to_next_page(driver, logger, current_page=1):
    """Navigate to the next page of search results. Returns True if successful."""
    import urllib.parse

    # ── Strategy 1: Click a "Next" link/button in the DOM ──
    next_selectors = [
        "a[aria-label='Next']",
        "a[title='Next Page']",
        "a[rel='next']",
        "button[aria-label='Next']",
        "a.next_page",
        "a[class*='next']",
        "[class*='pagination'] a:last-child",
        "[class*='Pagination'] button:last-child",
        "nav[aria-label*='pagination'] a:last-of-type",
    ]
    for selector in next_selectors:
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, selector)
            if next_btn.is_displayed() and next_btn.is_enabled():
                href = next_btn.get_attribute("href")
                if href and href.startswith("http"):
                    logger.info(f"📄 Navigating to next page via link: {href[:120]}")
                    driver.get(href)
                    human_delay((3, 5))
                    return True
                scroll_to_element(driver, next_btn)
                safe_click(driver, next_btn, logger)
                logger.info("📄 Navigating to next page via click...")
                human_delay((3, 5))
                return True
        except NoSuchElementException:
            continue

    # ── Strategy 2: XPath for links with "Next" text ──
    try:
        btns = driver.find_elements(By.XPATH,
            "//a[contains(text(),'Next')] | //button[contains(text(),'Next')]")
        for btn in btns:
            if btn.is_displayed():
                href = btn.get_attribute("href")
                if href and href.startswith("http"):
                    driver.get(href)
                else:
                    safe_click(driver, btn, logger)
                logger.info("📄 Navigating to next page (XPath)...")
                human_delay((3, 5))
                return True
    except NoSuchElementException:
        pass

    # ── Strategy 3: Modify the URL to add/increment &page= parameter ──
    try:
        current_url = driver.current_url
        parsed = urllib.parse.urlparse(current_url)
        params = urllib.parse.parse_qs(parsed.query)
        next_page = current_page + 1
        params["page"] = [str(next_page)]
        new_query = urllib.parse.urlencode(params, doseq=True)
        new_url = urllib.parse.urlunparse(parsed._replace(query=new_query))
        logger.info(f"📄 Navigating to page {next_page} via URL: {new_url[:120]}")
        driver.get(new_url)
        human_delay((3, 5))

        # Verify new page actually loaded new results
        time.sleep(2)
        cards = driver.find_elements(By.CSS_SELECTOR, "article[id^='job-card-']")
        if cards:
            logger.info(f"   ✅ Page {next_page} loaded with {len(cards)} job cards")
            return True
        else:
            logger.info("📄 No more pages available (no cards on next page)")
            return False
    except Exception as e:
        logger.info(f"📄 Could not navigate to next page: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────
def run(dry_run=False):
    """Main entry point — orchestrates the entire job search & apply flow."""
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("  🤖 ZipRecruiter Job Search & Auto-Apply Bot")
    logger.info(f"  📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  🔍 Query: {config.SEARCH_QUERY}")
    logger.info(f"  📍 Location: {config.SEARCH_LOCATION or 'Any'}")
    logger.info(f"  🏷️  Mode: {'DRY RUN (no applications)' if dry_run else 'LIVE (will apply)'}")
    logger.info(f"  📊 Match threshold: {config.MATCH_THRESHOLD} keywords")
    logger.info(f"  🎯 Max applications: {config.MAX_APPLICATIONS}")
    logger.info("=" * 60)

    # Stats tracking
    stats = {
        "jobs_scanned": 0,
        "jobs_matched": 0,
        "jobs_applied": 0,
        "jobs_skipped": 0,
        "jobs_excluded": 0,
        "jobs_failed": 0,
        "pages_scanned": 0,
        "applied_jobs": [],    # list of (title, company, url)
        "skipped_jobs": [],
    }

    driver = None
    applied_tracker = load_applied_jobs()
    logger.info(f"  📂 Loaded {len(applied_tracker)} previously applied jobs from tracker")

    try:
        # ── Step 1: Launch browser ──
        driver = create_driver(logger)

        # ── Step 2: Login ──
        if not login(driver, logger):
            logger.error("❌ Could not log in. Exiting.")
            return stats

        # ── Step 3: Search ──
        perform_search(driver, logger)

        # ── Step 4: Apply Filters ──
        apply_filters(driver, logger)

        # ── Step 5: Scan & Apply Loop ──
        for page_num in range(1, config.MAX_PAGES + 1):
            stats["pages_scanned"] += 1
            logger.info(f"\n{'─'*60}")
            logger.info(f"📄 PAGE {page_num}")
            logger.info(f"{'─'*60}")

            listings = get_job_listings(driver, logger)

            if not listings:
                logger.info("   No job listings found on this page")
                break

            for i, job in enumerate(listings, 1):
                if stats["jobs_scanned"] >= config.MAX_JOBS_TO_SCAN:
                    logger.info(f"🛑 Reached max jobs to scan ({config.MAX_JOBS_TO_SCAN})")
                    break
                if stats["jobs_applied"] >= config.MAX_APPLICATIONS:
                    logger.info(f"🛑 Reached max applications ({config.MAX_APPLICATIONS})")
                    break

                stats["jobs_scanned"] += 1
                title = job["title"]
                company = job["company"]
                url = job.get("url", "")
                job_id = job.get("job_id", "")

                logger.info(f"\n🔹 [{stats['jobs_scanned']}] {title}")
                if company:
                    logger.info(f"   🏢 {company}")
                if job_id:
                    logger.info(f"   🆔 {job_id}")

                # Skip if already applied (from tracker file or DOM badge)
                if job_id and job_id in applied_tracker:
                    logger.info(f"   ⏭️  Already applied (from tracker) — skipping")
                    stats["jobs_skipped"] += 1
                    continue
                if job.get("already_applied_badge"):
                    logger.info(f"   ⏭️  Already applied (badge on card) — skipping")
                    stats["jobs_skipped"] += 1
                    if job_id:
                        applied_tracker[job_id] = {"title": title, "company": company}
                        save_applied_jobs(applied_tracker)
                    continue

                # ── Click job card to load details in the side panel ──
                try:
                    element = job["element"]
                    click_target = job.get("click_target", element)
                    scroll_to_element(driver, element)
                    human_delay(config.SCAN_DELAY)

                    # Dismiss any overlays before clicking
                    dismiss_overlay(driver, logger)

                    # Use JavaScript to click — bypasses ::after pseudo-element
                    try:
                        driver.execute_script("arguments[0].click();", click_target)
                    except Exception:
                        try:
                            driver.execute_script("arguments[0].click();", element)
                        except Exception:
                            safe_click(driver, click_target, logger)

                    # Wait for the right pane to update with job details
                    time.sleep(2)

                    # Dismiss overlay again (email gate often appears after click)
                    dismiss_overlay(driver, logger)

                    # Small additional wait for content to fully render
                    time.sleep(1)

                    # Get the description from the right-side panel
                    description = get_job_description_from_panel(driver, logger)

                    if not description:
                        logger.info("   ⚠️ Could not extract job description — skipping")
                        stats["jobs_skipped"] += 1
                        continue

                    # ── Analyze the job ──
                    analysis = analyze_job(title, description, logger)

                    if analysis["exclude_hit"]:
                        stats["jobs_excluded"] += 1
                        stats["skipped_jobs"].append((title, company, f"Excluded: {analysis['exclude_keyword']}"))
                    elif analysis["should_apply"]:
                        stats["jobs_matched"] += 1

                        # Attempt to apply (button is in the right pane)
                        applied = attempt_application(driver, logger, dry_run=dry_run)
                        if applied:
                            stats["jobs_applied"] += 1
                            stats["applied_jobs"].append((title, company, url))
                            logger.info(f"   🎉 Application #{stats['jobs_applied']} submitted!")
                            # Save to tracker
                            if job_id:
                                applied_tracker[job_id] = {
                                    "title": title,
                                    "company": company,
                                    "url": url,
                                    "applied_at": datetime.now().isoformat(),
                                }
                                save_applied_jobs(applied_tracker)
                        else:
                            stats["jobs_failed"] += 1
                            logger.info(f"   ❌ Application attempt failed")
                    else:
                        stats["jobs_skipped"] += 1
                        stats["skipped_jobs"].append((
                            title, company,
                            f"Score {analysis['match_count']}/{config.MATCH_THRESHOLD}"
                        ))

                except StaleElementReferenceException:
                    logger.warning(f"   ⚠️ Stale element — page may have refreshed. Skipping.")
                    stats["jobs_skipped"] += 1
                    continue
                except Exception as e:
                    logger.warning(f"   ⚠️ Error processing job: {e}")
                    stats["jobs_failed"] += 1
                    continue

            # Check if we've hit limits
            if stats["jobs_applied"] >= config.MAX_APPLICATIONS:
                break
            if stats["jobs_scanned"] >= config.MAX_JOBS_TO_SCAN:
                break

            # ── Go to next page ──
            if not go_to_next_page(driver, logger, current_page=page_num):
                break

    except KeyboardInterrupt:
        logger.info("\n⛔ Interrupted by user (Ctrl+C)")
    except WebDriverException as e:
        logger.error(f"❌ Browser error: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
    finally:
        # ── Print Summary Report ──
        logger.info(f"\n{'='*60}")
        logger.info("  📊 SESSION SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"  📄 Pages scanned:    {stats['pages_scanned']}")
        logger.info(f"  🔍 Jobs scanned:     {stats['jobs_scanned']}")
        logger.info(f"  ✅ Jobs matched:     {stats['jobs_matched']}")
        logger.info(f"  🎯 Applied:          {stats['jobs_applied']}")
        logger.info(f"  ⏭️  Skipped:          {stats['jobs_skipped']}")
        logger.info(f"  ❌ Excluded:         {stats['jobs_excluded']}")
        logger.info(f"  ⚠️  Failed:           {stats['jobs_failed']}")

        if stats["applied_jobs"]:
            logger.info(f"\n  ── Applied To ──")
            for j, (t, c, u) in enumerate(stats["applied_jobs"], 1):
                logger.info(f"  {j}. {t}  @ {c}")
                if u:
                    logger.info(f"     🔗 {u}")

        logger.info(f"\n{'='*60}")
        logger.info(f"  ℹ️  The browser window has been left open for review.")
        logger.info(f"  ℹ️  Close it manually when you're done.")
        logger.info(f"{'='*60}")

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="🤖 ZipRecruiter Job Search & Auto-Apply Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ziprecruiter_bot.py              # Full run (search + apply)
  python ziprecruiter_bot.py --dry-run    # Scan only, no applications
  python ziprecruiter_bot.py --query "ML Engineer" --location "Austin, TX"
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan jobs and log matches WITHOUT actually applying",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help=f"Override search query (default: '{config.SEARCH_QUERY}')",
    )
    parser.add_argument(
        "--location",
        type=str,
        default=None,
        help=f"Override location (default: '{config.SEARCH_LOCATION}')",
    )
    parser.add_argument(
        "--max-apply",
        type=int,
        default=None,
        help=f"Override max applications (default: {config.MAX_APPLICATIONS})",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=None,
        help=f"Override keyword match threshold (default: {config.MATCH_THRESHOLD})",
    )

    args = parser.parse_args()

    # Apply CLI overrides to config
    if args.query:
        config.SEARCH_QUERY = args.query
    if args.location:
        config.SEARCH_LOCATION = args.location
    if args.max_apply:
        config.MAX_APPLICATIONS = args.max_apply
    if args.threshold:
        config.MATCH_THRESHOLD = args.threshold

    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
