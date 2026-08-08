# Von Kármán nosecone (Stage 3b Phase 1)

A helical layer wound on a **Von Kármán (LD-Haack) nose** — the first
non-developable surface. The winding path is a **numeric geodesic** (the Clairaut
relation integrated over the curved meridian), not a closed-form straight line.

- `mandrelParameters.profile = { "type": "vonKarman" }` (schemaVersion **1.2**).
  The base radius is `diameter`/2 and the axial length is `windLength`; the tip is at
  `z = windLength`.
- The geodesic turns around at the Clairaut radius `C = (diameter/2)·sin(windAngle)`,
  so it **cannot** reach the tip: this example leaves an **expected bare polar cap** of
  diameter ≈ `2C` near the tip (reported by the planner). Full tip coverage requires
  non-geodesic winding — Phase 2 (#327).

## Not byte-goldened

Like `cone_reducer`, this example is **equivalence-gated**, not byte-compared: the
geodesic coordinates come from transcendental functions whose last rounded digit is not
bit-stable across platforms. `tests/planning/test_profile.py` locks it by the Clairaut
geometry invariant (re-derived from the emitted Motion IR), coverage, circuit count, and
an integer `len(moves)` structural gate. See `docs/guides/wind-format.md`.
