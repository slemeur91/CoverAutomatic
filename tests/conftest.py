"""Pytest fixtures for CoverAutomatic tests."""
from __future__ import annotations

from typing import Any

import pytest

from custom_components.cover_automatic.models import (
    Condition,
    ConditionType,
    CoverConfig,
    Facade,
    Rule,
    Scenario,
)
from custom_components.cover_automatic.storage import CoverAutomaticStorage


def bind_profile_settings(storage: Any) -> Any:
    """Give a mock storage the real per-profile accessors.

    comfort_settings() / sun_settings() only read attributes: bound to the
    mock, they return the values the test set (comfort_temp_min_b, ...).
    """
    storage.comfort_settings = lambda p: CoverAutomaticStorage.comfort_settings(storage, p)
    storage.sun_settings = lambda p: CoverAutomaticStorage.sun_settings(storage, p)
    return storage


@pytest.fixture
def sample_facade() -> Facade:
    """Create a sample facade for testing."""
    return Facade(
        id="south_facade",
        name="South Facade",
        azimuth_start=135.0,
        azimuth_end=225.0,
        direction="south",
        min_elevation=0.0,
    )


@pytest.fixture
def sample_cover() -> CoverConfig:
    """Create a sample cover configuration for testing."""
    return CoverConfig(
        entity_id="cover.living_room",
        name="Living Room",
        facade_id="south_facade",
        auto_enabled=True,
        pause_duration=120,
    )


@pytest.fixture
def sample_rule() -> Rule:
    """Create a sample rule for testing."""
    return Rule(
        id="sun_shade",
        name="Sun Shade Rule",
        enabled=True,
        priority=10,
        conditions=[
            Condition(
                type=ConditionType.SUN_ON_FACADE,
                params={},
            ),
            Condition(
                type=ConditionType.SUN_ELEVATION_ABOVE,
                params={"value": 15},
            ),
        ],
        target_position=30,
        facade_ids=["south_facade"],
    )


@pytest.fixture
def sample_scenario() -> Scenario:
    """Create a sample scenario for testing."""
    return Scenario(
        id="summer",
        name="Summer Mode",
        icon="mdi:white-balance-sunny",
    )
