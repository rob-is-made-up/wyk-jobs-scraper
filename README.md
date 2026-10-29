# WYK Jobs Scraper

Builds the entry-level digital marketing vacancy page automatically each week.

## How it works

1. `discover.py` (one-off, re-run occasionally) visits each agency's website, finds its careers page and the hiring system behind it (Greenhouse, Workable, Workday…), and writes `careers_map.csv`. Fix any row by hand and set `manual` to `y` so it is never overwritten.
2. `run.py` (weekly) reads each hiring system's public job list, adds Reed and Adzuna results if API keys are set, keeps entry-level digital/media roles in London and the UK, and compares with last week (`state.json`) to mark roles new or closed. It writes `jobs.json` and `review-YYYY-MM-DD.xlsx` for the team.
3. `build_page.py` turns `jobs.json` into `vacancies.html`, which Claude publishes to the vacancy page.

The scripts only read structured job fields (title, location, link, date). No AI reads the raw web pages, so text planted on a careers site can't instruct anything.

## Team controls

- `overrides.csv` with columns `id,hide,pin,note` lets the team hide a role, pin a WYK pick, or add a note (ids are in the review sheet).
- `extras.json` holds events and courses: `{"events": [{"title": "...", "url": "...", "detail": "..."}]}`.
- `keys.env` holds the API keys (Adzuna, Reed). Keep it private and never share or upload it.
- `config.py` holds the title and location word lists if the filter lets through too much or too little.

## Network access

`allowed_domains.txt` lists the domains the scripts need. API keys go in environment variables: `REED_API_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`.

## Commands

```
pip install requests openpyxl
python discover.py "UK Agencies.xlsx"
python run.py --limit 20     # quick test
python run.py
python build_page.py
```
