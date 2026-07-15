#!/usr/bin/env python3
"""Enforce a CVSS >= 7.0 gate over a ``cargo audit --json`` report.

Fails (exit 1) if any vulnerability has a CVSS base score >= 7.0. Vulnerabilities
below the threshold, or with no/unparseable score, are reported but do not block;
informational warnings (unmaintained / unsound / yanked) are summarised.

Why this is not a one-liner: the RustSec ``cvss`` field is a CVSS v3.x *vector*
string (e.g. ``"CVSS:3.1/AV:N/AC:L/..."``), not a number. A naive ``float(cvss)``
raises and, if swallowed, silently lets every vulnerability through — so the base
score is computed from the vector here. A missing report (tool/network failure)
fails closed via the ``json.loads`` raise in :func:`main`.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

THRESHOLD = 7.0

# CVSS v3.x base-metric weights (identical between 3.0 and 3.1).
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}
_AC = {"L": 0.77, "H": 0.44}
_UI = {"N": 0.85, "R": 0.62}
_PR_UNCHANGED = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_CHANGED = {"N": 0.85, "L": 0.68, "H": 0.50}
_CIA = {"H": 0.56, "L": 0.22, "N": 0.00}


def _roundup(value: float) -> float:
    """CVSS v3.1 Roundup: round up to one decimal place (exact-integer aware)."""
    scaled = round(value * 100000)
    if scaled % 10000 == 0:
        return scaled / 100000.0
    return (math.floor(scaled / 10000) + 1) / 10.0


def cvss3_base_score(vector: str) -> float:
    """Compute a CVSS v3.1 base score from its vector string.

    Uses the v3.1 formula, which is identical to v3.0 except for the
    changed-scope impact sub-score. Raises ValueError if the string is not a
    parseable CVSS v3.x base vector.
    """
    if not vector.startswith("CVSS:3."):
        raise ValueError(f"not a CVSS v3.x vector: {vector!r}")
    metrics = dict(part.split(":", 1) for part in vector.split("/")[1:] if ":" in part)
    scope_changed = metrics.get("S") == "C"
    try:
        av = _AV[metrics["AV"]]
        ac = _AC[metrics["AC"]]
        ui = _UI[metrics["UI"]]
        pr = (_PR_CHANGED if scope_changed else _PR_UNCHANGED)[metrics["PR"]]
        conf, integ, avail = _CIA[metrics["C"]], _CIA[metrics["I"]], _CIA[metrics["A"]]
    except KeyError as exc:
        raise ValueError(f"missing/invalid base metric {exc} in {vector!r}") from exc

    iss = 1 - (1 - conf) * (1 - integ) * (1 - avail)
    if scope_changed:
        # CVSS v3.1 changed-scope impact (v3.0 used ``(iss - 0.02) ** 15``,
        # which under-scores by up to ~0.1 and can miss the 7.0 boundary).
        impact = 7.52 * (iss - 0.029) - 3.25 * (iss * 0.9731 - 0.02) ** 13
    else:
        impact = 6.42 * iss
    if impact <= 0:
        return 0.0
    exploitability = 8.22 * av * ac * pr * ui
    combined = impact + exploitability
    raw = 1.08 * combined if scope_changed else combined
    return _roundup(min(raw, 10.0))


def score_of(cvss: object) -> float | None:
    """Best-effort numeric base score from a RustSec ``cvss`` field, else None."""
    if cvss is None:
        return None
    if isinstance(cvss, (int, float)):
        return float(cvss)
    text = str(cvss).strip()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        return cvss3_base_score(text)
    except ValueError:
        return None


def evaluate(report: dict) -> int:
    """Print an audit summary and return the intended process exit code."""
    vulnerabilities = report.get("vulnerabilities")
    if not isinstance(vulnerabilities, dict) or "list" not in vulnerabilities:
        print("::error::cargo audit report missing 'vulnerabilities.list'", file=sys.stderr)
        return 1

    vulns = vulnerabilities["list"]
    warnings = report.get("warnings", {})

    blocking: list[tuple[str, str, str, float | None, str]] = []
    below: list[tuple[str, str, str, float | None, str]] = []
    unscored: list[tuple[str, str, str, float | None, str]] = []
    for item in vulns:
        advisory = item.get("advisory", {})
        row = (
            advisory.get("id", "unknown"),
            advisory.get("package", "?"),
            item.get("package", {}).get("version", "?"),
            score_of(advisory.get("cvss")),
            advisory.get("title", ""),
        )
        score = row[3]
        if score is None:
            unscored.append(row)
        elif score >= THRESHOLD:
            blocking.append(row)
        else:
            below.append(row)

    def show(rows: list[tuple[str, str, str, float | None, str]]) -> None:
        for advisory_id, pkg, ver, score, title in rows:
            label = "no-score" if score is None else f"CVSS {score}"
            print(f"  - {advisory_id}  {pkg} {ver}  [{label}]  {title}")

    warning_total = sum(len(v) for v in warnings.values())
    print(f"Cargo audit: {len(vulns)} vulnerabilities, {warning_total} informational warnings.")
    if blocking:
        print(f"\nBLOCKING — CVSS >= {THRESHOLD} ({len(blocking)}):")
        show(blocking)
    if below:
        print(f"\nBelow threshold — CVSS < {THRESHOLD}, not blocking ({len(below)}):")
        show(below)
    if unscored:
        print(f"\nUnscored vulnerabilities — reported, not blocking ({len(unscored)}):")
        show(unscored)
        for advisory_id, pkg, ver, _score, _title in unscored:
            print(
                f"::warning::Unscored vulnerability {advisory_id} in {pkg} {ver} — review manually"
            )
    if warnings:
        counts = ", ".join(f"{k}={len(v)}" for k, v in sorted(warnings.items()))
        print(f"\nInformational warnings (not blocking): {counts}")

    if blocking:
        print(f"\n::error::{len(blocking)} vulnerability(ies) with CVSS >= {THRESHOLD} — failing.")
        return 1
    print(f"\nNo vulnerabilities with CVSS >= {THRESHOLD}. Gate passed.")
    return 0


def main(path: str) -> int:
    # A missing/empty/malformed report raises here -> the gate fails closed.
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    return evaluate(report)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: cargo_audit_gate.py <cargo-audit.json>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
