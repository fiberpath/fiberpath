"""Tests for the machine-profile contract (#197)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fiberpath.config import (
    MachineProfile,
    MachineProfileError,
    default_machine_profile,
    load_machine_profile,
)
from fiberpath.gcode.dialects import MARLIN_XAB_STANDARD, dialect_from_profile
from pydantic import ValidationError


def test_default_profile_is_marlin_xab() -> None:
    profile = default_machine_profile()
    assert profile.id == "marlin-xab"
    assert profile.profile_version == "1.0"
    assert profile.controller == "marlin"
    assert profile.units == "mm"
    assert profile.feed_mode == "G94"
    assert profile.required_gcodes == ("G0", "G21", "G90", "G92", "G94")
    assert (
        profile.axis_mapping.carriage,
        profile.axis_mapping.mandrel,
        profile.axis_mapping.delivery_head,
    ) == ("X", "A", "B")


def test_default_profile_reproduces_legacy_dialect() -> None:
    """The derived dialect must match the historical X/A/B constant exactly so
    that existing G-code output stays byte-identical."""
    dialect = dialect_from_profile(default_machine_profile())
    assert dialect.axis_mapping == MARLIN_XAB_STANDARD.axis_mapping
    assert dialect.units == MARLIN_XAB_STANDARD.units
    assert dialect.feed_mode == MARLIN_XAB_STANDARD.feed_mode


def test_profile_is_immutable() -> None:
    profile = default_machine_profile()
    with pytest.raises(ValidationError, match="frozen"):
        profile.controller = "grbl"  # type: ignore[misc]


def test_loads_a_profile_from_disk(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text(
        json.dumps(
            {
                "id": "x",
                "name": "X",
                "controller": "marlin",
                "axisMapping": {"carriage": "X", "mandrel": "C", "deliveryHead": "A"},
                "requiredGcodes": ["G0"],
            }
        ),
        encoding="utf-8",
    )
    profile = load_machine_profile(path)
    assert profile.axis_mapping.mandrel == "C"
    assert profile.profile_version == "1.0"  # defaulted


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(MachineProfileError, match="No machine profile"):
        load_machine_profile(tmp_path / "nope.json")


def test_invalid_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(MachineProfileError, match="Invalid JSON"):
        load_machine_profile(path)


def _base(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "x",
        "name": "X",
        "controller": "marlin",
        "requiredGcodes": ["G0", "G92"],
    }
    payload.update(overrides)
    return payload


def test_incompatible_major_version_is_rejected() -> None:
    with pytest.raises(MachineProfileError, match="failed validation"):
        load_profile_payload(_base(profileVersion="2.0"))


def test_non_distinct_axes_are_rejected() -> None:
    with pytest.raises(MachineProfileError, match="distinct"):
        load_profile_payload(
            _base(axisMapping={"carriage": "X", "mandrel": "X", "deliveryHead": "B"})
        )


def test_multi_letter_axis_is_rejected() -> None:
    with pytest.raises(MachineProfileError, match="single uppercase"):
        load_profile_payload(
            _base(axisMapping={"carriage": "XX", "mandrel": "A", "deliveryHead": "B"})
        )


def test_empty_required_gcodes_is_rejected() -> None:
    with pytest.raises(MachineProfileError, match="failed validation"):
        load_profile_payload(_base(requiredGcodes=[]))


def test_non_gcode_required_entry_is_rejected() -> None:
    with pytest.raises(MachineProfileError, match="failed validation"):
        load_profile_payload(_base(requiredGcodes=["G0", "nonsense"]))


def test_non_mm_units_is_rejected() -> None:
    # inch is not honorable today (no G20 emitted), so the contract must reject it.
    with pytest.raises(MachineProfileError, match="failed validation"):
        load_profile_payload(_base(units="inch"))


def load_profile_payload(payload: dict[str, object]) -> MachineProfile:
    """Validate an in-memory payload via the same error contract as the loader."""
    from fiberpath.config.machine_profile import _validate

    return _validate(payload, "test payload")
