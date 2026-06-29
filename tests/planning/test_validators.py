"""Unit tests for planner validation helpers."""

from __future__ import annotations

import pytest
from fiberpath.config.schemas import (
    HelicalLayer,
    HoopLayer,
    MandrelParameters,
    SkipLayer,
    TowParameters,
)
from fiberpath.planning.exceptions import LayerValidationError
from fiberpath.planning.surface import Cone
from fiberpath.planning.validators import (
    validate_cone_helical_layer,
    validate_helical_layer,
    validate_layer,
)

MANDREL = MandrelParameters.model_validate({"diameter": 70.0, "windLength": 100.0})
BASE_LAYER = {
    "windAngle": 35.0,
    "patternNumber": 31,
    "skipIndex": 1,
    "lockDegrees": 180.0,
    "leadInMM": 5.0,
    "leadOutDegrees": 15.0,
}

# Mandrel whose geometry produces num_circuits=39 (divisible by 3) for 45° / 3.5mm tow.
# Used for lockDegrees tests that require patternNumber=3.
MANDREL_45 = MandrelParameters.model_validate({"diameter": 60.0, "windLength": 150.0})
BASE_LAYER_45 = {
    "windAngle": 45.0,
    "patternNumber": 3,
    "skipIndex": 1,
    "lockDegrees": 540.0,
    "leadInMM": 10.0,
    "leadOutDegrees": 30.0,
}
TOW_45 = TowParameters.model_validate({"width": 3.5, "thickness": 0.5})


def test_validate_helical_layer_rejects_skip_index_ge_pattern() -> None:
    layer = HelicalLayer.model_validate({**BASE_LAYER, "skipIndex": 4, "patternNumber": 4})
    tow = TowParameters.model_validate({"width": 6.0, "thickness": 0.5})

    with pytest.raises(LayerValidationError):
        validate_helical_layer(1, layer, MANDREL, tow)


def test_validate_helical_layer_rejects_non_divisible_circuit_pattern() -> None:
    # With this fixture geometry/tow width, num_circuits computes to 31.
    # patternNumber=4 must fail because 31 % 4 != 0.
    layer = HelicalLayer.model_validate({**BASE_LAYER, "patternNumber": 4, "skipIndex": 1})
    tow = TowParameters.model_validate({"width": 6.0, "thickness": 0.5})

    with pytest.raises(LayerValidationError, match="not divisible by patternNumber"):
        validate_helical_layer(2, layer, MANDREL, tow)


def test_validate_helical_layer_rejects_lead_in_exceeding_wind_length() -> None:
    # leadInMM >= the mandrel windLength drives the carriage off the end of the
    # mandrel into negative coordinates and inverts the main-pass rotation
    # (the machine could ram an end-stop). MANDREL.windLength is 100mm.
    layer = HelicalLayer.model_validate({**BASE_LAYER, "leadInMM": 150.0})
    tow = TowParameters.model_validate({"width": 6.0, "thickness": 0.5})

    with pytest.raises(LayerValidationError, match="leadInMM"):
        validate_helical_layer(1, layer, MANDREL, tow)


def test_validate_helical_layer_allows_valid_parameters() -> None:
    layer = HelicalLayer.model_validate(BASE_LAYER)
    tow = TowParameters.model_validate({"width": 6.0, "thickness": 0.5})

    result = validate_helical_layer(2, layer, MANDREL, tow)

    # Returned object comes directly from compute_helical_kinematics; ensure
    # we get a positive circuit count to prove the happy path executes.
    assert result.num_circuits > 0


# ---------------------------------------------------------------------------
# lockDegrees coverage validation
# ---------------------------------------------------------------------------


def test_validate_helical_layer_rejects_lock_degrees_condition1() -> None:
    # lock=270, P=3: (2*270) % 360 = 180; 180 % 120 = 60 != 0.
    # Condition 1 fails: per-circuit advance is not a multiple of slot width.
    layer = HelicalLayer.model_validate({**BASE_LAYER_45, "lockDegrees": 270.0})
    with pytest.raises(LayerValidationError, match="lockDegrees"):
        validate_helical_layer(1, layer, MANDREL_45, TOW_45)


def test_validate_helical_layer_rejects_lock_degrees_condition2() -> None:
    # lock=120, P=3: (2*120) % 360 = 240; 240 % 120 = 0 (condition 1 passes).
    # slot_step = (240 + 1*120) % 360 = 0; j = 0; gcd(0, 3) = 3 != 1.
    # Condition 2 fails: all in-pattern circuits alias onto the same position.
    layer = HelicalLayer.model_validate({**BASE_LAYER_45, "lockDegrees": 120.0})
    with pytest.raises(LayerValidationError, match="lockDegrees"):
        validate_helical_layer(1, layer, MANDREL_45, TOW_45)


