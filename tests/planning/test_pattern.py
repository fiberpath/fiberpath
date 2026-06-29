"""Unit tests for the declarative pattern primitive (Stage 2 / S1)."""

from __future__ import annotations

import pytest
from fiberpath.config.schemas import HelicalLayer, HoopLayer, SkipLayer
from fiberpath.planning.pattern import HOOP_ALPHA_DEG, PatternSpec, pattern_spec

HELICAL = {
    "windAngle": 35.0,
    "patternNumber": 31,
    "skipIndex": 2,
    "lockDegrees": 180.0,
    "leadInMM": 5.0,
    "leadOutDegrees": 15.0,
    "skipInitialNearLock": True,
}


def test_hoop_maps_to_alpha_90_laying_spec() -> None:
    spec = pattern_spec(HoopLayer.model_validate({"terminal": True}))

    assert spec.lay is True
    assert spec.alpha_deg == HOOP_ALPHA_DEG
    assert spec.pattern_number == 1
    assert spec.lock_degrees == 180.0
    assert spec.terminal is True
    assert spec.reposition_degrees == 0.0


def test_helical_maps_fields_through_verbatim() -> None:
    layer = HelicalLayer.model_validate(HELICAL)
    spec = pattern_spec(layer)

    assert spec == PatternSpec(
        lay=True,
        alpha_deg=35.0,
        pattern_number=31,
        skip_index=2,
        lock_degrees=180.0,
        lead_in_mm=5.0,
        lead_out_degrees=15.0,
        terminal=False,
        skip_initial_near_lock=True,
        reposition_degrees=0.0,
    )


def test_skip_maps_to_non_laying_reposition() -> None:
    spec = pattern_spec(SkipLayer.model_validate({"mandrelRotation": 123.5}))

    assert spec.lay is False
    assert spec.reposition_degrees == 123.5


def test_pattern_spec_rejects_unknown_layer() -> None:
    with pytest.raises(TypeError):
        pattern_spec(object())  # type: ignore[arg-type]
