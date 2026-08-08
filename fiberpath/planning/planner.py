"""High-level wind planning orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from fiberpath.config import MachineProfile, WindDefinition, default_machine_profile
from fiberpath.config.schemas import HelicalLayer, HoopLayer
from fiberpath.gcode.dialects import dialect_from_profile
from fiberpath.gcode.serializer import serialize

from .calculations import ConeHelicalKinematics, HelicalKinematics, ProfileHelicalKinematics
from .exceptions import LayerValidationError
from .helpers import Axis
from .ir import Move, MoveKind, Program, ProgramMeta
from .layer_strategies import build_layer_summary, dispatch_layer
from .machine import WinderMachine
from .metrics import nominal_metrics
from .surface import Cone, VonKarman, surface_from_mandrel
from .validators import (
    validate_cone_helical_layer,
    validate_layer,
    validate_layer_sequence,
    validate_profile_helical_layer,
)


@dataclass(slots=True)
class PlanOptions:
    verbose: bool = False
    # The target machine profile (the compatibility contract); defaults to the
    # bundled Marlin X/A/B profile. The planner derives the G-code dialect from it.
    profile: MachineProfile = field(default_factory=default_machine_profile)


@dataclass(slots=True)
class LayerMetrics:
    index: int
    wind_type: str
    commands: int
    time_s: float
    cumulative_time_s: float
    tow_m: float
    cumulative_tow_m: float
    terminal: bool


@dataclass(slots=True)
class PlanResult:
    commands: list[str]
    total_time_s: float
    total_tow_m: float
    layers: list[LayerMetrics]


def plan_wind(definition: WindDefinition, options: PlanOptions | None = None) -> PlanResult:
    options = options or PlanOptions()
    dialect = dialect_from_profile(options.profile)
    machine = WinderMachine(
        mandrel_diameter=definition.mandrel_parameters.diameter,
        verbose_output=options.verbose,
        dialect=dialect,
    )

    machine.set_feed_rate(definition.default_feed_rate)
    encountered_terminal = False
    mandrel_diameter = definition.mandrel_parameters.diameter

    # (index, wind_type, terminal, pre_count, post_count) per layer; metrics are
    # computed from the recorded Moves after the loop via the single O1 model.
    layer_records: list[tuple[int, str, bool, int, int]] = []

    for index, layer in enumerate(definition.layers, start=1):
        validate_layer_sequence(index, encountered_terminal)

        # Per-layer mandrel copy: model_copy preserves every field (endDiameter,
        # profile, ...) so a new schema field can never be silently dropped here.
        current_mandrel = definition.mandrel_parameters.model_copy()

        # Validate over the declarative primitive, keyed on the mandrel surface.
        # Cone/profile helical return their own kinematics; cylinder helical returns
        # helical kinematics; hoop/skip return None. All reused by dispatch.
        surface = surface_from_mandrel(current_mandrel)
        helical_kinematics: HelicalKinematics | None = None
        cone_kinematics: ConeHelicalKinematics | None = None
        profile_kinematics: ProfileHelicalKinematics | None = None
        if isinstance(surface, Cone):
            if isinstance(layer, HoopLayer):
                raise LayerValidationError(index, "hoop layers on a cone are not supported yet")
            if isinstance(layer, HelicalLayer):
                cone_kinematics = validate_cone_helical_layer(
                    index, layer, surface, definition.tow_parameters
                )
        elif isinstance(surface, VonKarman):
            if isinstance(layer, HoopLayer):
                raise LayerValidationError(
                    index, "hoop layers on a profile surface are not supported yet"
                )
            if isinstance(layer, HelicalLayer):
                profile_kinematics = validate_profile_helical_layer(
                    index, layer, surface, definition.tow_parameters
                )
        else:
            helical_kinematics = validate_layer(
                index, layer, current_mandrel, definition.tow_parameters
            )

        summary = build_layer_summary(index, len(definition.layers), layer)
        machine.insert_comment(summary)
        if profile_kinematics is not None:
            # Surface the expected bare polar cap to the operator: a geodesic turns
            # around at the Clairaut radius, so it cannot reach the tip. Full tip
            # coverage needs non-geodesic winding (Phase 2, #327).
            machine.insert_comment(
                f"\tBare polar cap: ~{profile_kinematics.cap_diameter:.2f} mm diameter "
                "(geodesic turnaround; full tip coverage requires non-geodesic winding)"
            )

        pre_count = len(machine.get_moves())
        dispatch_layer(
            machine,
            layer,
            current_mandrel,
            definition.tow_parameters,
            helical_kinematics=helical_kinematics,
            cone_kinematics=cone_kinematics,
            profile_kinematics=profile_kinematics,
        )
        terminal = bool(getattr(layer, "terminal", False))
        layer_records.append(
            (index, layer.wind_type, terminal, pre_count, len(machine.get_moves()))
        )
        if terminal:
            encountered_terminal = True

    moves = machine.get_moves()

    # Per-layer metrics: cumulative O1 metrics at each layer boundary, differenced.
    # (Between layers only a summary comment is recorded, which accrues no
    # time/tow, so cumulative-at-pre equals cumulative-at-previous-post.)
    layer_metrics: list[LayerMetrics] = []
    prev_time = 0.0
    prev_dist = 0.0
    for index, wind_type, terminal, pre_count, post_count in layer_records:
        cumulative = nominal_metrics(moves[:post_count], mandrel_diameter)
        layer_metrics.append(
            LayerMetrics(
                index=index,
                wind_type=wind_type,
                commands=post_count - pre_count,
                time_s=cumulative.time_s - prev_time,
                cumulative_time_s=cumulative.time_s,
                tow_m=(cumulative.distance_mm - prev_dist) / 1000.0,
                cumulative_tow_m=cumulative.distance_mm / 1000.0,
                terminal=terminal,
            )
        )
        prev_time = cumulative.time_s
        prev_dist = cumulative.distance_mm

    total = nominal_metrics(moves, mandrel_diameter)

    # The init move (all-zero rapid) is the program's first line; the header is
    # carried structurally in ProgramMeta and rendered by serialize().
    init_move = Move(
        MoveKind.RAPID,
        targets={Axis.CARRIAGE: 0.0, Axis.MANDREL: 0.0, Axis.DELIVERY_HEAD: 0.0},
    )
    meta = ProgramMeta(
        mandrel_diameter=definition.mandrel_parameters.diameter,
        wind_length=definition.mandrel_parameters.wind_length,
        tow_width=definition.tow_parameters.width,
        tow_thickness=definition.tow_parameters.thickness,
    )
    program = Program(meta=meta, moves=[init_move, *moves])
    commands = serialize(program, dialect)
    if options.verbose:
        commands.insert(0, "; Verbose output enabled")

    return PlanResult(
        commands=commands,
        total_time_s=total.time_s,
        total_tow_m=total.distance_mm / 1000.0,
        layers=layer_metrics,
    )
