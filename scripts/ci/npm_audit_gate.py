#!/usr/bin/env python3
"""Enforce a high/critical gate over an ``npm audit --json`` report, with an allowlist.

Fails (exit 1) if any advisory of severity ``high`` or ``critical`` is present and
not waived with ``--ignore <GHSA-ID>``. ``moderate``/``low``/``info`` are reported
but do not block; any other severity value blocks unless its advisory is ignored.
An ignored advisory that no longer appears is flagged so its allowlist entry gets
removed.

Why this exists: npm has no per-advisory ignore, so ``--audit-level=high`` cannot
accept a triaged advisory that has no fixed version upstream. Only advisory objects
in ``via`` are counted; string entries name another vulnerable package and are the
same advisory propagated up the tree.

Fails closed on a missing/malformed report, on any ``auditReportVersion`` other
than 2, and when a package npm flags at high/critical (or an unknown severity) does
not trace through its ``via`` links to a parsed high/critical advisory — a shape
change must not read as a clean audit, even while another advisory is ignored.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

NON_BLOCKING = {"moderate", "low", "info"}


def advisory_id(advisory: dict) -> str:
    """The GHSA ID from an advisory's URL, falling back to npm's numeric source."""
    url = str(advisory.get("url", ""))
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return tail if tail.startswith("GHSA-") else str(advisory.get("source", "unknown"))


def evaluate(report: dict, ignore: set[str]) -> int:
    """Print an audit summary and return the intended process exit code."""
    # Only the v2 shape (npm 7+) is understood; anything else could hide
    # advisories where this parser does not look, so fail closed.
    if report.get("auditReportVersion") != 2:
        print("::error::npm audit report is not auditReportVersion 2", file=sys.stderr)
        return 1
    vulnerabilities = report.get("vulnerabilities")
    if not isinstance(vulnerabilities, dict):
        print("::error::npm audit report missing 'vulnerabilities'", file=sys.stderr)
        return 1

    advisories: dict[str, dict] = {}
    for entry in vulnerabilities.values():
        for via in entry.get("via", []):
            if not isinstance(via, dict):
                continue
            adv_id = advisory_id(via)
            # On an id collision, keep the advisory that would block.
            kept = advisories.get(adv_id)
            if kept is None or kept.get("severity") in NON_BLOCKING:
                advisories[adv_id] = via

    def explained(name: str, seen: set[str]) -> bool:
        """Whether a package traces through string ``via`` links to a blocking advisory."""
        entry = vulnerabilities.get(name)
        if not isinstance(entry, dict) or name in seen:
            return False
        seen.add(name)
        for via in entry.get("via", []):
            if isinstance(via, dict) and via.get("severity") not in NON_BLOCKING:
                return True
            if isinstance(via, str) and explained(via, seen):
                return True
        return False

    # Every package npm flags at high/critical (or an unknown severity) must be
    # accounted for by a parsed advisory; otherwise the parser missed one.
    unexplained = sorted(
        name
        for name, entry in vulnerabilities.items()
        if entry.get("severity") not in NON_BLOCKING and not explained(name, set())
    )

    blocking: list[tuple[str, dict]] = []
    ignored: list[tuple[str, dict]] = []
    below: list[tuple[str, dict]] = []
    for adv_id, adv in sorted(advisories.items()):
        if adv.get("severity") in NON_BLOCKING:
            below.append((adv_id, adv))
        elif adv_id in ignore:
            ignored.append((adv_id, adv))
        else:
            blocking.append((adv_id, adv))

    def show(rows: list[tuple[str, dict]]) -> None:
        for adv_id, adv in rows:
            print(
                f"  - {adv_id}  {adv.get('name', '?')} {adv.get('range', '?')}"
                f"  [{adv.get('severity', '?')}]  {adv.get('title', '')}"
            )

    print(f"npm audit: {len(advisories)} advisories.")
    if blocking:
        print(f"\nBLOCKING — high/critical ({len(blocking)}):")
        show(blocking)
    if ignored:
        print(f"\nAccepted via --ignore, not blocking ({len(ignored)}):")
        show(ignored)
    if below:
        print(f"\nBelow threshold — moderate/low/info, not blocking ({len(below)}):")
        show(below)
    for adv_id in sorted(ignore - advisories.keys()):
        print(f"::warning::--ignore {adv_id} matched nothing — remove it from the allowlist")

    if blocking:
        print(f"\n::error::{len(blocking)} high/critical advisory(ies) not accepted — failing.")
        return 1
    if unexplained:
        print(
            f"\n::error::{len(unexplained)} high/critical package(s) trace to no parsed "
            f"high/critical advisory: {', '.join(unexplained)}"
        )
        return 1
    print("\nNo unaccepted high/critical advisories. Gate passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("report", help="path to npm-audit.json")
    parser.add_argument(
        "--ignore", action="append", default=[], metavar="GHSA-ID", help="accepted advisory"
    )
    args = parser.parse_args(argv)
    # A missing/empty/malformed report raises here -> the gate fails closed.
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    return evaluate(report, set(args.ignore))


if __name__ == "__main__":
    raise SystemExit(main())
