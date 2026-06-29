"""Declarative pattern primitive for winding layers.

A single machine-agnostic description of *what* a layer lays on the developed
(unwrapped) cylinder, independent of how it lowers to machine axes. The three
historical layer types are special cases of one primitive:

- **helical** -> a constant-angle path (``alpha_deg``) laid with a coverage
  pattern (``pattern_number`` / ``skip_index``) and turnarounds;
- **hoop** -> the ``alpha_deg -> 90`` limit of that same path;
- **skip** -> ``lay=False``: a non-laying reposition that only advances the
  mandrel.

Wind angle (``alpha_deg``) follows the normative convention: measured from the
mandrel axis, ``0`` axial and ``90`` hoop (see ``docs/reference/concepts.md``
and ``docs/guides/wind-format.md``).

Introduced in Stage 2 / S1 (#295). The primitive is *constructed* from each
layer here but not yet lowered: the planner still uses the per-pattern
generators in :mod:`fiberpath.planning.layer_strategies`. Lowering this
primitive to the Motion IR lands in S2 (#296).
"""

from __future__ import annotations

from dataclasses import dataclass

from fiberpath.config.schemas import (
    HelicalLayer,
    HoopLayer,
    LayerModel,
    SkipLayer,
)

#: The wind angle of a hoop layer: a circumferential wrap is the alpha -> 90 limit.
HOOP_ALPHA_DEG = 90.0


@dataclass(frozen=True, slots=True)
class PatternSpec:
    """One winding layer as a declarative pattern on the developed cylinder.

    When ``lay`` is ``False`` (a skip) the layer lays no fiber and only the
    ``reposition_degrees`` field is meaningful; the angle/coverage/turnaround
    fields carry inert defaults.
    """

    lay: bool
    """Whether fiber is laid. ``False`` is a bare reposition (skip)."""

    alpha_deg: float
    """Wind angle from the mandrel axis (0 axial, 90 hoop). Used when ``lay``."""

    pattern_number: int
    """Coverage pattern number *p*; ``1`` for a single-circuit layer."""

    skip_index: int
    """Phase-advance stride *d*; used when ``lay`` and ``pattern_number > 1``."""

    lock_degrees: float
    """Turnaround dwell at each end of a pass."""

    lead_in_mm: float
    """Axial lead-in before the angled pass (``lay`` only)."""

    lead_out_degrees: float
    """Rotational lead-out after the angled pass (``lay`` only)."""

    terminal: bool
    """Lay a single direction only, with no return pass."""

    skip_initial_near_lock: bool
    """Omit the initial near-end lock move."""

    reposition_degrees: float
    """Mandrel advance for a non-laying skip (``lay=False``)."""


def hoop_spec(layer: HoopLayer) -> PatternSpec:
    """Map a hoop layer onto the primitive as the ``alpha -> 90`` case.

    The turnaround lock (``180``) and the delivery-head lean are derived from
    geometry at lowering time (S2), so only the declarative defaults are set here.
    """
    return PatternSpec(
        lay=True,
        alpha_deg=HOOP_ALPHA_DEG,
        pattern_number=1,
        skip_index=1,
        lock_degrees=180.0,
        lead_in_mm=0.0,
        lead_out_degrees=0.0,
        terminal=layer.terminal,
        skip_initial_near_lock=False,
        reposition_degrees=0.0,
    )


def helical_spec(layer: HelicalLayer) -> PatternSpec:
    """Map a helical layer onto the primitive (the general laying case)."""
    return PatternSpec(
        lay=True,
        alpha_deg=layer.wind_angle,
        pattern_number=layer.pattern_number,
        skip_index=layer.skip_index,
        lock_degrees=layer.lock_degrees,
        lead_in_mm=layer.lead_in_mm,
        lead_out_degrees=layer.lead_out_degrees,
        terminal=False,
        skip_initial_near_lock=layer.skip_initial_near_lock,
        reposition_degrees=0.0,
    )


def skip_spec(layer: SkipLayer) -> PatternSpec:
    """Map a skip layer onto the primitive as a non-laying reposition."""
    return PatternSpec(
        lay=False,
        alpha_deg=0.0,
        pattern_number=1,
        skip_index=1,
        lock_degrees=0.0,
        lead_in_mm=0.0,
        lead_out_degrees=0.0,
        terminal=False,
        skip_initial_near_lock=False,
        reposition_degrees=layer.mandrel_rotation,
    )


def pattern_spec(layer: LayerModel) -> PatternSpec:
    """Map any layer model onto the declarative pattern primitive."""
    if isinstance(layer, HoopLayer):
        return hoop_spec(layer)
    if isinstance(layer, HelicalLayer):
        return helical_spec(layer)
    if isinstance(layer, SkipLayer):
        return skip_spec(layer)
    raise TypeError(f"Unsupported layer type: {layer}")
