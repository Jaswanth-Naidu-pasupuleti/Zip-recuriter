# 🤖 ZipRecruiter Job Search & Auto-Apply Bot

Automates searching for **Data Engineer** jobs on ZipRecruiter, filtering results by keywords, and applying to positions that match your criteria.

## ⚡ Quick Start

### 1. Install Dependencies
```bash
pip3 install -r requirements.txt
```

### 2. Set Up Credentials
```bash
cp .env.example .env
# Edit .env with your ZipRecruiter email and password
```

### 3. Customize Your Preferences
Edit `config.py` to adjust:
- **Search query** and **location**
- **Filters** (job type, date posted, remote preference, salary)
- **Match keywords** (skills you want the job to require)
- **Exclude keywords** (jobs to skip automatically)
- **Match threshold** (minimum keyword matches to auto-apply)

### 4. Run the Bot

**Dry Run** (scan only, no applications — recommended first!):
```bash
python3 ziprecruiter_bot.py --dry-run
```

**Live Run** (will actually apply):
```bash
python3 ziprecruiter_bot.py
```

## 🎛️ CLI Options

| Flag | Description | Example |
|------|-------------|---------|
| `--dry-run` | Scan and log matches without applying | `python3 ziprecruiter_bot.py --dry-run` |
| `--query` | Override search query | `--query "ML Engineer"` |
| `--location` | Override location | `--location "Austin, TX"` |
| `--max-apply` | Override max applications per session | `--max-apply 10` |
| `--threshold` | Override keyword match threshold | `--threshold 4` |

**Combined example:**
```bash
python3 ziprecruiter_bot.py --dry-run --query "ML Engineer" --location "Austin, TX" --threshold 4
```

## 📁 Project Structure

```
├── ziprecruiter_bot.py   # Main automation script
├── config.py             # All configurable settings
├── .env                  # Your credentials (gitignored)
├── .env.example          # Credential template
├── .gitignore            # Protects sensitive files
├── requirements.txt      # Python dependencies
├── README.md             # This file
└── logs/                 # Session logs (auto-created)
    └── job_search_*.log
```

## 🔧 How It Works

1. **Launch** — Opens a visible Chrome browser (you can watch it work)
2. **Login** — Auto-fills credentials or waits for you to log in manually
3. **Search** — Navigates to job search with your query + location
4. **Filter** — Applies configured filters (job type, remote, salary, etc.)
5. **Scan** — Reads each job listing's description
6. **Match** — Checks description against your keyword criteria
7. **Apply** — Clicks "Apply" on matching jobs, skips the rest
8. **Log** — Records everything to a timestamped log file

## 📊 Keyword Matching

The bot scores each job by counting how many of your `MATCH_KEYWORDS` appear in the description. If the count meets or exceeds `MATCH_THRESHOLD`, it applies. Jobs containing any `EXCLUDE_KEYWORDS` are always skipped.

**Default match keywords:**
`Python, SQL, ETL, Airflow, Spark, AWS, Azure, GCP, dbt, Snowflake, BigQuery, Kafka, Data Pipeline, Data Warehouse, Redshift, Databricks, Docker, Kubernetes, Terraform, CI/CD`

**Default exclude keywords:**
`Senior Staff, Principal, Director, VP, Vice President, 10+ years, 15+ years, security clearance, TS/SCI`

## 🛡️ Safety Features

- **Dry-run mode** — Test without submitting any applications
- **Visible browser** — Watch exactly what the bot does
- **Max application limit** — Won't exceed the configured cap
- **Human-like delays** — Random pauses between actions
- **Session logging** — Full audit trail of every action
- **Browser stays open** — Review results after the script finishes
- **Manual login fallback** — If auto-login fails, you get 2 minutes to log in yourself

## ⚠️ Disclaimer

- This script is for **educational and personal productivity purposes**
- Automated applications may violate ZipRecruiter's Terms of Service
- Use responsibly and at your own risk
- Always review the jobs the bot matches before running in live mode
- Consider using `--dry-run` first to verify keyword matching works well
# Zip-recuriter-
