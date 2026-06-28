"""Typed configuration models shared across the FiberPath toolchain."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt


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


class MandrelParameters(BaseFiberPathModel):
    diameter: PositiveFloat
    wind_length: PositiveFloat = Field(alias="windLength")


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
