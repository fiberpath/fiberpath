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

Today FiberPath plans **cylindrical mandrels** (hoop, helical, and skip layers) and emits Marlin XAB
G-code. The direction below generalizes that — first by making the internals explicit and data-driven on
the cylinder, then by extending to non-cylindrical surfaces — without breaking the validated cylinder path.

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
        │   surface model: typed analytic segments (Cylinder, Cone; Dome later)
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
| 3b | **Domes / general surfaces of revolution** — Clairaut + non-geodesic (λ) path solving with measured friction, 3-D delivery-eye kinematics | Longer-horizon (est. 2027+, hardware-gated) | [#139](https://github.com/fiberpath/fiberpath/issues/139) |

Notes:

- **Stages 1, 2, and 3a have shipped.** Hoop, helical, and skip are expressed as one declarative pattern
  primitive on the developed surface that lowers through a single Motion IR path (`fiberpath/planning/`:
  `pattern.py` defines the primitive, `developed.py` the per-pattern path builders + the one lowering).
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
- Stage 3b is intentionally not broken into sub-issues yet — it starts only when there is real
  non-cylindrical demand and a machine to validate the friction model on. Straight cones (3a) cover the
  near-term non-cylindrical need (transitions/reducers); curved (ogive) nose cones are non-developable and
  fall into the 3b tier.

## Open winding-program format

There is no open, documented interchange format for winding programs — commercial tools keep theirs
proprietary and open hobby tools are cylinder-only and machine-specific. FiberPath intends to publish one,
as a cross-cutting deliverable:

- The **`.wind` spec** is the flagship, stable, versioned format (where a community would form); the Motion
  IR is documented as a secondary, separately-versioned format; emitted G-code is treated as a build
  artifact, not a standard.
- Concrete groundwork: relax the schema version constraint so the format can evolve additively
  ([#140](https://github.com/fiberpath/fiberpath/issues/140)); promote the format guide to a
  normative versioned SPEC, add a versioned JSON-Schema `$id`, and build a conformance corpus
  (`valid/` / `invalid/` / golden outputs) ([#141](https://github.com/fiberpath/fiberpath/issues/141)).
- Evolution policy: additive-only within a major version; tolerant readers ignore unknown fields; breaking
  changes bump the major. The existing `windAngle` convention (measured from the mandrel axis: 0° axial,
  90° hoop) is normative.

## Infrastructure

Tracked under the org-migration epic
([#142](https://github.com/fiberpath/fiberpath/issues/142)), front-loaded because the documentation
URL, schema `$id`, badges, and dependency tooling all depend on the project's home:

- Migrate the repository to a dedicated `fiberpath` GitHub org, restoring the release pipeline — chiefly
  the PyPI trusted publisher, which is keyed on the repository owner/name
  ([#131](https://github.com/fiberpath/fiberpath/issues/131)).
- Stand up an org-pages documentation site and point the owned `fiberpath.org` domain at it
  ([#133](https://github.com/fiberpath/fiberpath/issues/133)); update badges/links
  ([#132](https://github.com/fiberpath/fiberpath/issues/132)).
- Add an org `.github` community-health repository
  ([#134](https://github.com/fiberpath/fiberpath/issues/134)) and switch dependency updates from
  Dependabot to org-level Renovate, keeping security alerts
  ([#135](https://github.com/fiberpath/fiberpath/issues/135)).

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
