"""Tests for the npm audit gate (scripts/ci/npm_audit_gate.py).

The gate must block on an unaccepted high/critical advisory, accept one only by
its exact ID, not count propagated string ``via`` entries as extra advisories, and
fail closed on a missing, malformed or unrecognised report.
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


def _report(vulnerabilities: dict) -> dict:
    return {"auditReportVersion": 2, "vulnerabilities": vulnerabilities}


def _braces_report() -> dict:
    # Shape of the real 2026-10 report: one advisory on braces, propagated up the
    # stylelint chain as string ``via`` entries.
    return _report(
        {
            "braces": {"severity": "high", "via": [_advisory(BRACES, "high", "braces")]},
            "micromatch": {"severity": "high", "via": ["braces"]},
            "stylelint": {"severity": "high", "via": ["micromatch"]},
        }
    )


def test_advisory_id_from_url() -> None:
    assert gate.advisory_id(_advisory(BRACES, "high")) == BRACES


def test_advisory_id_falls_back_to_source() -> None:
    assert gate.advisory_id({"source": 1240992, "url": ""}) == "1240992"


def test_blocks_on_high() -> None:
    assert gate.evaluate(_braces_report(), set()) == 1


def test_blocks_on_critical() -> None:
    report = _report({"a": {"via": [_advisory("GHSA-aaaa", "critical")]}})
    assert gate.evaluate(report, set()) == 1


def test_ignored_advisory_does_not_hide_another_critical() -> None:
    # The deployed configuration: braces is always ignored.
    report = _braces_report()
    report["vulnerabilities"]["x"] = {
        "severity": "critical",
        "via": [_advisory("GHSA-cccc", "critical")],
    }
    assert gate.evaluate(report, {BRACES}) == 1


@pytest.mark.parametrize("severity", ["moderate", "low", "info"])
def test_below_threshold_does_not_block(severity: str) -> None:
    report = _report({"a": {"severity": severity, "via": [_advisory("GHSA-aaaa", severity)]}})
    assert gate.evaluate(report, set()) == 0


@pytest.mark.parametrize("severity", ["High", None, ""])
def test_unrecognised_severity_blocks(severity: str | None) -> None:
    report = _report({"a": {"via": [_advisory("GHSA-aaaa", "x") | {"severity": severity}]}})
    assert gate.evaluate(report, set()) == 1


def test_propagated_entries_count_as_one_advisory(capsys: pytest.CaptureFixture[str]) -> None:
    gate.evaluate(_braces_report(), {BRACES})
    assert "npm audit: 1 advisories." in capsys.readouterr().out


def test_ignore_accepts_listed_advisory(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.evaluate(_braces_report(), {BRACES}) == 0
    assert "::warning::" not in capsys.readouterr().out


def test_ignore_does_not_cover_another_advisory() -> None:
    report = _braces_report()
    report["vulnerabilities"]["devalue"] = {"via": [_advisory("GHSA-bbbb", "high")]}
    assert gate.evaluate(report, {BRACES}) == 1


def test_stale_ignore_warns_but_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.evaluate(_report({}), {BRACES}) == 0
    assert f"--ignore {BRACES} matched nothing" in capsys.readouterr().out


@pytest.mark.parametrize(
    "entry",
    [
        # Advisory outside ``via``, where the parser does not look.
        {"severity": "critical", "advisories": [{"severity": "critical"}]},
        # ``via`` string naming a package that is not in the report.
        {"severity": "high", "via": ["ghost"]},
        # ``via`` as a bare string rather than a list.
        {"severity": "critical", "via": "GHSA-cccc"},
        # Severity unrecognised at package level, nothing behind it.
        {"severity": "High", "via": []},
    ],
)
def test_untraced_package_fails_closed_while_braces_ignored(entry: dict) -> None:
    report = _braces_report()
    report["vulnerabilities"]["x"] = entry
    assert gate.evaluate(report, {BRACES}) == 1


def test_high_package_with_only_a_moderate_advisory_fails_closed() -> None:
    report = _report({"a": {"severity": "high", "via": [_advisory("GHSA-aaaa", "moderate")]}})
    assert gate.evaluate(report, set()) == 1


def test_via_cycle_is_traced_without_recursing_forever() -> None:
    # npm can link packages to each other; the chain still ends at braces.
    report = _braces_report()
    report["vulnerabilities"]["a"] = {"severity": "high", "via": ["b", "braces"]}
    report["vulnerabilities"]["b"] = {"severity": "high", "via": ["a"]}
    assert gate.evaluate(report, {BRACES}) == 0


def test_critical_on_ignored_chain_package_fails_closed() -> None:
    # A new critical advisory on micromatch, outside ``via``: its string link to the
    # ignored high braces advisory must not account for a critical package.
    report = _braces_report()
    report["vulnerabilities"]["micromatch"] = {
        "severity": "critical",
        "via": ["braces"],
        "advisories": [_advisory("GHSA-eeee", "critical", "micromatch")],
    }
    assert gate.evaluate(report, {BRACES}) == 1


def test_critical_linked_into_ignored_high_chain_fails_closed() -> None:
    report = _braces_report()
    report["vulnerabilities"]["x"] = {"severity": "critical", "via": ["micromatch"]}
    assert gate.evaluate(report, {BRACES}) == 1


def test_critical_linked_only_to_moderate_package_fails_closed() -> None:
    report = _report(
        {
            "m": {"severity": "moderate", "via": [_advisory("GHSA-mmmm", "moderate")]},
            "x": {"severity": "critical", "via": ["m"]},
        }
    )
    assert gate.evaluate(report, set()) == 1


def test_id_collision_keeps_the_blocking_advisory() -> None:
    low = {"name": "y", "severity": "low"}
    critical = {"name": "z", "severity": "critical"}
    report = _braces_report()
    report["vulnerabilities"]["y"] = {"severity": "low", "via": [low]}
    report["vulnerabilities"]["z"] = {"severity": "critical", "via": [critical]}
    assert gate.evaluate(report, {BRACES}) == 1


@pytest.mark.parametrize("version", [1, 3, None])
def test_other_report_versions_fail_closed(version: int | None) -> None:
    report = _report({}) | {"auditReportVersion": version}
    assert gate.evaluate(report, set()) == 1


def test_registry_error_fails_closed() -> None:
    # What npm 11 writes to stdout when the registry request fails.
    error = {"message": "request to ... failed", "error": {"summary": "", "detail": ""}}
    assert gate.evaluate(error, set()) == 1


def test_missing_vulnerabilities_fails_closed() -> None:
    assert gate.evaluate({"auditReportVersion": 2}, set()) == 1


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
