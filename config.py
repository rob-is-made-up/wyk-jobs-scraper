"""Settings for the WYK jobs scraper. Edit these lists rather than the code."""

# Title must contain at least one of these (case-insensitive) to count as entry level.
ENTRY_TERMS = [
    "assistant", "executive", "exec", "junior", "graduate", "apprentice", "apprenticeship",
    "trainee", "intern", "internship", "entry level", "entry-level", "early careers",
    "coordinator", "co-ordinator", "associate", "analyst", "academy", "scheme", "programme",
]

# ...and must NOT contain any of these.
EXCLUDE_TERMS = [
    "senior", "snr", "sr.", "lead", "head of", "director", "manager", "principal", "vp ",
    "vice president", "partner", "chief", "account director", "associate director",
    "executive assistant", "pa to", "personal assistant", "sales executive", "business development",
    "software", "engineer", "developer", "finance", "accounts payable", "payroll", "legal",
    "it support", "receptionist",
    # sales and non-marketing roles that borrow marketing words
    "sales", "new business", "saas", "b2b", "fintech", "trading", "certification", "procurement",
    # contract types the sheet doesn't cover
    "freelance", "temporary", "temp ", "interim", "part time", "part-time", "fixed term",
    # paid training courses pretending to be jobs
    "training course", "no experience required",
    # overseas offices picked up from agency careers pages
    "cape town", "argentina", "south africa", "india", "dubai", "singapore", "new york", "sydney",
]

# Companies whose adverts are paid training courses or recruiters we don't want.
EXCLUDE_EMPLOYERS = [
    "netcom", "itol", "qualify nation", "it career switch", "learning people", "e-careers", "growth for good",
]

# Title should relate to digital marketing / media / creative work.
FIELD_TERMS = [
    "marketing", "digital", "media", "social", "content", "seo", "geo", "ppc", "paid", "search",
    "biddable", "programmatic", "performance", "planning", "planner", "account", "client",
    "campaign", "brand", "creative", "copy", "influencer", "creator", "community", "crm", "email",
    "ecommerce", "e-commerce", "analytics", "insight", "data", "pr", "communications", "comms",
    "partnerships", "growth", "strategy", "strategist", "production", "producer", "design",
]

# Where we want roles. "region" decides the page section.
LONDON_TERMS = [
    "london", "greater london", "middlesex", "surrey", "kent", "essex", "hertfordshire", "herts",
    "berkshire", "buckinghamshire", "bucks", "croydon", "kingston", "richmond", "watford",
    "slough", "reading", "guildford", "woking", "epsom", "redhill", "dorking", "chesham",
    "uxbridge", "hayes", "harrow", "ilford", "romford", "bromley", "sutton",
]
UK_TERMS = ["united kingdom", "uk", "england", "scotland", "wales", "northern ireland", "gb",
            "manchester", "birmingham", "leeds", "bristol", "glasgow", "edinburgh", "cardiff",
            "liverpool", "newcastle", "sheffield", "nottingham", "brighton", "remote"]

# Big groups: one central careers system covers every agency in the group.
# ats + token are what the fetchers need. Anything marked "verify" should be checked
# on the first run with network access.
GROUP_FEEDS = [
    {"company": "WPP Media (EssenceMediacom, Mindshare, Wavemaker, OpenDoor…)", "ats": "greenhouse", "token": "wppmedia"},
    {"company": "Dentsu (Carat, iProspect, Merkle, dentsu X, Dentsu B2B…)", "ats": "workday",
     "token": "dentsuaegis|wd3|DAN_GLOBAL"},
    {"company": "Havas (Havas Media Network, Havas London…)", "ats": "workday_site",
     "token": "havas|wd3|GroupExternalCareerSite"},
    {"company": "Publicis Groupe (Starcom, Zenith, Spark Foundry, Digitas, Leo, Saatchi, BBH…)", "ats": "icims",
     "token": "careers-publicisgroupe"},
    {"company": "Omnicom (OMD, PHD, Hearts & Science, adam&eveDDB, AMV BBDO, McCann, UM, Initiative…)",
     "ats": "verify", "token": ""},
    {"company": "Monks (S4 Capital)", "ats": "verify", "token": ""},
    {"company": "Accenture Song (Droga5…)", "ats": "verify", "token": ""},
    {"company": "VCCP", "ats": "verify", "token": ""},
    {"company": "the7stars", "ats": "verify", "token": ""},
    {"company": "Brainlabs", "ats": "verify", "token": ""},
    {"company": "Jellyfish", "ats": "verify", "token": ""},
]

# Agencies in the pilot whose jobs are covered by a group feed above.
GROUP_MEMBERS = {
    "WPP": ["AKQA", "EssenceMediacom", "Mindshare", "Mirum Agency", "SYZYGY London", "Wavemaker UK"],
    "Dentsu": ["Carat UK", "iProspect", "Merkle"],
    "Publicis": ["Digitas UK", "Performics"],
    "Omnicom": ["Adam&EveDDB", "AMV BBDO", "Critical Mass", "MG OMD", "PHD Media", "McCann Demand",
                "Mediahub UK", "Reprise Digital"],
    "Havas": ["Havas"],
}

USER_AGENT = "WYK-Digital-jobs-bot/1.0 (+https://www.wykdigital.com; learner vacancy sheet)"
REQUEST_TIMEOUT = 20
