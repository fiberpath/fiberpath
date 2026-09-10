# Roadmap

This document describes FiberPath's intended technical direction. It is the narrative companion to the
issue tracker: GitHub issues track concrete near-term work, while this roadmap captures the multi-stage
arc — including longer-horizon items that span months and won't fit cleanly into a single issue yet.

It records decisions that have been made and reasoned through; it is deliberately grounded and avoids
speculative features. Items with no demand or no hardware to validate them are noted as such rather than
promised. For features that have been **considered and deferred or rejected**, see
[feature-backlog.md](feature-backlog.md).

## North star

> An open, auditable filament-winding compiler: winding patterns expressed as mathematics over a mandrel
> surface, lowered through an explicit toolpath representation to G-code, with a documented, versioned open
> winding-program format.

Today FiberPath plans **cylinders, reducing cones and Von Kármán nose profiles** (hoop, helical, and skip
layers, geodesic or friction-assisted) and emits Marlin XAB G-code. The direction below records how that
was reached — first by making the internals explicit and data-driven on the cylinder, then by extending to
non-cylindrical and finally non-developable surfaces — without ever breaking the validated cylinder path.

## Why this is grounded, not aspirational

FiberPath's existing pattern controls are already the cylinder-specialized form of standard
filament-winding theory (Koussios, *Filament Winding: A Unified Approach*, 2004):

- `patternNumber` / `skipIndex` / `lockDegrees` are the pattern number, phase-advance stride, and
  turnaround dwell of classical winding-pattern theory; the coverage validators encode the Diophantine
  coverage conditions (`gcd(patternNumber, skipIndex) = 1`, circuit divisibility, the lock-degrees slot
  math).
- On a cylinder, a constant-angle helix is a geodesic (Clairaut's relation `r·sin α = const` with `r`
  constant), and the unwrapped surface is a flat plane in which the path is a straight line.

So "patterns as data/math" is making an already-mathematical core explicit, not inventing new theory.

### The developability boundary

This is the key structural fact that shapes the staging:

- **Cylinders and cones are *developable*** — they unroll to a flat plane with no distortion, so winding
  paths are **closed-form** (straight lines in the development). No differential-equation solver and no
  friction model are required.
- **Domes and general curved heads are *not* developable** — paths must be obtained by integrating the
  geodesic (Clairaut) ODE, or, to hit a target angle, the non-geodesic equation `k_g = λ·k_n` with a
  **measured** slippage coefficient (`λ ≤ μ`). These also need full 3-D delivery-eye kinematics.

The natural boundary is therefore *developable (cylinder + cone)* vs *non-developable (dome)* — not
"cylinder vs everything else."

## Target architecture

Built bottom-up so each layer ships value on its own:

```
(z, r) mandrel profile  +  declarative layer-stack spec     ── the .wind open format
        │   surface model: typed analytic segments (Cylinder, Cone, VonKarman; Dome later)
        ▼
unified pattern primitive  (path on the developed surface + coverage pattern + turnaround)
        ▼
geometry / surface path    (developable ⇒ closed-form; non-developable ⇒ Clairaut / λ-ODE)
        ▼
Motion IR  (typed, machine-agnostic moves)            ── single source of motion math
        ├─▶ serialize(moves, dialect) ─▶ G-code        (dialect = post-processor; G-code = build artifact)
        ├─▶ simulate(moves) ─▶ time / material
        └─▶ plot(moves)     ─▶ 2-D preview
```

Two design commitments worth stating:

- **One toolpath representation, introduced first.** The dialect/axis-mapping layer is already a correct
  machine post-processor; what's missing is the machine-agnostic toolpath it should post-process. A single
  typed Motion IR fills that gap and becomes the one place motion math lives.
- **Declarative data, not a DSL.** Winding intent is a bounded parameter set, so a typed schema is the
  right front-end. If parametric authoring is ever needed, a Python builder that emits a `.wind` definition
  is preferable to inventing a language.

## Engine roadmap

Each stage is regression-gated against real, shipping parts (the `examples/rocketry/` mandrels) — the
toolpath must be reproduced bit-for-bit (or coverage-equivalent) before and after.

