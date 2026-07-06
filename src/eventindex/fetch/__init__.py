"""Fetcher (§5): polite HTTP with content-hash early exit.

Sync httpx: the worker runs one job at a time and the per-domain rate limit
forbids concurrency within a source anyway; async returns when the scheduler
fetches many sources at once.
"""

import hashlib
import time
from dataclasses import dataclass

import httpx

from eventindex import config

FETCHED = "fetched"
UNCHANGED = "unchanged"


@dataclass
class FetchResult:
    status: str  # fetched | unchanged
    url: str
    content: bytes = b""
    content_type: str = ""
    content_hash: str = ""
    etag: str | None = None
    last_modified: str | None = None


def fetch_source(source: dict) -> FetchResult:
    """One conditional GET of the source URL.

    robots.txt is deliberately NOT consulted (Alexander's decision,
    2026-07-06, DECISIONS.md changelog); politeness = honest UA + rate limit.
    """
    headers = {"User-Agent": config.USER_AGENT}
    if source.get("http_etag"):
        headers["If-None-Match"] = source["http_etag"]
    if source.get("http_last_modified"):
        headers["If-Modified-Since"] = source["http_last_modified"]

    with httpx.Client(
        timeout=30, follow_redirects=True, headers={"User-Agent": config.USER_AGENT}
    ) as client:
        time.sleep(config.CRAWL_DELAY_S)
        resp = client.get(source["url"], headers=headers)
        if resp.status_code == 304:
            return FetchResult(status=UNCHANGED, url=source["url"])
        resp.raise_for_status()

    content_hash = hashlib.sha256(resp.content).hexdigest()
    if content_hash == source.get("last_content_hash"):
        return FetchResult(status=UNCHANGED, url=str(resp.url), content_hash=content_hash)

    return FetchResult(
        status=FETCHED,
        url=str(resp.url),
        content=resp.content,
        content_type=resp.headers.get("content-type", ""),
        content_hash=content_hash,
        etag=resp.headers.get("etag"),
        last_modified=resp.headers.get("last-modified"),
    )
