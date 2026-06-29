# cone_reducer

The first non-cylindrical example: a **reducing cone (frustum)**, 98 mm → 54 mm
diameter over 120 mm (≈10.4° half-angle) — an HPR-style transition/reducer.

A single helical layer is wound as a **geodesic** (Clairaut). The wind angle
(`30°`) is anchored at the **large end** (z = 0, `diameter`); the achieved fiber
angle grows toward the small end (`endDiameter`) as `sin α(z) = C / r(z)`. The
path is closed-form (a straight line in the unrolled sector) — no ODE/friction
solver, because a cone is developable.

`endDiameter` is a `schemaVersion 1.1` addition; omit it (or set it equal to
`diameter`) for a cylinder. See `docs/guides/wind-format.md`.

> **No `expected.gcode` byte golden.** Unlike the cylinder examples, this one is
> gated by the tolerance-based **equivalence harness**
> (`tests/planning/test_cone.py::test_cone_reducer_example_is_a_valid_geodesic`:
> Clairaut geometry, coverage, circuit count) rather than a byte-for-byte golden.
> The geodesic's `acos`/`asin` accumulation is not bit-stable across platforms
> (Linux vs Windows differ by ~1e-6 on boundary coordinates), so an exact golden
> would be spuriously fragile.
