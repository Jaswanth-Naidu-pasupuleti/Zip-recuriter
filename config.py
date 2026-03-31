"""
ZipRecruiter Automation — Configuration
========================================
Edit this file to customize your job search, filters, and matching criteria.
"""

# ──────────────────────────────────────────────────────────────────────────────
# SEARCH SETTINGS
# ──────────────────────────────────────────────────────────────────────────────

SEARCH_QUERY = "Data Engineer"

# Location: e.g. "Remote", "Dallas, TX", "New York, NY", "" for any
SEARCH_LOCATION = ""

# ──────────────────────────────────────────────────────────────────────────────
# FILTER SETTINGS
# ──────────────────────────────────────────────────────────────────────────────

# Date posted filter: "any", "last_24_hours", "last_3_days", "last_7_days", "last_14_days"
DATE_POSTED = "last_24_hours"

# Job type: "any", "full_time", "part_time", "contract", "temporary", "internship"
JOB_TYPE = "contract"

# Salary minimum (integer, annual). Set to 0 to skip salary filter.
SALARY_MIN = 0

# Remote preference: "any", "remote", "hybrid", "on_site"
REMOTE_PREFERENCE = "any"

# Distance in miles (only relevant for non-remote). Set to 0 to skip.
DISTANCE_MILES = 0

# Only apply to "Easy Apply" / "1-Click Apply" jobs (skips external redirects)
EASY_APPLY_ONLY = True

# ──────────────────────────────────────────────────────────────────────────────
# TITLE-BASED REGEX MATCHING
# ──────────────────────────────────────────────────────────────────────────────
# The bot uses regex patterns on the JOB TITLE to decide include/exclude.

# Job title MUST match this pattern (case-insensitive) to be considered
REQUIRED_PATTERN = r"(data engineer|etl developer|etl engineer|databricks|snowflake|big data)"

# Job title matching this pattern (case-insensitive) will be EXCLUDED
EXCLUDED_PATTERN = r"\b(lead|manager|scientist|analyst|architect|modeler|F2F|face to face|w2 only)\b"

# ──────────────────────────────────────────────────────────────────────────────
# DESCRIPTION KEYWORD SCORING (secondary — title regex is the primary gate)
# ──────────────────────────────────────────────────────────────────────────────

MATCH_KEYWORDS = [
    "Python",
    "SQL",
    "ETL",
    "Airflow",
    "Spark",
    "AWS",
    "Azure",
    "GCP",
    "dbt",
    "Snowflake",
    "BigQuery",
    "Kafka",
    "Data Pipeline",
    "Data Warehouse",
    "Redshift",
    "Databricks",
    "Docker",
    "Kubernetes",
    "Terraform",
    "CI/CD",
]

# Minimum number of MATCH_KEYWORDS in the description (secondary check)
MATCH_THRESHOLD = 2

# ──────────────────────────────────────────────────────────────────────────────
# APPLICATION LIMITS & BEHAVIOR
# ──────────────────────────────────────────────────────────────────────────────

# Maximum number of applications to submit in one session
MAX_APPLICATIONS = 25

# Maximum number of job pages to scan
MAX_PAGES = 10

# Maximum number of jobs to scan total (across all pages)
MAX_JOBS_TO_SCAN = 100

# ──────────────────────────────────────────────────────────────────────────────
# TIMING (seconds) — Randomized delays to mimic human behavior
# ──────────────────────────────────────────────────────────────────────────────

# Scale all delays by this factor (lower = faster). 1.0 keeps original timing.
DELAY_FACTOR = 0.7

# Delay range after each major action (min, max)
ACTION_DELAY = (2, 5)

# Delay range between scanning individual jobs
SCAN_DELAY = (1, 3)

# Delay after submitting an application
APPLY_DELAY = (3, 7)

# Maximum time to wait for a page element to load (seconds)
PAGE_LOAD_TIMEOUT = 20

# Time to wait for user to complete manual login (seconds)
MANUAL_LOGIN_TIMEOUT = 120

# Optional: use your real Chrome profile to reuse cookies/sessions (helps avoid CAPTCHAs)
# Example (macOS): USER_DATA_DIR = "/Users/<you>/Library/Application Support/Google/Chrome"
USER_DATA_DIR = ""
PROFILE_DIRECTORY = "Default"

# Set to True to try undetected_chromedriver first; False to stick with standard ChromeDriver
USE_UNDETECTED = False

# ──────────────────────────────────────────────────────────────────────────────
# APPLICANT INFO — Used to auto-fill application forms
# ──────────────────────────────────────────────────────────────────────────────

APPLICANT_INFO = {
    "first_name":       "Jaswanth",
    "last_name":        "Naidu",
    "full_name":        "Jaswanth Naidu",
    "email":            "JaswanthNaidu643@gmail.com",
    "phone":            "5308508289",
    "linkedin":         "https://linkedin.com/in/jaswanthnaidup",
    "current_title":    "Senior Data Engineer",
    "current_company":  "PayPal",
    "years_experience": "11",
    "education":        "Bachelor's Degree in Computer Science",
    "city":             "",
    "state":            "",
    "zip_code":         "",
    "country":          "United States",
    "willing_to_relocate": True,
    "work_authorization": "Authorized to work in the US",
    "sponsorship_needed": False,
    "salary_expectation": "",
    "start_date":       "Immediately",
    "certifications": [
        "Google Cloud Certified Professional Data Engineer",
        "AWS Certified Data Engineer Associate",
        "Microsoft Certified Azure Data Engineer Associate",
    ],
    "skills_summary": (
        "Python, SQL, ETL, AWS Glue, Airflow, Spark, PySpark, Databricks, "
        "Snowflake, BigQuery, Kafka, Redshift, Azure Data Factory, Terraform, "
        "Docker, Kubernetes, CI/CD, dbt, FastAPI, gRPC, GraphQL, Django, "
        "MongoDB, PostgreSQL, Oracle, SageMaker, Bedrock, GenAI, Pandas, "
        "NumPy, PyArrow, Scikit-Learn, Boto3, Prefect, Dagster"
    ),
}

# ──────────────────────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────────────────────

# Log directory (relative to project root)
LOG_DIR = "logs"

# Print verbose output to console
VERBOSE = True
