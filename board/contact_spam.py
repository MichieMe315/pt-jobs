import re
from urllib.parse import urlsplit


BLOCKED_DOMAINS = ("boostleadgen.com", "ultraleadgeneration.com")
LINK_PATTERN = re.compile(r"https?://[^\s<>\"']+|(?<![\w.-])www\.[^\s<>\"']+", re.IGNORECASE)


def is_blocked_domain(domain):
    domain = domain.lower().rstrip(".")
    return any(domain == blocked or domain.endswith("." + blocked) for blocked in BLOCKED_DOMAINS)


def is_blocked_contact(email, message):
    if is_blocked_domain(email.rpartition("@")[2]):
        return True
    for match in LINK_PATTERN.finditer(message):
        link = match.group()
        try:
            host = urlsplit(link if "://" in link else "//" + link).hostname
        except ValueError:
            continue
        if host and is_blocked_domain(host.rstrip(",;!?)")):
            return True
    return False
