"""Regression tests from the 2026-07-20 red-team audit: each pins the exact
production defect class with the real payloads/wording that slipped through."""

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from eventindex.extract import is_non_event, sanity_filter
from eventindex.resolve.rebuild import (Claim, _recurrence_of,
                                        _reconcile_titled_weekday,
                                        _title_weekday)

VIENNA = ZoneInfo("Europe/Vienna")


def _claim(title, starts, recurrence):
    return Claim(
        id=uuid.uuid4(), source_id=uuid.uuid4(), fingerprint="fp",
        extracted_at=datetime.now(timezone.utc),
        payload={"title": {"value": title},
                 "starts_at": {"value": starts.isoformat()},
                 "recurrence": {"value": recurrence}},
        trust=0.8, source_url="https://x.at", source_lat=None,
        source_lon=None, title=title, starts_at=starts,
    )


_REC = {"freq": "daily", "weekday": None, "week_of_month": None,
        "interval": 1, "time": "08:00", "duration_minutes": None,
        "except_holidays": [], "valid_from": None, "valid_until": None,
        "as_stated": "täglich in Christkönig"}


def test_weekday_titled_daily_rule_coerces_to_weekly():
    # the live defect: Freitag-titled mass + 'täglich' group description
    friday = datetime(2026, 7, 17, 8, 0, tzinfo=VIENNA)  # a Friday
    c = _claim("Wochentagsmesse (Eucharistiefeier) - Freitag", friday, _REC)
    rec = _recurrence_of(c)
    assert rec is not None
    assert rec.freq == "weekly"
    assert rec.weekday == "FR"


def test_weekday_titled_daily_rule_fails_closed_on_anchor_mismatch():
    tuesday = datetime(2026, 7, 14, 8, 0, tzinfo=VIENNA)
    c = _claim("Wochentagsmesse - Freitag", tuesday, _REC)
    assert _recurrence_of(c) is None


def test_contradicting_weekly_rule_fails_closed():
    friday = datetime(2026, 7, 17, 8, 0, tzinfo=VIENNA)
    rec = _REC | {"freq": "weekly", "weekday": "TU",
                  "as_stated": "jeden Dienstag"}
    c = _claim("Gebet am Freitag", friday, rec)
    assert _recurrence_of(c) is None


def test_title_weekday_detection_bounds():
    assert _title_weekday("Brunch am Sonntag") == "SU"
    # compounds stay unmatched: a named one-off must not be coerced
    assert _title_weekday("Sonntagsbrunch im Hof") is None
    assert _title_weekday("Wochentagsmesse - Freitag") == "FR"
    assert _title_weekday("Konzert am Montag oder Dienstag") is None  # two
    assert _title_weekday("Freitagskonzert") is None  # compound, no boundary
    assert _title_weekday("Sommerfest") is None


def test_untitled_rules_pass_through_unchanged():
    friday = datetime(2026, 7, 17, 19, 0, tzinfo=VIENNA)
    rec = _REC | {"as_stated": "täglich geöffnet"}
    c = _claim("Sommerkino im Hof", friday, rec)
    out = _recurrence_of(c)
    assert out is not None and out.freq == "daily"


def test_announcements_are_non_events():
    # the live Stahlwelt defect
    assert is_non_event("Wiedereröffnung der voestalpine Stahlwelt - Touren ab 13. Juli")
    assert is_non_event("Neueröffnung im Zentrum")
    assert is_non_event("Wir haben jetzt wieder geöffnet")
    # a dated celebration stays an event (German compound keeps the boundary)
    assert not is_non_event("Wiedereröffnungsfeier mit Livemusik")
    assert not is_non_event("Sommerkonzert der Stadtkapelle")
