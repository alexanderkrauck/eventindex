"""Tier a2: deterministic extraction from JSON API bodies.

The "second API format" trigger anticipated in the cascade fired 2026-07-20:
SPA platforms (Nexudus et al.) serve their events as public JSON that the
onboarding agent names as entry_url, but the cascade could not parse a JSON
body - three correct factory300 recipes were rejected with "items 0" while
the events sat beyond llm_text's char cap.

No per-platform code: a walker finds arrays of records carrying a title-ish
and a parseable date-ish key; fields map by key-name heuristics. Anything it
cannot map falls through to the LLM tier as before.
"""

import json

CONFIDENCE = 0.85  # same standing as recipe selectors: structured, unverified
_MIN_DATED = 0.6   # share of records that must carry a parseable start

_TITLE_KEYS = ("title", "name", "eventname", "event_name", "summary")
_START_KEYS = ("startdate", "start_date", "starts_at", "startsat", "dtstart",
               "start", "datefrom", "date_from", "begin", "date", "from")
_END_KEYS = ("enddate", "end_date", "ends_at", "endsat", "dtend", "end",
             "dateto", "date_to", "to")
_URL_KEYS = ("url", "link", "permalink", "weburl", "website", "publicurl",
             "eventurl", "event_url")
_VENUE_KEYS = ("venuename", "venue_name", "venue", "location", "locationname",
               "place", "room")
_DESC_KEYS = ("description", "shortdescription", "short_description", "teaser",
              "body", "longdescription")
_ORGANIZER_KEYS = ("organizer", "organiser", "host", "hostfullname", "hostname")
_BOOKING_KEYS = ("bookingurl", "booking_url", "ticketurl", "ticket_url",
                 "registrationurl", "signupurl")
_PRICE_KEYS = ("price", "cheapestprice", "chepeastprice",  # Nexudus ships the typo
               "pricefrom", "price_from", "minprice")


def _datish(value) -> bool:
    """A string that plausibly denotes a date(time) - never a bare id/number."""
    from eventindex.extract import parse_dt

    if not isinstance(value, str) or len(value) < 8:
        return False
    if not any(sep in value for sep in ("-", ".", "/", "T")):
        return False
    return parse_dt(value) is not None


def _pick(record: dict, keys: tuple, want=str):
    lowered = {k.lower(): v for k, v in record.items()}
    for key in keys:
        value = lowered.get(key)
        if isinstance(value, want) and (value or want is not str):
            return value
    return None


def _pick_date(record: dict, keys: tuple) -> str | None:
    lowered = {k.lower(): v for k, v in record.items()}
    for key in keys:
        value = lowered.get(key)
        if _datish(value):
            return value
    return None


def _event_arrays(node, path=()) -> list[tuple[tuple, list[dict]]]:
    """All arrays-of-dicts in the tree whose records look like events.
    Arrays nested inside an accepted array's records are skipped - an
    event's own occurrence list must not double as a second event list."""
    found: list[tuple[tuple, list[dict]]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found += _event_arrays(value, path + (key,))
    elif isinstance(node, list) and node and all(isinstance(r, dict) for r in node):
        dated = sum(
            1 for r in node
            if _pick(r, _TITLE_KEYS) and _pick_date(r, _START_KEYS)
        )
        if dated and dated / len(node) >= _MIN_DATED:
            found.append((path, node))
        else:
            for i, record in enumerate(node):
                found += _event_arrays(record, path + (i,))
    accepted: list[tuple[tuple, list[dict]]] = []
    for path_a, arr in found:
        if not any(path_a[: len(path_b)] == path_b and path_a != path_b
                   for path_b, _ in found):
            accepted.append((path_a, arr))
    return accepted


def _strip_html(value: str) -> str:
    from eventindex.extract.llm_text import html_to_text

    return html_to_text(value.encode()) if "<" in value else value


def _payload(record: dict) -> dict | None:
    from eventindex.extract import field

    title = _pick(record, _TITLE_KEYS)
    starts = _pick_date(record, _START_KEYS)
    if not title or not starts:
        return None
    payload = {"title": field(title, CONFIDENCE),
               "starts_at": field(starts, CONFIDENCE)}
    if ends := _pick_date(record, _END_KEYS):
        payload["ends_at"] = field(ends, CONFIDENCE)
    if url := _pick(record, _URL_KEYS):
        payload["url"] = field(url, CONFIDENCE)
    if venue := _pick(record, _VENUE_KEYS):
        payload["venue_name"] = field(venue, CONFIDENCE)
    if desc := _pick(record, _DESC_KEYS):
        payload["description"] = field(_strip_html(desc)[:2000], CONFIDENCE)
    if organizer := _pick(record, _ORGANIZER_KEYS):
        payload["organizer"] = field(organizer, CONFIDENCE)
    if booking := _pick(record, _BOOKING_KEYS):
        payload["booking_url"] = field(booking, CONFIDENCE)
    price = _pick(record, _PRICE_KEYS, want=(int, float))
    if price is not None and not isinstance(price, bool):
        payload["price_min"] = field(float(price), CONFIDENCE)
    lowered = {k.lower(): v for k, v in record.items()}
    lat, lon = lowered.get("latitude"), lowered.get("longitude")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        payload["lat"] = field(float(lat), CONFIDENCE)
        payload["lon"] = field(float(lon), CONFIDENCE)
    return payload


def parse(content: bytes) -> list[dict]:
    """JSON body -> claim payloads; [] when it isn't JSON or holds no events."""
    try:
        tree = json.loads(content)
    except (ValueError, UnicodeDecodeError):
        return []
    payloads = []
    for _, records in _event_arrays(tree):
        for record in records:
            if (p := _payload(record)) is not None:
                payloads.append(p)
    return payloads
