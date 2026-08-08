# Von Kármán nosecone — non-geodesic (friction-assisted) winding (Stage 3b Phase 2)

The same Von Kármán nose as [`vk_nosecone`](../vk_nosecone), but the helical layer
sets **`frictionLambda`** to wind **non-geodesically** and reach past the geodesic
turnaround toward the tip.

- `frictionLambda = 0.15` (schemaVersion **1.3**): the friction ratio λ = k_g/k_n the
  laid tow holds. `0` is the geodesic (a bare cap ≈ `2·(diameter/2)·sin(windAngle)`);
  raising λ lays deeper, leaving a **smaller** bare cap. It must stay within the machine
  slip limit μ (`slipLimit` in the [machine profile](../../docs/guides/machine-profile.md),
  default `0.2`) — a higher value would slip and is rejected.
- The planner reports the reachable cap **and** the turnaround **dwell** demand. Here the
  dwell exceeds μ, so the *laying* reaches the cap but the *reversal* is flagged as needing
  4th-axis delivery (a future capability) — the report is honest about that boundary.
- Only valid on a `profile` mandrel; a non-zero `frictionLambda` on a cylinder or cone is
  rejected. See [`docs/guides/wind-format.md`](../../docs/guides/wind-format.md).

## Not byte-goldened

Like `vk_nosecone`, this example is **equivalence-gated**, not byte-compared: the
non-geodesic coordinates come from an adaptive ODE integration whose last rounded digit is
not bit-stable across platforms. `tests/planning/test_profile.py` locks it by planning it
end-to-end (deeper cap than the geodesic, the friction comment) rather than a byte golden.
