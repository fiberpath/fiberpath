"""Dialects encapsulate controller-specific behavior.

A :class:`MarlinDialect` is the G-code-layer runtime view (axis letters + number
formatting) used by the serializer and reader. The user-facing, versioned
description of a target controller is :class:`fiberpath.config.MachineProfile`;
:func:`dialect_from_profile` bridges a profile to the runtime dialect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fiberpath.config import MachineProfile


@dataclass(slots=True)
class AxisMapping:
    """Maps logical axes to G-code axis letters."""

    carriage: str = "X"  # Linear motion along mandrel
    mandrel: str = "A"  # Mandrel rotation
    delivery_head: str = "B"  # Delivery head rotation

    @property
    def is_rotational_mandrel(self) -> bool:
        """True if mandrel uses a rotational axis (A/B/C)."""
        return self.mandrel in {"A", "B", "C"}

    @property
    def is_rotational_delivery(self) -> bool:
        """True if delivery head uses a rotational axis (A/B/C)."""
        return self.delivery_head in {"A", "B", "C"}


@dataclass(slots=True)
class MarlinDialect:
    """G-code dialect configuration for Marlin controllers."""

    units: str = "mm"
    feed_mode: str = "G94"  # Units per minute
    axis_mapping: AxisMapping = field(default_factory=AxisMapping)

    def prologue(self) -> list[str]:
        """Modal setup lines emitted before motion so the program is self-describing.

        The planner authors absolute coordinates in the dialect's units and feeds
        in units-per-minute; without this preamble the program would silently
        inherit whatever modal state the controller happened to be in (#322).
        """
        units_code = "G21" if self.units == "mm" else "G20"
        units_label = "millimeter" if self.units == "mm" else "inch"
        return [
            f"{units_code} ; {units_label} units",
            "G90 ; absolute positioning",
            f"{self.feed_mode} ; feed rate in units per minute",
        ]


def dialect_from_profile(profile: MachineProfile) -> MarlinDialect:
    """Build the runtime dialect a serializer/reader uses from a machine profile."""
    mapping = profile.axis_mapping
    return MarlinDialect(
        units=profile.units,
        feed_mode=profile.feed_mode,
        axis_mapping=AxisMapping(
            carriage=mapping.carriage,
            mandrel=mapping.mandrel,
            delivery_head=mapping.delivery_head,
        ),
    )


def _default_dialect() -> MarlinDialect:
    # Derived from the bundled, versioned `marlin-xab` profile rather than a
    # hardcoded literal (#197). Reproduces the historical X/A/B dialect exactly.
    from fiberpath.config import default_machine_profile

    return dialect_from_profile(default_machine_profile())


# The canonical Marlin X/A/B dialect, sourced from the versioned default profile.
MARLIN_XAB_STANDARD = _default_dialect()
