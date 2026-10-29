"""Weekly run: fetch every source, keep entry-level digital roles, compare with last week,
write jobs.json + a team review spreadsheet, and build the vacancy page.

  python run.py                 # everything in careers_map.csv (+ Reed/Adzuna if keys are set)
  python run.py --limit 20      # quick test on the first 20 employers

Keys (optional) come from a keys.env file in this folder or environment variables:
  REED_API_KEY, ADZUNA_APP_ID, ADZUNA_APP_KEY
"""
import csv
import datetime as dt
import json
import os
import re
import sys
import traceback

import openpyxl

import sources
from config import ENTRY_TERMS, EXCLUDE_TERMS, FIELD_TERMS, LONDON_TERMS, UK_TERMS

STATE_FILE = "state.json"
OVERRIDES_FILE = "overrides.csv"      # team edits: id, hide (y), pin (y), note
TODAY = dt.date.today()


def load_env(paths=("keys.env", ".env")):
    """Read KEY=value lines from keys.env (or .env) into the environment (keys stay out of the code)."""
    for path in paths:
      try:
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
      except FileNotFoundError:
        pass


load_env()


def _has(text, terms):
    return any(re.search(r"(?<![a-z])" + re.escape(t) + r"(?![a-z])", text) for t in terms)


def keep(job):
    t = job["title"].lower()
    if not t or _has(t, EXCLUDE_TERMS):
        return False
    if not _has(t, ENTRY_TERMS):
        return False
    return _has(t, FIELD_TERMS)


def region(job, default_london=False):
    loc = (job.get("location") or "").lower()
    if _has(loc, LONDON_TERMS):
        return "L"
    if _has(loc, UK_TERMS):
        return "R"
    if not loc and default_london:
        return "L"
    return None


def load_map():
    with open("careers_map.csv", newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("ats") and r["ats"] not in ("verify", "teamtailor?")]


def fetch_all(limit=None):
    jobs, log = [], []
    rows = load_map()[:limit] if limit else load_map()
    for r in rows:
        ats = r["ats"]
        target = r["careers_url"] if ats == "html" else r["token"]
        if not target:
            continue
        try:
            got = sources.FETCHERS[ats](target, r["company"].split(" (")[0])
            for j in got:
                j["_london_default"] = True  # every employer in the pilot is London-based
            jobs += got
            log.append((r["company"], ats, "ok", len(got)))
        except Exception as e:  # keep going; report at the end
            log.append((r["company"], ats, f"error: {type(e).__name__}: {str(e)[:120]}", 0))
    if os.getenv("REED_API_KEY"):
        try:
            got = sources.reed(os.environ["REED_API_KEY"]); jobs += got; log.append(("Reed", "api", "ok", len(got)))
        except Exception as e:
            log.append(("Reed", "api", f"error: {e}", 0))
    if os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY"):
        try:
            got = sources.adzuna(os.environ["ADZUNA_APP_ID"], os.environ["ADZUNA_APP_KEY"]); jobs += got
            log.append(("Adzuna", "api", "ok", len(got)))
        except Exception as e:
            log.append(("Adzuna", "api", f"error: {e}", 0))
    return jobs, log


def dedupe(jobs):
    """Same title + company from several sources → keep the employer's own listing."""
    rank = {"reed": 3, "adzuna": 4, "careers-page": 2}
    best = {}
    for j in jobs:
        k = (re.sub(r"\W+", " ", j["title"].lower()).strip(), (j["company"] or "").lower()[:20])
        if k not in best or rank.get(j["source"], 0) < rank.get(best[k]["source"], 0):
            best[k] = j
    return list(best.values())


def update_state(jobs):
    try:
        state = json.load(open(STATE_FILE))
    except FileNotFoundError:
        state = {}
    now = TODAY.isoformat()
    current = {}
    for j in jobs:
        prev = state.get(j["id"], {})
        j["first_seen"] = prev.get("first_seen", now)
        current[j["id"]] = j
    closed = [v for k, v in state.items() if k not in current]
    json.dump(current, open(STATE_FILE, "w"), indent=1)
    return closed


def load_overrides():
    try:
        with open(OVERRIDES_FILE, newline="") as f:
            return {r["id"]: r for r in csv.DictReader(f)}
    except FileNotFoundError:
        return {}


def write_review(jobs, closed, log):
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "This week"
    ws.append(["id", "New?", "Region", "Title", "Employer", "Location", "Salary", "Posted", "First seen",
               "Source", "Link", "hide (y)", "pin (y)", "WYK note"])
    for j in sorted(jobs, key=lambda x: (x["region"], x["first_seen"]), reverse=True):
        ws.append([j["id"], "NEW" if j["new"] else "", "London & around" if j["region"] == "L" else "Rest of UK",
                   j["title"], j["company"], j["location"], j.get("salary") or "", j.get("posted") or "",
                   j["first_seen"], j["source"], j["url"], "", "", ""])
    ws2 = wb.create_sheet("Closed since last run")
    ws2.append(["Title", "Employer", "Link", "First seen"])
    for j in closed:
        ws2.append([j["title"], j["company"], j["url"], j.get("first_seen")])
    ws3 = wb.create_sheet("Run log")
    ws3.append(["Employer / source", "System", "Result", "Jobs fetched"])
    for row in log:
        ws3.append(list(row))
    name = f"review-{TODAY.isoformat()}.xlsx"
    wb.save(name)
    return name


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    raw, log = fetch_all(limit)
    kept = []
    for j in raw:
        if not keep(j):
            continue
        reg = region(j, j.pop("_london_default", False))
        if not reg:
            continue
        j["region"] = reg
        kept.append(j)
    kept = dedupe(kept)
    closed = update_state(kept)
    ov = load_overrides()
    for j in kept:
        o = ov.get(j["id"], {})
        j["hidden"] = o.get("hide", "").lower() == "y"
        j["pinned"] = o.get("pin", "").lower() == "y"
        j["note"] = o.get("note", "")
        j["new"] = (TODAY - dt.date.fromisoformat(j["first_seen"])).days <= 7
    json.dump({"generated": TODAY.isoformat(), "jobs": kept, "closed": len(closed)},
              open("jobs.json", "w"), indent=1)
    review = write_review(kept, closed, log)
    errors = [l for l in log if l[2] != "ok"]
    print(f"fetched {len(raw)} · kept {len(kept)} ({sum(j['region']=='L' for j in kept)} London) · "
          f"new {sum(j['new'] for j in kept)} · closed {len(closed)} · source errors {len(errors)}")
    print(f"review sheet: {review}")


if __name__ == "__main__":
    main()
