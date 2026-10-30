"""Fetchers for each hiring system and job board. Each returns a list of job dicts:
{id, title, company, location, url, posted (YYYY-MM-DD or None), source, salary, snippet}
"""
import datetime as dt
import html
import re
import xml.etree.ElementTree as ET

import requests

from config import USER_AGENT, REQUEST_TIMEOUT

S = requests.Session()
S.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9, */*;q=0.8"})


def _get(url, **kw):
    r = S.get(url, timeout=REQUEST_TIMEOUT, **kw)
    r.raise_for_status()
    return r


def _date(v):
    """Normalise assorted date formats to YYYY-MM-DD."""
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):  # epoch ms or s
        v = v / 1000 if v > 1e11 else v
        return dt.datetime.utcfromtimestamp(v).date().isoformat()
    s = str(v).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d", "%d/%m/%Y", "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else None


def _strip(h, n=280):
    t = re.sub(r"<[^>]+>", " ", html.unescape(h or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return (t[: n - 1] + "…") if len(t) > n else t


def _job(source, company, jid, title, location, url, posted=None, salary=None, snippet=""):
    return {"id": f"{source}:{jid}", "title": (title or "").strip(), "company": company,
            "location": (location or "").strip(), "url": url, "posted": _date(posted),
            "source": source, "salary": salary, "snippet": snippet}


# ---------- hiring systems ----------

def greenhouse(token, company):
    d = _get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs").json()
    return [_job("greenhouse", company, j["id"], j["title"], (j.get("location") or {}).get("name"),
                 j["absolute_url"], j.get("first_published") or j.get("updated_at")) for j in d.get("jobs", [])]


def lever(token, company):
    out = []
    for host in ("api.lever.co", "api.eu.lever.co"):
        try:
            d = _get(f"https://{host}/v0/postings/{token}?mode=json").json()
        except requests.HTTPError:
            continue
        for j in d:
            c = j.get("categories") or {}
            out.append(_job("lever", company, j["id"], j.get("text"), c.get("location"), j.get("hostedUrl"),
                            j.get("createdAt"), snippet=_strip(j.get("descriptionPlain") or j.get("description"))))
        if out:
            break
    return out


def ashby(token, company):
    d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{token}").json()
    return [_job("ashby", company, j.get("id"), j.get("title"), j.get("location"), j.get("jobUrl"),
                 j.get("publishedAt"), snippet=_strip(j.get("descriptionPlain"))) for j in d.get("jobs", [])
            if j.get("isListed", True)]


def workable(token, company):
    d = _get(f"https://apply.workable.com/api/v1/widget/accounts/{token}").json()
    out = []
    for j in d.get("jobs", []):
        loc = ", ".join(x for x in [j.get("city"), j.get("country")] if x)
        out.append(_job("workable", company, j.get("shortcode"), j.get("title"), loc,
                        j.get("url") or j.get("application_url"), j.get("published_on") or j.get("created_at")))
    return out


def teamtailor(base, company):
    """base = careers site root, e.g. https://acme.teamtailor.com or https://careers.acme.com"""
    r = _get(base.rstrip("/") + "/jobs.rss")
    root = ET.fromstring(r.content)
    out = []
    for it in root.iter("item"):
        g = lambda tag: (it.findtext(tag) or "").strip()
        loc = " ".join(e.text or "" for e in it.iter() if e.tag.lower().endswith("city") or e.tag.lower().endswith("location"))
        out.append(_job("teamtailor", company, g("guid") or g("link"), g("title"), loc, g("link"), g("pubDate"),
                        snippet=_strip(g("description"))))
    return out


def workday(token, company, site_host=False):
    """token = tenant|wdN|site. site_host=True for *.myworkdaysite.com tenants."""
    tenant, wd, site = token.split("|")
    if site_host:
        api = f"https://{wd}.myworkdaysite.com/wday/cxs/{tenant}/{site}/jobs"
        pub = f"https://{wd}.myworkdaysite.com/recruiting/{tenant}/{site}"
    else:
        api = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
        pub = f"https://{tenant}.{wd}.myworkdayjobs.com/en-US/{site}"
    out, offset = [], 0
    while offset < 400:
        r = S.post(api, json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": "London"},
                   timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        d = r.json()
        posts = d.get("jobPostings", [])
        for j in posts:
            out.append(_job("workday", company, j.get("externalPath"), j.get("title"), j.get("locationsText"),
                            pub + (j.get("externalPath") or ""), _workday_posted(j.get("postedOn"))))
        offset += 20
        if offset >= d.get("total", 0) or not posts:
            break
    return out


def _workday_posted(text):
    """Workday says 'Posted Today', 'Posted 3 Days Ago', 'Posted 30+ Days Ago'."""
    if not text:
        return None
    t = text.lower()
    today = dt.date.today()
    if "today" in t:
        return today.isoformat()
    if "yesterday" in t:
        return (today - dt.timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\+?\s*day", t)
    return (today - dt.timedelta(days=int(m.group(1)))).isoformat() if m else None


def smartrecruiters(token, company):
    d = _get(f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100").json()
    out = []
    for j in d.get("content", []):
        loc = j.get("location") or {}
        out.append(_job("smartrecruiters", company, j.get("id"), j.get("name"),
                        ", ".join(x for x in [loc.get("city"), loc.get("country")] if x),
                        f"https://jobs.smartrecruiters.com/{token}/{j.get('id')}", j.get("releasedDate")))
    return out


def recruitee(token, company):
    d = _get(f"https://{token}.recruitee.com/api/offers/").json()
    return [_job("recruitee", company, j.get("id"), j.get("title"), j.get("location"), j.get("careers_url"),
                 j.get("published_at"), snippet=_strip(j.get("description"))) for j in d.get("offers", [])]


def pinpoint(token, company):
    d = _get(f"https://{token}.pinpointhq.com/postings.json").json()
    out = []
    for j in d.get("data", d if isinstance(d, list) else []):
        loc = j.get("location") or {}
        out.append(_job("pinpoint", company, j.get("id"), j.get("title"),
                        loc.get("name") if isinstance(loc, dict) else loc, j.get("url"), j.get("published_at")))
    return out


def personio(token, company):
    r = _get(f"https://{token}.jobs.personio.de/xml")
    root = ET.fromstring(r.content)
    out = []
    for p in root.iter("position"):
        jid = p.findtext("id")
        out.append(_job("personio", company, jid, p.findtext("name"), p.findtext("office"),
                        f"https://{token}.jobs.personio.de/job/{jid}", p.findtext("createdAt")))
    return out


def bamboohr(token, company):
    d = _get(f"https://{token}.bamboohr.com/careers/list").json()
    out = []
    for j in d.get("result", []):
        loc = j.get("location") or {}
        out.append(_job("bamboohr", company, j.get("id"), j.get("jobOpeningName"),
                        ", ".join(x for x in [loc.get("city"), loc.get("state")] if x),
                        f"https://{token}.bamboohr.com/careers/{j.get('id')}"))
    return out


def icims(token, company):
    """iCIMS has no public JSON; read the search results page (London filter)."""
    base = f"https://{token}.icims.com"
    out = []
    for page in range(0, 10):
        r = _get(f"{base}/jobs/search?pr={page}&searchLocation=12781-12827-London&in_iframe=1")
        found = re.findall(r'href="(https://[^"]+/jobs/(\d+)/[^"]+/job)[^"]*"[^>]*>\s*(?:<[^>]+>\s*)*([^<]{3,140})<', r.text)
        if not found:
            break
        for url, jid, title in found:
            out.append(_job("icims", company, jid, html.unescape(title), "London", url))
    return list({j["id"]: j for j in out}.values())


def generic_html(url, company):
    """Last resort: collect link texts on a careers page that look like job titles.
    The filter decides which survive; results are marked for a human to check."""
    r = _get(url)
    out = []
    for href, text in re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', r.text, flags=re.S | re.I):
        t = _strip(text, 140)
        if 6 <= len(t) <= 120:
            full = requests.compat.urljoin(url, href)
            out.append(_job("careers-page", company, full, t, "", full))
    return out


FETCHERS = {
    "greenhouse": greenhouse, "lever": lever, "ashby": ashby, "workable": workable,
    "teamtailor": teamtailor, "workday": workday,
    "workday_site": lambda t, c: workday(t, c, site_host=True),
    "smartrecruiters": smartrecruiters, "recruitee": recruitee, "pinpoint": pinpoint,
    "personio": personio, "bamboohr": bamboohr, "icims": icims, "html": generic_html,
}


# ---------- job boards ----------

REED_QUERIES = ["digital marketing assistant", "digital marketing executive", "social media executive",
                "social media assistant", "marketing assistant", "seo executive", "ppc executive",
                "paid social executive", "media executive", "account executive marketing",
                "content assistant", "graduate marketing", "marketing apprentice"]


def reed(api_key, location="London", distance=25, max_days=14):
    out, seen = [], set()
    for q in REED_QUERIES:
        r = S.get("https://www.reed.co.uk/api/1.0/search", auth=(api_key, ""), timeout=REQUEST_TIMEOUT,
                  params={"keywords": q, "locationName": location, "distanceFromLocation": distance,
                          "resultsToTake": 100})
        r.raise_for_status()
        for j in r.json().get("results", []):
            if j["jobId"] in seen:
                continue
            seen.add(j["jobId"])
            posted = _date(j.get("date"))
            if posted and (dt.date.today() - dt.date.fromisoformat(posted)).days > max_days:
                continue
            sal = None
            if j.get("minimumSalary"):
                sal = f"£{int(j['minimumSalary']):,}" + (f"–£{int(j['maximumSalary']):,}" if j.get("maximumSalary") and j["maximumSalary"] != j["minimumSalary"] else "")
            out.append(_job("reed", j.get("employerName"), j["jobId"], j.get("jobTitle"), j.get("locationName"),
                            j.get("jobUrl"), posted, sal, _strip(j.get("jobDescription"))))
    return out


def adzuna(app_id, app_key, where="London", max_days=14):
    out, seen = [], set()
    for q in REED_QUERIES:
        r = S.get("https://api.adzuna.com/v1/api/jobs/gb/search/1", timeout=REQUEST_TIMEOUT,
                  params={"app_id": app_id, "app_key": app_key, "what": q, "where": where, "distance": 40,
                          "results_per_page": 50, "max_days_old": max_days, "content-type": "application/json"})
        r.raise_for_status()
        for j in r.json().get("results", []):
            if j["id"] in seen:
                continue
            seen.add(j["id"])
            sal = None
            if j.get("salary_min") and not j.get("salary_is_predicted") == "1":
                sal = f"£{int(j['salary_min']):,}" + (f"–£{int(j['salary_max']):,}" if j.get("salary_max") and j["salary_max"] != j["salary_min"] else "")
            out.append(_job("adzuna", (j.get("company") or {}).get("display_name"), j["id"], j.get("title"),
                            (j.get("location") or {}).get("display_name"), j.get("redirect_url"),
                            j.get("created"), sal, _strip(j.get("description"))))
    return out


# ---------- Jibe / iCIMS careers sites (e.g. careers.publicisgroupe.com) ----------

def jibe(base, company):
    """base = site root. Pulls every job within 15 miles of London; the title filter does the rest."""
    base = base.rstrip("/")
    params = ("location=London%2C%20Greater%20London%2C%20United%20Kingdom&woe=7&regionCode=GB"
              "&stretchUnit=MILES&stretch=15&limit=100")
    out, page = [], 1
    while page <= 10:
        d = _get(f"{base}/api/jobs?{params}&page={page}", headers={"Accept": "application/json"}).json()
        jobs = d.get("jobs", [])
        for x in jobs:
            j = x.get("data", {})
            brand = "/".join(j.get("tags2") or []) or j.get("hiring_organization") or company
            level = "/".join(j.get("tags5") or [])
            out.append(_job("jibe", f"{company} - {brand}" if brand != company else company,
                            j.get("req_id") or j.get("slug"), j.get("title"), j.get("city") or j.get("location_name"),
                            f"{base}/jobs/{j.get('slug')}?lang=en-us", j.get("posted_date"),
                            snippet=(f"Experience level: {level}. " if level else "") + _strip(j.get("description"), 220)))
        if len(jobs) < 100 or page * 100 >= d.get("totalCount", 0):
            break
        page += 1
    return out


FETCHERS["jibe"] = jibe
