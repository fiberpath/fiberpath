"""The machine-profile contract: what a winder must satisfy to run FiberPath output.

A :class:`MachineProfile` is a versioned, validated description of a target
controller — its axis lettering, the units/feed semantics FiberPath assumes, and
the G-code opcodes the planner emits (which the controller must support). It is
the seed of the compatibility spec tracked in #197; the planner consumes a
profile instead of a hardcoded dialect constant.

The bundled ``marlin-xab`` profile (loaded by :func:`default_machine_profile`) is
the canonical Marlin X/A/B target and reproduces the historical
``MARLIN_XAB_STANDARD`` dialect exactly, so existing G-code output is unchanged.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Annotated

from pydantic import (
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from .schemas import BaseFiberPathModel

#: Resource name of the bundled default profile under ``fiberpath/profiles``.
_DEFAULT_PROFILE_RESOURCE = "marlin_xab.json"


class MachineProfileError(RuntimeError):
    """Raised when a machine profile cannot be loaded or fails validation."""


class ProfileAxisMapping(BaseFiberPathModel):
    """Logical winder axes mapped to G-code axis letters."""

    # frozen: a profile is an immutable value, so the cached default is safe to share.
    model_config = ConfigDict(frozen=True)

    carriage: str = "X"  # linear motion along the mandrel
    mandrel: str = "A"  # mandrel rotation
    delivery_head: str = Field(default="B", alias="deliveryHead")  # delivery-head rotation

    @field_validator("carriage", "mandrel", "delivery_head")
    @classmethod
    def _single_uppercase_letter(cls, value: str) -> str:
        if len(value) != 1 or not value.isascii() or not value.isalpha() or not value.isupper():
            raise ValueError(f"axis letter must be a single uppercase letter A-Z, got {value!r}")
        return value

    @model_validator(mode="after")
    def _axes_distinct(self) -> ProfileAxisMapping:
        letters = (self.carriage, self.mandrel, self.delivery_head)
        if len(set(letters)) != len(letters):
            raise ValueError(
                f"carriage/mandrel/deliveryHead must be distinct axis letters, got {letters}"
            )
        return self


class MachineProfile(BaseFiberPathModel):
    """A versioned compatibility contract for a target winder/controller."""

    model_config = ConfigDict(frozen=True)

    # profileVersion mirrors the .wind schemaVersion policy: absent -> 1.0, any 1.x
    # minor is accepted (additive evolution), an incompatible major (2.0+) is rejected.
    profile_version: str = Field(
        default="1.0",
        alias="profileVersion",
        pattern=r"^1\.\d+$",
        description="Version of the machine-profile schema (1.x).",
    )
    id: str = Field(description="Stable slug identifying this profile, e.g. 'marlin-xab'.")
    name: str = Field(description="Human-readable profile name.")
    controller: str = Field(description="Controller/firmware family, e.g. 'marlin'.")
    # mm-only: FiberPath authors mm coordinates and never emits G20/G21, so a
    # non-mm value would be a contract the planner cannot honor. Widen this only
    # when unit conversion (and the matching mode-setting code) actually exists.
    units: str = Field(
        default="mm",
        pattern=r"^mm$",
        description="Coordinate units; FiberPath emits mm only, so the controller must use mm.",
    )
    feed_mode: str = Field(
        default="G94",
        alias="feedMode",
        pattern=r"^G94$",
        description="Feed-rate mode the controller must use (units per minute).",
    )
    axis_mapping: ProfileAxisMapping = Field(
        default_factory=ProfileAxisMapping,
        alias="axisMapping",
    )
    # tuple (not list): a frozen profile is an immutable value, and the bundled
    # default is cached + shared, so the sequence must not be mutable either.
    # Each entry is a G-/M-code opcode (e.g. G0, G92, M3), so empties/typos are rejected.
    required_gcodes: tuple[Annotated[str, StringConstraints(pattern=r"^[GM]\d+$")], ...] = Field(
        alias="requiredGcodes",
        min_length=1,
        description="G-code opcodes the planner emits; a compatible controller must support all.",
    )
    # The slip limit μ (profileVersion 1.1+): the max sustainable |k_g/k_n| before a laid tow
    # slips on this machine+material setup. It bounds a layer's non-geodesic frictionLambda (the
    # planner rejects frictionLambda > slipLimit). A per-setup CONTACT limit — recalibrate per
    # material/tension; the default 0.2 is a realistic dry-ish value that leaves headroom.
    # Additive: profiles that omit it get the default. See docs/guides/machine-profile.md.
    # Upper bound 0.5: the non-geodesic integrator is validated (converged, platform-stable) over
    # λ ∈ [0, 0.5], which already reaches within ~1 mm of the tip; μ > 0.5 pushes λ into a regime
    # where the cap is not yet numerically stable. Physically 0.5 is already a high dry limit.
    slip_limit: float = Field(
        default=0.2,
        alias="slipLimit",
        gt=0.0,
        le=0.5,
        description="Friction slip limit μ = max |k_g/k_n| a tow holds; bounds frictionLambda.",
    )


def _validate(payload: object, source: str) -> MachineProfile:
    try:
        return MachineProfile.model_validate(payload)
    except ValidationError as exc:
        raise MachineProfileError(f"Machine profile {source} failed validation: {exc}") from exc


def load_machine_profile(path: str | Path) -> MachineProfile:
    """Load, parse, and validate a machine-profile JSON file."""
    location = Path(path)
    if not location.exists():
        raise MachineProfileError(f"No machine profile found at {location}")
    try:
        raw = location.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise MachineProfileError(f"Could not read machine profile at {location}: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MachineProfileError(f"Invalid JSON in {location}: {exc}") from exc
    return _validate(payload, f"at {location}")


@lru_cache(maxsize=1)
def default_machine_profile() -> MachineProfile:
    """Return the bundled canonical ``marlin-xab`` profile (cached, immutable)."""
    raw = (
        resources.files("fiberpath.profiles").joinpath(_DEFAULT_PROFILE_RESOURCE).read_text("utf-8")
    )
    return _validate(json.loads(raw), f"bundled {_DEFAULT_PROFILE_RESOURCE}")