def test_validate_helical_layer_accepts_lock_degrees_540_pattern3() -> None:
    # lock=540, P=3: per_circuit_mod=0, slot_step=120, j=1, gcd(1,3)=1.
    layer = HelicalLayer.model_validate({**BASE_LAYER_45, "lockDegrees": 540.0})
    result = validate_helical_layer(1, layer, MANDREL_45, TOW_45)
    assert result.num_circuits > 0


def test_validate_helical_layer_accepts_lock_180_pattern1() -> None:
    # lock=180 satisfies both conditions for any patternNumber.
    # BASE_LAYER uses P=31, lock=180 and is the canonical valid fixture.
    layer = HelicalLayer.model_validate(BASE_LAYER)
    tow = TowParameters.model_validate({"width": 6.0, "thickness": 0.5})
    result = validate_helical_layer(1, layer, MANDREL, tow)
    assert result.num_circuits > 0


# ---------------------------------------------------------------------------
# validate_layer: the single validation surface over the primitive
# ---------------------------------------------------------------------------

_TOW = TowParameters.model_validate({"width": 6.0, "thickness": 0.5})


def test_validate_layer_returns_kinematics_for_helical() -> None:
    result = validate_layer(1, HelicalLayer.model_validate(BASE_LAYER), MANDREL, _TOW)
    assert result is not None
    assert result.num_circuits > 0


def test_validate_layer_propagates_helical_coverage_errors() -> None:
    layer = HelicalLayer.model_validate({**BASE_LAYER, "skipIndex": 4, "patternNumber": 4})
    with pytest.raises(LayerValidationError):
        validate_layer(1, layer, MANDREL, _TOW)


def test_validate_layer_passes_through_hoop_and_skip_with_no_kinematics() -> None:
    # Hoop and skip carry no coverage pattern, so the uniform entry validates
    # them (no error) and returns no kinematics.
    assert validate_layer(1, HoopLayer(terminal=False), MANDREL, _TOW) is None
    assert validate_layer(1, HoopLayer(terminal=True), MANDREL, _TOW) is None
    assert (
        validate_layer(1, SkipLayer.model_validate({"mandrelRotation": 45.0}), MANDREL, _TOW)
        is None
    )


# ---------------------------------------------------------------------------
# cone helical validation
# ---------------------------------------------------------------------------

# windAngle=30 on this frustum gives num_circuits=45 (divisible by patternNumber=3).
_CONE = Cone(r0=49.0, r1=27.0, length=120.0)
_CONE_LAYER = HelicalLayer.model_validate(
    {
        "windAngle": 30.0,
        "patternNumber": 3,
        "skipIndex": 1,
        "lockDegrees": 180.0,
        "leadInMM": 5.0,
        "leadOutDegrees": 15.0,
    }
)


def test_validate_cone_helical_layer_returns_kinematics() -> None:
    result = validate_cone_helical_layer(1, _CONE_LAYER, _CONE, _TOW)
    assert result.num_circuits == 45
    assert result.num_circuits % _CONE_LAYER.pattern_number == 0


def test_validate_cone_rejects_expanding_frustum() -> None:
    with pytest.raises(LayerValidationError, match="reducing frustum"):
        validate_cone_helical_layer(1, _CONE_LAYER, Cone(r0=27.0, r1=49.0, length=120.0), _TOW)


def test_validate_cone_rejects_unreachable_angle() -> None:
    # asin(27/49) ~= 33.4 deg is the steepest reachable angle on this frustum.
    steep = HelicalLayer.model_validate(
        {**_CONE_LAYER.model_dump(by_alias=True), "windAngle": 40.0}
    )
    with pytest.raises(LayerValidationError, match="too steep"):
        validate_cone_helical_layer(1, steep, _CONE, _TOW)


def test_validate_cone_rejects_non_divisible_circuit_pattern() -> None:
    # num_circuits=45; patternNumber=2 must fail because 45 % 2 != 0 (skip 1 is coprime).
    layer = HelicalLayer.model_validate(
        {**_CONE_LAYER.model_dump(by_alias=True), "patternNumber": 2, "skipIndex": 1}
    )
    with pytest.raises(LayerValidationError, match="not divisible by patternNumber"):
        validate_cone_helical_layer(1, layer, _CONE, _TOW)
