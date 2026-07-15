"""Tests for the cargo-audit CVSS gate (scripts/ci/cargo_audit_gate.py).

Guards the two historical failure modes: the gate must actually *block* on a
CVSS >= 7.0 vulnerability (a naive ``float(cvss)`` on a vector string silently
passed everything), and it must *fail closed* on a missing/malformed report.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "cargo_audit_gate.py"
_spec = importlib.util.spec_from_file_location("cargo_audit_gate", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


@pytest.mark.parametrize(
    ("vector", "expected"),
    [
        # RUSTSEC-2026-0194/0195 (quick-xml DoS) — the real advisories that must block.
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H", 7.5),
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8),
        ("CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N", 1.8),
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H", 10.0),
        ("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H", 7.5),  # unchanged scope: 3.0 == 3.1
        # Changed-scope: the v3.1 formula differs from v3.0. These pin v3.1 and
        # would catch a regression to the v3.0 impact sub-score (which yields
        # 9.6 and 6.9 respectively — the latter a silent miss at the boundary).
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:H/I:H/A:H", 9.7),
        ("CVSS:3.1/AV:P/AC:H/PR:L/UI:R/S:C/C:H/I:H/A:H", 7.0),
    ],
)
def test_cvss3_base_score(vector: str, expected: float) -> None:
    assert gate.cvss3_base_score(vector) == pytest.approx(expected, abs=0.05)


def test_cvss3_base_score_rejects_non_v3() -> None:
    with pytest.raises(ValueError, match="not a CVSS v3.x vector"):
        gate.cvss3_base_score("AV:N/AC:L/Au:N/C:P/I:P/A:P")  # a CVSS v2 vector


@pytest.mark.parametrize(
    ("cvss", "expected"),
    [
        (None, None),
        (9.1, 9.1),
        ("7.5", 7.5),
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H", 7.5),
        ("AV:N/AC:L/Au:N/C:P/I:P/A:P", None),  # v2 vector -> unscored
        ("garbage", None),
    ],
)
def test_score_of(cvss: object, expected: float | None) -> None:
    assert gate.score_of(cvss) == expected


def _report(*vulns: dict, warnings: dict | None = None) -> dict:
    return {
        "vulnerabilities": {"count": len(vulns), "list": list(vulns)},
        "warnings": warnings or {},
    }


def _vuln(advisory_id: str, cvss: object) -> dict:
    return {
        "package": {"version": "1.0.0"},
        "advisory": {"id": advisory_id, "package": "pkg", "title": "t", "cvss": cvss},
    }


def test_blocks_on_high_severity() -> None:
    report = _report(_vuln("RUSTSEC-2026-0195", "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"))
    assert gate.evaluate(report) == 1


def test_passes_below_threshold() -> None:
    report = _report(_vuln("X-1", "CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N"))
    assert gate.evaluate(report) == 0


def test_blocks_at_changed_scope_boundary() -> None:
    # v3.1 scores this exactly 7.0 and must block; the v3.0 formula scored it
    # 6.9 and let it through — the silent miss this gate exists to prevent.
    report = _report(_vuln("X-3", "CVSS:3.1/AV:P/AC:H/PR:L/UI:R/S:C/C:H/I:H/A:H"))
    assert gate.evaluate(report) == 1


def test_unscored_vuln_does_not_block() -> None:
    assert gate.evaluate(_report(_vuln("X-2", None))) == 0


def test_warnings_do_not_block() -> None:
    report = _report(warnings={"unmaintained": [{"a": 1}], "unsound": [{"b": 2}]})
    assert gate.evaluate(report) == 0


def test_missing_vulnerabilities_key_fails_closed() -> None:
    assert gate.evaluate({"warnings": {}}) == 1


def test_main_fails_closed_on_malformed_report(tmp_path: Path) -> None:
    bad = tmp_path / "cargo-audit.json"
    bad.write_text("not json {", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        gate.main(str(bad))


def test_main_passes_clean_report(tmp_path: Path) -> None:
    clean = tmp_path / "cargo-audit.json"
    clean.write_text(json.dumps(_report()), encoding="utf-8")
    assert gate.main(str(clean)) == 0
