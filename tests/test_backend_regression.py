from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from mailtrace.api import list_analyses
from mailtrace.config import Settings
from mailtrace.models import Case, Evidence
from mailtrace.parser import ParseLimitError, parse_evidence, safe_filename
from mailtrace.reports import bundle_report, csv_report, html_report, json_report, pdf_report
from mailtrace.service import delete_original, ingest_evidence, prune_expired_analyses

FIXTURES = Path(__file__).parents[1] / "mailtrace" / "fixtures"


def parse_fixture(name: str, settings: Settings) -> dict[str, Any]:
    return parse_evidence((FIXTURES / f"{name}.eml").read_bytes(), "eml", settings)


def test_analysis_list_uses_joined_case_snapshot(db: Session, settings: Settings) -> None:
    case = Case(title="Concurrent listing")
    db.add(case)
    db.commit()
    db.refresh(case)
    evidence = ingest_evidence(
        db,
        case,
        b"From: Alice <alice@example.com>\r\nSubject: Snapshot\r\n\r\n",
        "snapshot.eml",
        "eml",
        False,
        settings,
    )

    # Reproduce the stale relationship state seen during concurrent delete/list requests.
    set_committed_value(evidence, "case", None)  # type: ignore[no-untyped-call]

    analyses = list_analyses(db, settings)
    assert [(item["id"], item["title"]) for item in analyses] == [
        (evidence.id, "Concurrent listing")
    ]


def test_folded_encoded_repeated_and_malformed_headers(settings: Settings) -> None:
    raw = (
        b"From: =?utf-8?Q?Jos=C3=A9_Example?= <jose@example.com>\r\n"
        b"Subject: =?utf-8?Q?Quarterly?=\r\n report\r\n"
        b"X-Trace: first\r\nX-Trace: second\r\n"
        b"line without a colon\r\nMessage-ID: <one@example.com>\r\n\r\n"
    )
    result = parse_evidence(raw, "headers", settings)
    parsed = result["parsed_message"]
    assert parsed["from"][0]["display_name"] == "José Example"
    assert parsed["subject"] == "Quarterly report"
    assert parsed["header_counts"]["x-trace"] == 2
    assert any(item["code"] == "malformed-line" for item in result["warnings"])
    assert [h["decoded_value"] for h in parsed["headers"] if h["name_lower"] == "x-trace"] == [
        "first",
        "second",
    ]


def test_authentication_alignment_dkim_and_arc(settings: Settings) -> None:
    result = parse_fixture("forwarded-message", settings)
    auth = result["authentication"]
    assert auth["spf"]["result"] == "pass"
    assert auth["dkim"]["result"] == "pass"
    assert auth["dmarc"]["result"] == "pass"
    assert auth["dkim"]["domain"] == "origin.example"
    assert auth["dkim"]["selector"] == "mail"
    assert auth["arc"]["chain_instances"] == [1]
    assert auth["alignment"]["dkim_aligned"] is True
    assert "AUTH-002" in {item["rule_id"] for item in result["observations"]}
    assert "fresh cryptographic verification" in auth["source_notice"]


def test_received_spf_fallback_and_alignment(settings: Settings) -> None:
    raw = (
        b"Received-SPF: softfail client-ip=198.51.100.2; envelope-from=return@bounce.example\r\n"
        b"From: Person <person@visible.example>\r\n"
        b"Message-ID: <m@visible.example>\r\n\r\n"
    )
    result = parse_evidence(raw, "headers", settings)
    auth = result["authentication"]
    assert auth["spf"]["result"] == "softfail"
    assert auth["spf"]["domain"] == "bounce.example"
    assert auth["alignment"]["spf_aligned"] is False
    rules = {item["rule_id"] for item in result["observations"]}
    assert {"AUTH-SPF-SOFTFAIL", "AUTH-SPF-ALIGN"} <= rules


def test_delivery_hop_order_timezone_and_timestamp_anomaly(settings: Settings) -> None:
    result = parse_fixture("timestamp-anomaly", settings)
    hops = result["hops"]
    assert [hop["sequence"] for hop in hops] == [1, 2]
    assert hops[0]["from_host"] == "app.monitor.example"
    assert hops[0]["timezone"] == "+0000"
    assert hops[0]["utc_time"].endswith("+00:00")
    assert hops[1]["delay_from_previous_seconds"] == -240
    assert "HOP-001" in {item["rule_id"] for item in result["observations"]}


def test_eml_attachment_metadata_and_limits(settings: Settings) -> None:
    result = parse_fixture("incomplete-auth", settings)
    attachment = result["attachments"][0]
    assert attachment["filename"] == "agenda.txt"
    assert attachment["content_type"] == "application/octet-stream"
    assert attachment["size"] > 0
    assert attachment["executed"] is False
    assert attachment["stored"] is False

    restrictive = Settings(data_dir=settings.data_dir / "restricted", max_attachments=0)
    restrictive.ensure_directories()
    with pytest.raises(ParseLimitError, match="Attachment count"):
        parse_evidence((FIXTURES / "incomplete-auth.eml").read_bytes(), "eml", restrictive)


