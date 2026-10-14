"""Tests for the npm audit gate (scripts/ci/npm_audit_gate.py).

The gate must block on an unaccepted high/critical advisory, accept one only by
its exact ID, not count propagated string ``via`` entries as extra advisories, and
fail closed on a missing/malformed report.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "npm_audit_gate.py"
_spec = importlib.util.spec_from_file_location("npm_audit_gate", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

BRACES = "GHSA-vfj7-8cjw-p6xm"


def _advisory(ghsa: str, severity: str, name: str = "pkg") -> dict:
    return {
        "source": 1,
        "name": name,
        "title": "t",
        "url": f"https://github.com/advisories/{ghsa}",
        "severity": severity,
        "range": "*",
    }


def _braces_report() -> dict:
    # Shape of the real 2026-10 report: one advisory on braces, propagated up the
    # stylelint chain as string ``via`` entries.
    return {
        "auditReportVersion": 2,
        "vulnerabilities": {
            "braces": {"severity": "high", "via": [_advisory(BRACES, "high", "braces")]},
            "micromatch": {"severity": "high", "via": ["braces"]},
            "stylelint": {"severity": "high", "via": ["micromatch"]},
        },
    }


def test_advisory_id_from_url() -> None:
    assert gate.advisory_id(_advisory(BRACES, "high")) == BRACES


def test_advisory_id_falls_back_to_source() -> None:
    assert gate.advisory_id({"source": 1240992, "url": ""}) == "1240992"


def test_blocks_on_high() -> None:
    assert gate.evaluate(_braces_report(), set()) == 1


def test_blocks_on_critical() -> None:
    report = {"vulnerabilities": {"a": {"via": [_advisory("GHSA-aaaa", "critical")]}}}
    assert gate.evaluate(report, set()) == 1


@pytest.mark.parametrize("severity", ["moderate", "low", "info"])
def test_below_threshold_does_not_block(severity: str) -> None:
    report = {"vulnerabilities": {"a": {"via": [_advisory("GHSA-aaaa", severity)]}}}
    assert gate.evaluate(report, set()) == 0


def test_ignore_accepts_listed_advisory() -> None:
    assert gate.evaluate(_braces_report(), {BRACES}) == 0


def test_ignore_does_not_cover_another_advisory() -> None:
    report = _braces_report()
    report["vulnerabilities"]["devalue"] = {"via": [_advisory("GHSA-bbbb", "high")]}
    assert gate.evaluate(report, {BRACES}) == 1


def test_stale_ignore_warns_but_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.evaluate({"vulnerabilities": {}}, {BRACES}) == 0
    assert f"--ignore {BRACES} matched nothing" in capsys.readouterr().out


def test_missing_vulnerabilities_key_fails_closed() -> None:
    # npm writes {"error": {...}} when the registry request fails.
    assert gate.evaluate({"error": {"code": "ENOTFOUND"}}, set()) == 1


def test_main_fails_closed_on_malformed_report(tmp_path: Path) -> None:
    bad = tmp_path / "npm-audit.json"
    bad.write_text("not json {", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        gate.main([str(bad)])


def test_main_passes_ignore_flags(tmp_path: Path) -> None:
    path = tmp_path / "npm-audit.json"
    path.write_text(json.dumps(_braces_report()), encoding="utf-8")
    assert gate.main([str(path)]) == 1
    assert gate.main([str(path), "--ignore", BRACES]) == 0
