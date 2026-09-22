"""
config.py - Task 1: crawling configuration.

Everything that controls *what* and *how much* gets crawled lives here, so the
crawler logic never has to be edited to change a run.
"""

# ---------------------------------------------------------------- topic ----
TOPIC = "News & Information"

# Single-domain focused crawl: The Guardian only.
#
# To widen the crawl to a second domain from the same topic, uncomment the BBC
# entries below in DOMAINS, SEED_URLS and ALLOWED_DOMAINS - nothing else needs
# to change. (BBC was verified as crawlable: robots.txt allows the seed and it
# answers HTTP 200. Reuters was rejected - robots.txt disallows the seed page
# and the site answers HTTP 401.)
DOMAINS = [
    "The Guardian",
    # "BBC",
]

SEED_URLS = [
    "https://www.theguardian.com/international",
    "https://www.theguardian.com/world",
    # "https://www.bbc.com/news",
]

# Domain rule: a URL is in-scope when its host equals one of these entries or
# is a subdomain of one. So theguardian.com, www.theguardian.com and
# amp.theguardian.com are all accepted, while theguardian.com.evil.net is not
# (see parser.is_allowed_domain).
ALLOWED_DOMAINS = [
    "theguardian.com",
    # "bbc.com",
]

# The subdomain rule above is deliberately permissive, but theguardian.com
# hangs a lot of non-editorial business off its own subdomains: a holiday shop,
# the subscription and account portals, a jobs board and the ad sales sites.
# Those are on-domain by the rule yet carry no journalism, so they are excluded
# by host. Only the editorial hosts survive.
BLOCKED_SUBDOMAINS = (
    "holidays", "support", "manage", "profile", "jobs", "patrons",
    "advertising", "usadvertising", "ausadvertising", "syndication",
    "workforus", "sourcing", "contribute", "membership",
)

# --------------------------------------------------------- crawl limits ----
MAX_DEPTH = 2          # seeds are depth 0
MAX_PAGES = 100
REQUEST_TIMEOUT = 10   # seconds
CRAWL_DELAY = 1.0      # seconds between two requests

# A Guardian section page yields ~80 in-scope links, so two seeds alone produce
# ~150 URLs at depth 1 - more than MAX_PAGES. Breadth-first order then spends
# the whole page budget on depth 1 and never reaches depth 2, which is correct
# BFS behaviour but leaves the depth limit untested.
#
# Setting this to a small number caps how many links each page contributes to
# the frontier, so the crawl descends instead of fanning out. 0 = unlimited
# (the default, and the honest breadth-first sample).
MAX_LINKS_PER_PAGE = 0

# ------------------------------------------------------------- politeness --
USER_AGENT = "SEG301-StudentCrawler/1.0 (coursework; contact: student@fpt.edu.vn)"
RESPECT_ROBOTS = True

# ------------------------------------------------------------- filtering ---
# Link targets that are not web pages at all.
BLOCKED_SCHEMES = ("mailto:", "javascript:", "tel:", "sms:", "ftp:", "file:")

BLOCKED_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".bmp",
    ".css", ".js", ".json", ".xml", ".rss",
    ".zip", ".gz", ".tar", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".webm",
)

# "Focused" crawler: theguardian.com hosts a lot besides written journalism -
# a video player, photo galleries, crosswords, a shop, a jobs board and the
# subscription funnel. Those pages are on-domain but carry no article text, so
# they are excluded to keep the collected corpus on-topic.
#
# Note: /search, /discussion, /email, /print, /preference and /sections are
# already Disallowed by theguardian.com/robots.txt, so the robots check
# rejects them too; they are not duplicated here.
BLOCKED_PATH_PREFIXES = (
    "/video", "/audio", "/pictures", "/ng-interactive",
    "/crosswords", "/puzzles",
    "/signin", "/register", "/profile", "/account",
    "/help", "/info", "/about", "/contactus",
    "/membership", "/subscribe", "/contribute", "/give",
    "/jobs", "/guardian-masterclasses", "/guardian-live-events",
    "/index", "/tone", "/applications",
)

# ------------------------------------------------------------- storage -----
DATABASE_PATH = "data/crawler.db"
MAX_CONTENT_CHARS = 20000   # keeps the DB a sensible size; 0 = no limit