| Stage | Work | Horizon | Issue |
|---|---|---|---|
| 1 | **Motion IR** — typed machine-agnostic toolpath; planner emits it; simulate/plot/metrics/G-code consume it; adopt a single nominal time model (removes today's planner/simulator time divergence) | ✅ Done | [#136](https://github.com/fiberpath/fiberpath/issues/136) |
| 2 | **Unified pattern primitive** — express hoop/helical/skip as one parametric primitive on the developed cylinder, re-derived to bit-for-bit equality; validators become spec type-checkers | ✅ Done | [#137](https://github.com/fiberpath/fiberpath/issues/137) |
| 3a | **Cones** — typed `Cone` profile segment; developable closed-form paths; first golden is a straight HPR reducer frustum | ✅ Done | [#138](https://github.com/fiberpath/fiberpath/issues/138) |
| 3b | **Domes / general surfaces of revolution** — Clairaut + non-geodesic (λ) path solving with measured friction, 3-D delivery-eye kinematics | 🚧 Phases 1–2 shipped in 0.11.0; Phase 3 hardware-gated | [#139](https://github.com/fiberpath/fiberpath/issues/139) |

Notes:

- **Stages 1, 2 and 3a have shipped, and 3b is underway.** Hoop, helical, and skip are expressed as one
  declarative pattern primitive on the developed surface that lowers through a single Motion IR path
  (`fiberpath/planning/`: `pattern.py` defines the primitive, `developed.py` the per-pattern path builders
  + the one lowering).
  The cylinder cut-over reproduces the prior toolpaths **bit-for-bit** (the example goldens are unchanged),
  and the coverage validators are type-checkers over the primitive. **Stage 3a adds cones**: `surface.py`
  models the mandrel as a typed `Cylinder`/`Cone`, a reducing frustum is wound as a **geodesic** (Clairaut,
  anchored at the large end) via a new path builder that reuses the same lowering, exposed through the
  additive `.wind` `endDiameter` field (`schemaVersion 1.1`) with the `cone_reducer` example
  (gated by the tolerance-based equivalence harness — the geodesic's transcendental coordinates
  are not bit-stable across platforms, so it is not byte-goldened like the cylinder examples).
- **Time-model calibration** against the real machine is tracked separately and done when hardware time
  allows ([#130](https://github.com/fiberpath/fiberpath/issues/130)); the engine ships with a
  documented nominal estimate until then.
- **Stage 3b is split into three phases**, the first two of which shipped in 0.11.0:
    - *Phase 1 — geodesic path on a curved profile*
      ([#326](https://github.com/fiberpath/fiberpath/issues/326), done): the first **non-developable**
      surface. A Von Kármán nose is added as an optional
      `mandrelParameters.profile` (`schemaVersion 1.2`) and wound by integrating the Clairaut relation over
      the curved meridian. Because a geodesic turns around at its Clairaut radius, the layer leaves an
      expected **bare polar cap** near the tip, which the planner reports.
    - *Phase 2 — non-geodesic winding + friction calibration*
      ([#327](https://github.com/fiberpath/fiberpath/issues/327), done): an optional `frictionLambda`
      (λ = k_g/k_n, `schemaVersion 1.3`) lets a pass leave the geodesic and
      climb past the turnaround, shrinking that cap. It is bounded by a measured machine slip limit μ
      (`slipLimit`, `profileVersion 1.1`); the planner rejects λ > μ and reports the turnaround dwell
      demand. `fiberpath plan --profile` supplies a calibrated μ. λ = 0 is byte-identical to the geodesic.
    - *Phase 3 — delivery kinematics for steep profiles*
      ([#328](https://github.com/fiberpath/fiberpath/issues/328), open): the radial cross-feed 4th axis
      needed to close the remaining cap. **Hardware-gated** — it needs a
      machine to validate against, so it starts when there is one.
- Straight cones (3a) cover the near-term non-cylindrical need (transitions/reducers); true **domes** remain
  future 3b work beyond the Von Kármán profile already supported.

## Open winding-program format

There is no open, documented interchange format for winding programs — commercial tools keep theirs
proprietary and open hobby tools are cylinder-only and machine-specific. FiberPath publishes one, as a
cross-cutting deliverable. **This has shipped:**

- The **`.wind` spec** is the flagship, stable, versioned format (where a community would form); the Motion
  IR is documented as a secondary, separately-versioned format ([Motion IR reference](../reference/motion-ir.md));
  emitted G-code is treated as a build artifact, not a standard.
- The schema-version constraint was relaxed so the format can evolve additively
  ([#140](https://github.com/fiberpath/fiberpath/issues/140), done). The
  [format guide](../guides/wind-format.md) is now a normative SPEC with RFC-2119 conformance requirements,
  the media type `application/vnd.fiberpath.wind+json`, a major-versioned JSON-Schema `$id` that resolves at
  <https://fiberpath.org/schemas/wind/1/wind.schema.json>, and a `conformance/` corpus of `valid/` /
  `invalid/` cases enforced by `tests/conformance/`
  ([#141](https://github.com/fiberpath/fiberpath/issues/141), done).
- Evolution policy: additive-only within a major version; tolerant readers ignore unknown fields; breaking
  changes bump the major. The existing `windAngle` convention (measured from the mandrel axis: 0° axial,
  90° hoop) is normative.

## Infrastructure

Tracked under the org-migration epic
([#142](https://github.com/fiberpath/fiberpath/issues/142)), front-loaded because the documentation
URL, schema `$id`, badges, and dependency tooling all depend on the project's home. **This has shipped:**

- The repository moved to the dedicated `fiberpath` GitHub org and the release pipeline was restored —
  chiefly the PyPI trusted publisher, which is keyed on the repository owner/name
  ([#131](https://github.com/fiberpath/fiberpath/issues/131), done).
- An org-pages documentation site is live with the owned `fiberpath.org` domain pointed at it
  ([#133](https://github.com/fiberpath/fiberpath/issues/133), done); badges and links were updated
  ([#132](https://github.com/fiberpath/fiberpath/issues/132), done).
- The org `.github` community-health repository exists
  ([#134](https://github.com/fiberpath/fiberpath/issues/134), done) and dependency updates moved from
  Dependabot to org-level Renovate, keeping security alerts
  ([#135](https://github.com/fiberpath/fiberpath/issues/135), done).

The desktop GUI stays in the monorepo for now; splitting it into its own repository has been considered and
deferred (the engine refactor benefits from atomic cross-cutting changes, and the bundled-CLI coupling is
simpler in one repo).

## Guiding constraints

These hold across all stages:

- **Don't break the validated cylinder output.** Golden-file regression against real parts gates every
  refactor.
- **Keep planning machine-agnostic.** Machine specifics live in the dialect/post-processor and a machine
  model, never baked into pattern logic.
- **The physical world is calibrated, not assumed.** Friction/slippage for non-geodesic winding is measured
  on hardware; the engine ships nominal models with explicit tuning knobs rather than unvalidated theory.
- **Backward compatibility.** New capability is added as optional, additive schema fields; `.wind` files
  keep working.

## On timelines

Horizons are approximate and reflect a single maintainer balancing this with other work. "Near-term"
means actively planned; "longer-horizon" items depend on real demand and, for non-cylindrical surfaces,
hardware validation. This roadmap will be revised as stages land.