@pytest.mark.parametrize(
    "fixture",
    [
        "aligned-business",
        "spf-fail-reply-to",
        "dkim-pass-dmarc-fail",
        "forwarded-message",
        "mailing-list",
        "malformed-headers",
        "punycode-domain",
        "timestamp-anomaly",
        "internal-relay",
        "incomplete-auth",
    ],
)
def test_all_demonstration_fixtures_are_parser_driven(fixture: str, settings: Settings) -> None:
    result = parse_fixture(fixture, settings)
    assert result["parser_version"]
    assert isinstance(result["observations"], list)
    assert all("rule_id" in observation for observation in result["observations"])
    forbidden = {"likely_legitimate", "suspicious", "inconclusive"}
    assert not forbidden.intersection(json.dumps(result).lower().split())
    assert result["assessment"]["label"] in {
        "No clear concern found",
        "Some evidence needs review",
        "Concerning evidence found",
        "Insufficient evidence",
        "Parsing incomplete",
    }


def test_expected_fixture_observations(settings: Settings) -> None:
    expected = json.loads((FIXTURES / "expected-observations.json").read_text(encoding="utf-8"))
    for fixture, expected_rules in expected.items():
        actual = {item["rule_id"] for item in parse_fixture(fixture, settings)["observations"]}
        assert set(expected_rules) <= actual, fixture


def test_persistence_retention_audit_and_exports(db: Session, settings: Settings) -> None:
    case = Case(title="Regression <case>", description="Persistence and report smoke")
    db.add(case)
    db.commit()
    raw = (FIXTURES / "aligned-business.eml").read_bytes()
    evidence = ingest_evidence(db, case, raw, "../aligned-business.eml", "eml", True, settings)

    assert evidence.original_filename == "aligned-business.eml"
    assert evidence.stored_filename
    stored_path = settings.evidence_dir / evidence.stored_filename
    assert stored_path.read_bytes() == raw
    reloaded = db.scalar(select(Evidence).where(Evidence.id == evidence.id))
    assert reloaded is not None and reloaded.sha256 == evidence.sha256
    assert any(entry.action == "evidence_ingested" for entry in case.audit_entries)

    html_bytes = html_report(case)
    assert html_bytes.startswith(b"<!doctype html>")
    assert b"Regression &lt;case&gt;" in html_bytes
    assert b"<script" not in html_bytes.lower()
    pdf_bytes = pdf_report(case)
    assert pdf_bytes.startswith(b"%PDF-") and len(pdf_bytes) > 1000
    exported = json.loads(json_report(case))
    assert exported["evidence"][0]["sha256"] == evidence.sha256
    csv_bytes = csv_report(case)
    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(csv_bytes[3:].decode("utf-8"))))
    assert rows[0][0] == "case_id"
    bundle = bundle_report(case, {evidence.id: raw})
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        names = archive.namelist()
        assert any(name.endswith("report.pdf") for name in names)
        assert any("/originals/" in name for name in names)

    delete_original(db, case, evidence, settings)
    db.refresh(case)
    assert evidence.stored_filename is None
    assert not stored_path.exists()
    assert evidence.parsed_message["subject"] == "Invoice status update"
    assert any(entry.action == "original_evidence_deleted" for entry in case.audit_entries)


def test_retention_prunes_expired_rows_and_originals(db: Session, settings: Settings) -> None:
    raw = (FIXTURES / "aligned-business.eml").read_bytes()
    old_case = Case(title="Expired", description="")
    current_case = Case(title="Current", description="")
    db.add_all([old_case, current_case])
    db.commit()
    old = ingest_evidence(db, old_case, raw, "old.eml", "eml", True, settings)
    current = ingest_evidence(db, current_case, raw, "current.eml", "eml", True, settings)
    old_path = settings.evidence_dir / str(old.stored_filename)
    old.uploaded_at = datetime.now(UTC) - timedelta(days=8)
    db.commit()

    assert prune_expired_analyses(db, settings, 7) == 1
    assert db.get(Evidence, old.id) is None
    assert db.get(Evidence, current.id) is not None
    assert not old_path.exists()


def test_csv_formula_neutralisation(db: Session) -> None:
    case = Case(title="CSV", description="")
    Evidence(
        case=case,
        original_filename="x.eml",
        sha256="0" * 64,
        file_size=1,
        input_type="eml",
        parser_version="test",
        observations=[
            {
                "rule_id": "=1+1",
                "severity": "low",
                "confidence": "high",
                "evidence_level": "Direct header fact",
                "title": "+SUM(A1:A2)",
                "description": "@payload",
                "supporting_headers": ["-header"],
                "recommended_action": "\tformula",
            }
        ],
    )
    db.add(case)
    db.commit()
    rows = list(csv.reader(io.StringIO(csv_report(case)[3:].decode("utf-8"))))
    values = rows[1]
    assert values[2].startswith("'=")
    assert values[6].startswith("'+")
    assert values[7].startswith("'@")
    assert values[8].startswith("'-")
    assert values[9].startswith("'\t")


def test_safe_filename_blocks_traversal() -> None:
    assert safe_filename("../../evil.eml") == "evil.eml"
    assert safe_filename("..\\..\\evil.eml") == "evil.eml"
