"""Typed configuration models shared across the FiberPath toolchain."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt, model_validator


class BaseFiberPathModel(BaseModel):
    """Base class that applies shared Pydantic configuration."""

    # allow_inf_nan=False rejects NaN/Infinity on every float field. JSON
    # permits the NaN/Infinity literals, and unguarded non-finite values
    # otherwise propagate into the generated G-code (a literal "Anan" axis word)
    # or overflow math.ceil in the planner (uncaught OverflowError).
    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class VonKarmanProfile(BaseFiberPathModel):
    """Von Kármán (LD-Haack) nose profile (schemaVersion 1.2+).

    A non-developable surface of revolution: radius runs from the mandrel
    ``diameter`` at the base (z=0) to 0 at the tip (z=``windLength``). The profile
    carries only its ``type`` discriminator — base radius comes from ``diameter`` and
    axial length from ``windLength`` (no duplicated dimensions), mirroring how
    ``endDiameter`` reuses those fields. ``type`` lets other profiles (domes) be added
    additively later.
    """

    type: Literal["vonKarman"]


class MandrelParameters(BaseFiberPathModel):
    diameter: PositiveFloat
    wind_length: PositiveFloat = Field(alias="windLength")
    # Optional small-end diameter at z=windLength (schemaVersion 1.1+). When set
    # and smaller than `diameter`, the mandrel is a reducing cone/frustum (large
    # end `diameter` at z=0); absent reproduces a cylinder. Additive: older files
    # omit it and parse unchanged.
    end_diameter: PositiveFloat | None = Field(default=None, alias="endDiameter")
    # Optional surface-of-revolution profile (schemaVersion 1.2+). When set, it
    # fully defines the mandrel surface (base radius = `diameter`/2), so it is
    # mutually exclusive with `endDiameter`. Absent reproduces a cylinder/cone.
    profile: VonKarmanProfile | None = Field(default=None)

    @model_validator(mode="after")
    def _reject_profile_with_end_diameter(self) -> MandrelParameters:
        if self.profile is not None and self.end_diameter is not None:
            raise ValueError(
                "mandrelParameters.profile and endDiameter are mutually exclusive: a "
                "profile fully defines the surface (its base radius is diameter/2). "
                "Set one or the other, not both."
            )
        return self


class TowParameters(BaseFiberPathModel):
    width: PositiveFloat
    thickness: PositiveFloat


class HoopLayer(BaseFiberPathModel):
    wind_type: Literal["hoop"] = Field(alias="windType", default="hoop")
    terminal: bool = False


class HelicalLayer(BaseFiberPathModel):
    wind_type: Literal["helical"] = Field(alias="windType", default="helical")
    wind_angle: PositiveFloat = Field(alias="windAngle")
    pattern_number: PositiveInt = Field(alias="patternNumber")
    skip_index: PositiveInt = Field(alias="skipIndex")
    lock_degrees: PositiveFloat = Field(alias="lockDegrees")
    lead_in_mm: PositiveFloat = Field(alias="leadInMM")
    lead_out_degrees: PositiveFloat = Field(alias="leadOutDegrees")
    skip_initial_near_lock: bool = Field(default=False, alias="skipInitialNearLock")
    # Non-geodesic friction ratio λ = k_g/k_n for the laid tow (schemaVersion 1.3+). 0 (the
    # default) is the geodesic path; > 0 lets the pass climb past the geodesic turnaround
    # toward a Von Kármán tip, up to the machine slip limit μ (MachineProfile.slipLimit).
    # Additive: older files omit it and parse unchanged. Only meaningful on a profile mandrel
    # (the planner rejects a non-zero value on a cylinder/cone). Not PositiveFloat: 0 is valid.
    friction_lambda: float = Field(default=0.0, alias="frictionLambda", ge=0.0)


class SkipLayer(BaseFiberPathModel):
    wind_type: Literal["skip"] = Field(alias="windType", default="skip")
    mandrel_rotation: float = Field(alias="mandrelRotation")


LayerModel = Annotated[
    HoopLayer | HelicalLayer | SkipLayer,
    Field(discriminator="wind_type"),
]


class WindDefinition(BaseFiberPathModel):
    # The .wind format version. Absent is treated as the legacy 1.0 (default);
    # any 1.x minor is accepted (additive evolution), while an incompatible
    # major (2.0+) is rejected by the pattern. Bump the minor for additive
    # changes; a major bump is a breaking format change handled separately.
    schema_version: str = Field(
        default="1.0",
        alias="schemaVersion",
        pattern=r"^1\.\d+$",
        title="Schema Version",
        description="Version of the .wind file format schema (1.x).",
    )
    layers: list[LayerModel]
    mandrel_parameters: Annotated[MandrelParameters, Field(alias="mandrelParameters")]
    tow_parameters: Annotated[TowParameters, Field(alias="towParameters")]
    default_feed_rate: PositiveFloat = Field(alias="defaultFeedRate")
