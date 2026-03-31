import os
import csv
import time
import random
import re
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright

# =====================================================
# LOAD CREDENTIALS
# =====================================================

def load_credentials(csv_path="passwords.csv"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, csv_path)

    if not os.path.exists(path):
        raise FileNotFoundError("passwords.csv not found.")

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    return rows[0]["email"].strip(), rows[0]["password"].strip()

EMAIL, PASSWORD = load_credentials()

# =====================================================
# MODE
# =====================================================

AUTO_MODE = True

# =====================================================
# USER CONFIG
# =====================================================

JOB_KEYWORD = "Data Engineer"
LOCATION = "United States"

if AUTO_MODE:
    MAX_APPLICATIONS = 45
else:
    try:
        MAX_APPLICATIONS = int(input("Enter number of applications to submit: ").strip())
    except:
        MAX_APPLICATIONS = 1

if AUTO_MODE:
    POSTED_FILTER = "ONE"
else:
    print("\nSelect Posted Date Filter:")
    print("1 → Last 1 Day")
    print("3 → Last 3 Days")
    filter_input = input("Enter 1 / 3 : ").strip()
    POSTED_FILTER = "ONE" if filter_input == "1" else "THREE"

if AUTO_MODE:
    EMPLOYMENT_FILTER = ["CONTRACTS"]
else:
    print("\nSelect Employment Type:")
    print("1 → All")
    print("2 → Contract Only")
    print("3 → Full Time Only")
    print("4 → Contract + Full Time")
    job_type_input = input("Enter 1 / 2 / 3 / 4 : ").strip()

    EMPLOYMENT_FILTER = []
    if job_type_input == "2":
        EMPLOYMENT_FILTER = ["CONTRACTS"]
    elif job_type_input == "3":
        EMPLOYMENT_FILTER = ["FULLTIME"]
    elif job_type_input == "4":
        EMPLOYMENT_FILTER = ["CONTRACTS", "FULLTIME"]

# =====================================================
# FILTER RULES
# =====================================================

REQUIRED_PATTERN = r"(data engineer|etl developer|etl engineer|databricks|snowflake|big data)"
EXCLUDED_PATTERN = r"\b(lead|manager|scientist|analyst|architect|modeler|F2F|face to face|w2 only)\b"

# =====================================================
# APPLIED JOB TRACKING (JOB ID BASED)
# =====================================================

APPLIED_JOBS_FILE = "applied_jobs.csv"

def load_applied_jobs():
    if not os.path.exists(APPLIED_JOBS_FILE):
        return set()

    with open(APPLIED_JOBS_FILE, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return set(row[0] for row in reader if row)

def save_applied_job(job_id, job_title, job_url):
    with open(APPLIED_JOBS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([job_id, job_title, job_url])

def extract_job_id(url):
    """
    Extract Dice job ID from URL
    Example:
    https://www.dice.com/job-detail/UUID-HERE
    """
    if not url:
        return None

    match = re.search(r'/job-detail/([a-zA-Z0-9\-]+)', url)
    return match.group(1) if match else None

# =====================================================
# HELPERS
# =====================================================

def human_delay(a=1.0, b=2.0):
    time.sleep(random.uniform(a, b))

def build_search_url(page_num=1):
    params = {
        "q": JOB_KEYWORD,
        "location": LOCATION,
        "filters.postedDate": POSTED_FILTER,
        "filters.easyApply": "true",
        "latitude": "38.7945952",
        "longitude": "-106.5348379",
        "countryCode": "US",
        "locationPrecision": "Country",
        "page": page_num
    }

    query_string = urlencode(params)
    base_url = "https://www.dice.com/jobs?" + query_string

    for emp in EMPLOYMENT_FILTER:
        base_url += f"&filters.employmentType={emp}"

    return base_url

def run_wizard(page):
    human_delay(2, 3)

    for _ in range(20):
        human_delay(1.2, 2.2)

        for text in ["Submit", "Review", "Next", "Continue"]:
            btn = page.locator(f"button:has-text('{text}')")
            if btn.count() > 0 and btn.first.is_enabled():
                btn.first.click()
                if text == "Submit":
                    human_delay(2, 3)
                    return True
                break
        else:
            return False

    return False

# =====================================================
# MAIN
# =====================================================

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("Opening login page...")
        page.goto("https://www.dice.com/dashboard/login")
        human_delay(2, 3)

        page.fill("input[type='email']", EMAIL)
        page.click("button[type='submit']")
        page.fill("input[type='password']", PASSWORD)
        page.click("button[type='submit']")

        page.wait_for_url("**dice.com/**")
        print("Login successful.")
        human_delay(3, 4)

        applications_done = 0
        applied_jobs = load_applied_jobs()
        page_num = 1

        while applications_done < MAX_APPLICATIONS:

            page.goto(build_search_url(page_num))
            human_delay(3, 4)

            job_cards = page.locator("div[data-testid='job-card']")
            total = job_cards.count()

            if total == 0:
                break

            for i in range(total):

                if applications_done >= MAX_APPLICATIONS:
                    break

                job_card = job_cards.nth(i)

                try:
                    title_locator = job_card.locator("a[data-testid='job-search-job-detail-link']")
                    job_title = title_locator.first.inner_text().strip()
                    job_url = title_locator.first.get_attribute("href")
                except:
                    continue

                job_id = extract_job_id(job_url)

                if not job_id:
                    continue

                if job_id in applied_jobs:
                    print(f"Skipping already applied (ID match): {job_title}")
                    continue

                job_title_lower = job_title.lower()

                if not re.search(REQUIRED_PATTERN, job_title_lower):
                    continue

                if re.search(EXCLUDED_PATTERN, job_title_lower):
                    continue

                easy_apply_button = job_card.locator("a:has-text('Easy Apply')")
                if easy_apply_button.count() == 0:
                    continue

                if "Applied" in easy_apply_button.first.inner_text():
                    continue

                print(f"\nApplying to: {job_title}")

                try:
                    with context.expect_page(timeout=5000) as new_page_info:
                        easy_apply_button.first.click()

                    job_page = new_page_info.value
                    job_page.wait_for_load_state()
                    human_delay(2, 3)

                except:
                    continue

                detail_apply = job_page.locator("a[data-testid='apply-button']")
                if detail_apply.count() == 0:
                    job_page.close()
                    continue

                detail_apply.first.click()

                try:
                    job_page.wait_for_url("**/wizard", timeout=10000)
                except:
                    pass

                submitted = run_wizard(job_page)

                if submitted:
                    applications_done += 1
                    applied_jobs.add(job_id)
                    save_applied_job(job_id, job_title, job_url)
                    print(f"[APPLIED] {job_title} | Total: {applications_done}")

                job_page.close()
                human_delay(2, 3)

            page_num += 1

        print("\nFinished.")
        input("Press ENTER to close browser...")
        browser.close()

if __name__ == "__main__":
    main()
