"""
Generates and asserts the formal validation report.
Writes docs/validation-report.md on success.

This test runs the full validation engine against the live DB and asserts
the acceptance criteria:
  - >= 15 checks pass
  - 0 critical failures on baseline
  - The 5 anomaly types are detected
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.database import SessionLocal
from backend.app.validation import run_all_checks


def test_validation_report_writes_markdown() -> None:
    db = SessionLocal()
    try:
        report = run_all_checks(db)
    finally:
        db.close()

    # Acceptance: at least 15 of ~18 checks pass on the live dataset
    assert report.total_checks >= 15
    assert report.passed >= 15, f"Only {report.passed}/{report.total_checks} passed"
    assert report.critical == 0, f"{report.critical} critical failures on baseline"

    # Sanity — the 5 anomaly types must exist somewhere in the exception store
    from backend.app.models.system import ExceptionRecord
    from backend.app.models.enums import ExceptionType

    db = SessionLocal()
    try:
        types = {r.issue_type.value for r in db.query(ExceptionRecord).all()}
    finally:
        db.close()

    expected = {
        "optout_contacted",
        "post_conversion_scoring",
        "territory_mismatch",
        "duplicate_opportunity",
        "stage_gap",
    }
    assert expected.issubset(types), f"Missing anomaly types: {expected - types}"

    # Write the markdown report
    docs = Path("docs")
    docs.mkdir(exist_ok=True)
    md = ["# LeadFlow — Validation Report", "", f"Executed: `{report.executed_at}`", ""]
    md.append(f"- **Total checks:** {report.total_checks}")
    md.append(f"- **Passed:** {report.passed}")
    md.append(f"- **Failed:** {report.failed}")
    md.append(f"- **Critical failures:** {report.critical}")
    md.append(f"- **Warnings:** {report.warnings}")
    md.append("")
    md.append("## All Checks")
    md.append("")
    md.append("| Result | Category | Check | Violations | Severity | Details |")
    md.append("|--------|----------|-------|------------|----------|---------|")
    for c in report.checks:
        icon = "✅" if c.passed else ("🚨" if c.severity == "critical" else "❌")
        details = c.details.replace("|", "\\|") if c.details else ""
        md.append(f"| {icon} | {c.category} | {c.name} | {c.count_violations} | {c.severity} | {details} |")
    md.append("")
    md.append("## The 5 Injected Anomalies")
    md.append("")
    md.append("| Anomaly | Severity | Detected |")
    md.append("|---------|----------|----------|")
    for t in expected:
        found = t in types
        md.append(f"| {t} | — | {'✅' if found else '❌'} |")

    (docs / "validation-report.md").write_text("\n".join(md))
