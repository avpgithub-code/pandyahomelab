"""User-agent bot check for the page-view beacon.

Keep BOT_PATTERNS in sync with analytics-ingester/ingester/enricher.py. Only bots
that execute JavaScript can reach the beacon at all, so this is a second filter.
"""

BOT_PATTERNS = (
    "bot", "crawler", "spider", "scraper",
    "googlebot", "bingbot", "duckduckbot", "slurp", "yandex", "baiduspider",
    "ahrefsbot", "semrushbot", "mj12bot", "dotbot", "petalbot",
    "curl", "wget", "python-requests", "python-urllib", "httpx", "go-http-client",
    "facebookexternalhit", "twitterbot", "linkedinbot", "slackbot", "whatsapp",
    "uptimerobot", "pingdom", "statuscake", "site24x7",
    "headlesschrome", "phantomjs",
    "l9scan", "leakix", "infrawatch", "zgrab", "masscan", "nmap", "censys",
    "expanse", "nuclei", "odin", "internet-measurement",
    # JS-capable automation that the log-based ingester rarely sees
    "lighthouse", "chrome-lighthouse", "gtmetrix", "pagespeed", "playwright", "puppeteer", "selenium",
)


def is_bot(user_agent: str) -> bool:
    if not user_agent or not user_agent.strip():
        return True
    ua_lower = user_agent.lower()
    return any(p in ua_lower for p in BOT_PATTERNS)
