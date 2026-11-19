"""Rule action "do nothing" (Rule.no_action).

A winning "do nothing" rule leaves the cover where it is and hides the
lower rules (shading included); its target positions are kept for when the
option is unchecked. Never a safety rule.
"""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.cover_automatic.models import CoverTarget, CoverStatus, Rule
from tests.test_engine import (  # noqa: F401 -- pytest fixtures
    engine,
    mock_hass,
    mock_storage,
    test_cover,
)

COVER = "cover.living_room"


def _rule(rule_id, priority, **kw) -> Rule:
    return Rule(id=rule_id, name=rule_id.title(), priority=priority, cover_ids=[COVER], **kw)


class TestEngine:
    def test_no_action_rule_wins_without_position(self, engine, mock_storage, test_cover) -> None:
        mock_storage.rules = {
            "hold": _rule("hold", 50, no_action=True, target_position=30, target_tilt_position=40),
            "shade": _rule("shade", 10, target_position=0),
        }
        result = engine.evaluate_cover(test_cover)
        assert result.rule_id == "hold"
        assert result.position is None and result.tilt_position is None

    def test_lower_no_action_rule_does_not_block(self, engine, mock_storage, test_cover) -> None:
        mock_storage.rules = {
            "hold": _rule("hold", 5, no_action=True),
            "shade": _rule("shade", 10, target_position=0),
        }
        result = engine.evaluate_cover(test_cover)
        assert result.rule_id == "shade" and result.position == 0

    def test_not_considered_as_safety(self, engine, mock_storage, test_cover) -> None:
        mock_storage.rules = {"hold": _rule("hold", 50, no_action=True)}
        assert engine.evaluate_cover(test_cover, safety_only=True) is None


class TestModel:
    def test_round_trip_keeps_targets(self) -> None:
        rule = Rule.from_dict({"id": "r", "name": "R", "no_action": True,
                               "target_position": 30, "target_tilt_position": 40})
        assert rule.no_action is True
        assert rule.target_position == 30 and rule.target_tilt_position == 40
        assert rule.to_dict()["no_action"] is True

    def test_old_rule_is_a_position_rule(self) -> None:
        assert Rule.from_dict({"id": "r", "name": "R"}).no_action is False

    def test_never_safety(self) -> None:
        rule = Rule.from_dict({"id": "r", "name": "R", "no_action": True, "safety": True})
        assert rule.safety is False


class TestCoordinator:
    @pytest.fixture
    def coord(self):
        from custom_components.cover_automatic.coordinator import CoverAutomaticCoordinator
        coord = CoverAutomaticCoordinator.__new__(CoverAutomaticCoordinator)
        coord._last_matching_rules = {}
        coord.storage = MagicMock()
        coord.storage.rules = {"hold": _rule("hold", 50, no_action=True)}
        coord.log_storage = MagicMock()
        return coord

    def test_logged_as_do_nothing(self, coord) -> None:
        coord._log_rule_change(COVER, "hold", None)
        args = coord.log_storage.add_entry.call_args.args
        assert args[3] == {"key": "rule_no_action", "rule_id": "hold", "rule_name": "Hold"}

    def test_logged_once(self, coord) -> None:
        coord._log_rule_change(COVER, "hold", None)
        coord._log_rule_change(COVER, "hold", None)
        assert coord.log_storage.add_entry.call_count == 1

    def test_no_pending_rule_while_driving(self, coord) -> None:
        """An AUTO cover held by a "do nothing" rule shows that rule, no pending one."""
        coord.storage.enabled = True
        target = CoverTarget(position=None, rule_id="hold", rule_name="Hold")
        assert coord._pending_rule(MagicMock(), CoverStatus.AUTO, target) == {}
