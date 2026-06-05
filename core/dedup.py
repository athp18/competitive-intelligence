from hashlib import sha256
from urllib.parse import parse_qs, ParseResult, urlencode, urlparse

STRIP_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "ref", "fbclid"}


def canonicalize_url(url: str) -> str:
    parsed: ParseResult = urlparse(url)
    params = {k: v for k, v in parse_qs(parsed.query).items() if k not in STRIP_PARAMS}
    clean = parsed._replace(query=urlencode(params, doseq=True), fragment="")
    return clean.geturl()


def content_hash(title: str, url: str) -> str:
    canonical = canonicalize_url(url)
    return sha256(f"{title}||{canonical}".encode()).hexdigest()
