"""Value checkpoint (2026-07-08): the agent's yield estimate may extend the
session rings, but only through the deterministic gate and never past the
hard rings. LLM stubbed - tests must never spend."""

from types import SimpleNamespace

from eventindex import config
from eventindex.discovery import onboard


def test_extended_rings_scale_and_clamp():
    # small yield: base rings, no extension
    cap, turns, wall = onboard._extended_rings(10)
    assert (cap, turns, wall) == (config.ONBOARD_SESSION_CAP_EUR,
                                  config.ONBOARD_MAX_TURNS,
                                  config.ONBOARD_WALL_CLOCK_S)
    # big yield: everything clamps to the hard rings
    cap, turns, wall = onboard._extended_rings(500)
    assert cap == config.ONBOARD_HARD_CAP_EUR
    assert turns == config.ONBOARD_HARD_MAX_TURNS
    assert wall == config.ONBOARD_HARD_WALL_CLOCK_S
    # mid yield: proportional, monotonic between the rings
    cap, turns, wall = onboard._extended_rings(40)  # 40 * 0.03 = 1.20
    assert config.ONBOARD_SESSION_CAP_EUR < cap < config.ONBOARD_HARD_CAP_EUR
    assert config.ONBOARD_MAX_TURNS < turns <= config.ONBOARD_HARD_MAX_TURNS


def _checkpoint_with(monkeypatch, reply: str):
    monkeypatch.setattr(
        onboard.llm, "chat",
        lambda tx, messages, **kw: SimpleNamespace(content=reply),
    )
    return onboard._value_checkpoint(
        None, [], onboard.Session(), "mini", {"id": None}, None
    )


def test_checkpoint_extends_on_credible_estimate(monkeypatch):
    cap, turns, wall = _checkpoint_with(monkeypatch, (
        '{"expected_events_per_crawl": 100, "expects_success": true, '
        '"rationale": "large calendar"}'
    ))
    assert cap == config.ONBOARD_HARD_CAP_EUR


def test_checkpoint_fails_closed_on_garbage(monkeypatch):
    cap, turns, wall = _checkpoint_with(monkeypatch, "I think it looks promising!")
    assert (cap, turns, wall) == (config.ONBOARD_SESSION_CAP_EUR,
                                  config.ONBOARD_MAX_TURNS,
                                  config.ONBOARD_WALL_CLOCK_S)


def test_checkpoint_keeps_base_when_agent_expects_failure(monkeypatch):
    cap, _, _ = _checkpoint_with(monkeypatch, (
        '{"expected_events_per_crawl": 100, "expects_success": false, '
        '"rationale": "login wall"}'
    ))
    assert cap == config.ONBOARD_SESSION_CAP_EUR
