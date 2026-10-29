"""One-off (and occasional) step: find each employer's careers page and hiring system.

Reads the agency list, visits each website plus common careers paths, and spots links to
known hiring systems. Writes careers_map.csv. Rows you edit by hand (manual = "y") are kept
on later runs.

  python discover.py "UK Agencies.xlsx"            # London digital agencies (pilot)
  python discover.py "UK Agencies.xlsx" --all      # every company with a website
"""
import csv
import re
import sys
import time
from urllib.parse import urljoin, urlparse

import openpyxl
import requests

from config import GROUP_FEEDS, GROUP_MEMBERS
from sources import S

MAP_FILE = "careers_map.csv"
FIELDS = ["company", "website", "group", "careers_url", "ats", "token", "status", "manual", "notes"]
CAREERS_PATHS = ["", "/careers", "/careers/", "/jobs", "/join-us", "/work-with-us", "/about/careers", "/company/careers"]

ATS_PATTERNS = [
    ("greenhouse", r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?([A-Za-z0-9_-]+)"),
    ("lever", r"jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_-]+)"),
    ("ashby", r"jobs\.ashbyhq\.com/([A-Za-z0-9_.-]+)"),
    ("workable", r"apply\.workable\.com/([A-Za-z0-9_-]+)"),
    ("workday", r"([A-Za-z0-9_-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)"),
    ("workday_site", r"(wd\d+)\.myworkdaysite\.com/(?:[a-z]{2}-[A-Z]{2}/)?recruiting/([A-Za-z0-9_-]+)/([A-Za-z0-9_-]+)"),
    ("smartrecruiters", r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)"),
    ("recruitee", r"([A-Za-z0-9_-]+)\.recruitee\.com"),
    ("pinpoint", r"([A-Za-z0-9_-]+)\.pinpointhq\.com"),
    ("personio", r"([A-Za-z0-9_-]+)\.jobs\.personio\.(?:de|com)"),
    ("bamboohr", r"([A-Za-z0-9_-]+)\.bamboohr\.com"),
    ("icims", r"((?:careers-)?[A-Za-z0-9_-]+)\.icims\.com"),
    ("teamtailor", r"([A-Za-z0-9_-]+)\.teamtailor\.com"),
]
IGNORE_TOKENS = {"embed", "js", "www", "api", "app", "assets", "cdn", "static", "staticfe", "careers", "jobs"}


def find_ats(text):
    for ats, pat in ATS_PATTERNS:
        for m in re.finditer(pat, text):
            g = m.groups()
            if ats == "workday":
                return ats, f"{g[0]}|{g[1]}|{g[2]}"
            if ats == "workday_site":
                return ats, f"{g[1]}|{g[0]}|{g[2]}"
            if g[0].lower() in IGNORE_TOKENS:
                continue
            if ats == "teamtailor":
                return ats, f"https://{g[0]}.teamtailor.com"
            return ats, g[0]
    if "teamtailor" in text and "/jobs" in text:  # Teamtailor on a custom domain
        return "teamtailor", "SELF"
    return None, None


def careers_link(html, base):
    for href, label in re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', html, flags=re.S | re.I):
        lab = re.sub(r"<[^>]+>", " ", label).lower()
        if re.search(r"\b(careers?|jobs|join (us|the team)|work with us|vacancies|we're hiring|hiring)\b", lab + " " + href.lower()):
            return urljoin(base, href)
    return None


def probe(website):
    if not website:
        return dict(status="no website")
    site = website if website.startswith("http") else "https://" + website
    root = f"{urlparse(site).scheme}://{urlparse(site).netloc}"
    seen_pages, careers = [], None
    for path in CAREERS_PATHS:
        url = site if path == "" else root + path
        try:
            r = S.get(url, timeout=15, allow_redirects=True)
        except requests.RequestException as e:
            if path == "":
                return dict(status=f"site unreachable ({type(e).__name__})")
            continue
        if r.status_code >= 400:
            continue
        seen_pages.append(r.url)
        ats, token = find_ats(r.text)
        if path == "":
            careers = careers_link(r.text, r.url)
            if careers:  # follow the careers link first
                try:
                    r2 = S.get(careers, timeout=15)
                    a2, t2 = find_ats(r2.text)
                    if a2:
                        return dict(careers_url=r2.url, ats=a2, token=t2, status="found")
                    # one level deeper: links on the careers page
                    deeper = careers_link(r2.text, r2.url)
                    if deeper and deeper != careers:
                        r3 = S.get(deeper, timeout=15)
                        a3, t3 = find_ats(r3.text)
                        if a3:
                            return dict(careers_url=r3.url, ats=a3, token=t3, status="found")
                except requests.RequestException:
                    pass
        if ats:
            if token == "SELF":  # custom-domain Teamtailor: the site itself serves /jobs.rss
                token = f"{urlparse(r.url).scheme}://{urlparse(r.url).netloc}"
            return dict(careers_url=r.url, ats=ats, token=token, status="found")
        if path != "" and not careers:
            careers = r.url
        time.sleep(0.3)
    if careers:
        return dict(careers_url=careers, ats="html", token="", status="careers page, no hiring system found")
    return dict(status="no careers page found")


def load_agencies(xlsx, everything=False):
    wb = openpyxl.load_workbook(xlsx, read_only=True)
    rows = [r for r in list(wb["Accounts"].iter_rows(values_only=True))[1:] if r[2]]
    if not everything:
        rows = [r for r in rows if r[4] and "london" in str(r[4]).lower() and r[0] == "Digital agency"]
    member_of = {name: grp for grp, names in GROUP_MEMBERS.items() for name in names}
    out = []
    for r in rows:
        name = str(r[2]).strip()
        out.append(dict(company=name, website=r[5] or "", group=member_of.get(name, "")))
    return out


def main():
    xlsx = sys.argv[1]
    everything = "--all" in sys.argv
    existing = {}
    try:
        with open(MAP_FILE, newline="") as f:
            existing = {row["company"]: row for row in csv.DictReader(f)}
    except FileNotFoundError:
        pass

    rows = []
    for g in GROUP_FEEDS:
        prev = existing.get(g["company"])
        rows.append(prev if prev and prev.get("manual") == "y" else
                    dict(company=g["company"], website="", group="(group feed)", careers_url="",
                         ats=g["ats"], token=g["token"], status="group feed", manual="", notes=""))

    agencies = load_agencies(xlsx, everything)
    for i, a in enumerate(agencies, 1):
        prev = existing.get(a["company"])
        if prev and (prev.get("manual") == "y" or prev.get("status") == "found"):
            rows.append(prev)
            continue
        if a["group"]:
            rows.append(dict(a, careers_url="", ats="", token="", status=f"covered by {a['group']} group feed",
                             manual="", notes=""))
            continue
        res = probe(a["website"])
        rows.append(dict(a, careers_url=res.get("careers_url", ""), ats=res.get("ats", ""),
                         token=res.get("token", ""), status=res["status"], manual="", notes=""))
        print(f"[{i}/{len(agencies)}] {a['company']}: {res['status']} {res.get('ats') or ''} {res.get('token') or ''}")

    with open(MAP_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    found = sum(1 for r in rows if r["status"] == "found")
    print(f"\n{len(rows)} rows · hiring system found for {found} · see {MAP_FILE}")


if __name__ == "__main__":
    main()
