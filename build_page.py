"""Build vacancies.html from jobs.json (+ optional extras.json for events/courses the team adds)."""
import datetime as dt, html, json

E = html.escape
data = json.load(open("jobs.json"))
TODAY = dt.date.fromisoformat(data["generated"])
try:
    extras = json.load(open("extras.json"))   # {"events": [{"title","url","detail"}]}
except FileNotFoundError:
    extras = {"events": []}

def fmt(d):
    return f"{d.day} {d:%b}" if d else ""

def card(j):
    chips = []
    if j.get("pinned"): chips.append('<span class="chip soon">WYK pick</span>')
    if j["new"]: chips.append('<span class="chip new">New this week</span>')
    posted = dt.date.fromisoformat(j["posted"]) if j.get("posted") else None
    line = (f"Posted {fmt(posted)}" if posted else f"First seen {fmt(dt.date.fromisoformat(j['first_seen']))}")
    src = {"careers-page": "Careers page"}.get(j["source"], j["source"].title())
    meta = [f'<span><strong>{E(j["company"] or "")}</strong></span>']
    if j.get("location"): meta.append(f'<span class="sep">·</span><span>{E(j["location"])}</span>')
    if j.get("salary"): meta.append(f'<span class="sep">·</span><span class="mono">{E(j["salary"])}</span>')
    note = f'<p class="snippet"><strong>WYK note:</strong> {E(j["note"])}</p>' if j.get("note") else ""
    snip = f'<p class="snippet">{E(j["snippet"])}</p>' if j.get("snippet") else ""
    U = E(j["url"] or "")
    return f'''      <article class="listing">
        <div class="listing-top"><div class="chips">{''.join(chips)}</div><span class="chip source">{E(src)}</span></div>
        <h2><a href="{U}" target="_blank" rel="noopener">{E(j["title"])}</a></h2>
        <div class="meta">{''.join(meta)}</div>
        <div class="closing ok">{line}</div>
        {note}{snip}
        <a class="apply" href="{U}" target="_blank" rel="noopener">View &amp; apply →</a>
      </article>'''

def order(j):
    d = j.get("posted") or j["first_seen"]
    return (not j.get("pinned"), not j["new"], -dt.date.fromisoformat(d).toordinal())

def section(title, note, js, after=""):
    cs = "\n".join(card(j) for j in sorted(js, key=order))
    return f'''  <section class="region">
    <div class="region-head"><h2 class="display">{title}</h2><span class="mono count">{len(js)} roles</span></div>
    <p class="region-note">{note}</p>
{after}
    <div class="listings">
{cs}
    </div>
  </section>'''

jobs = [j for j in data["jobs"] if not j.get("hidden")]
L = [j for j in jobs if j["region"] == "L"]; R = [j for j in jobs if j["region"] == "R"]
ev = ""
if extras.get("events"):
    items = "".join(f'<li><a href="{E(e["url"])}" target="_blank" rel="noopener">{E(e["title"])}</a> — {E(e.get("detail",""))}</li>' for e in extras["events"])
    ev = f'    <aside class="events"><h3>Events &amp; courses</h3><ul>{items}</ul></aside>'
body = section("London &amp; Surrounding Areas", "Greater London plus commutable Home Counties. WYK picks first, then newest.", L, ev)
if R:
    body += "\n" + section("Rest of the UK", "Everywhere else. Newest first.", R)
tpl = open("page_template.html").read().replace("%%LOGO%%", open("logo.b64").read())
out = (tpl.replace("%%CARDS%%", body).replace("%%N%%", str(len(jobs))).replace("%%LN%%", str(len(L)))
          .replace("%%NEW%%", str(sum(j["new"] for j in jobs))).replace("%%SOON%%", str(data.get("closed", 0))))
out = out.replace("Updated 7 Oct 2026", f"Updated {TODAY.day} {TODAY:%b %Y}")
open("vacancies.html", "w").write(out)
print("vacancies.html written:", len(jobs), "roles")
