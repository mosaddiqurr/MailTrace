from __future__ import annotations

import hashlib
import json
import socket
import urllib.request
from typing import Any

import pytest
from sqlalchemy.orm import Session

from mailtrace import parser
from mailtrace.config import Settings
from mailtrace.models import Case
from mailtrace.parser import parse_evidence
from mailtrace.reports import html_report, pdf_report
from mailtrace.service import ingest_evidence


def _headers(*lines: str) -> bytes:
    return ("\r\n".join(lines) + "\r\n\r\n").encode()


def _observation(result: dict[str, Any], rule_id: str) -> dict[str, Any]:
    return next(item for item in result["observations"] if item["rule_id"] == rule_id)


def test_benign_authentication_has_clean_entities_and_no_observations(settings: Settings) -> None:
    raw = _headers(
        "From: Alice <alice@northbridge.example>",
        "To: Bob <bob@recipient.example>",
        "Message-ID: <alert-88271@northbridge.example>",
        "Authentication-Results: mx.recipient.example; spf=pass smtp.mailfrom=alice@northbridge.example; dkim=pass header.d=northbridge.example header.s=mail; dmarc=pass header.from=northbridge.example",
    )
    result = parse_evidence(raw, "headers", settings)

    assert result["authentication"]["spf"]["result"] == "pass"
    assert result["authentication"]["dkim"]["result"] == "pass"
    assert result["authentication"]["dmarc"]["result"] == "pass"
    assert result["authentication"]["alignment"]["spf_aligned"] is True
    assert result["authentication"]["alignment"]["dkim_aligned"] is True
    assert result["observations"] == []

    entities = {(item["type"], item["value"]) for item in result["entities"]}
    assert ("message_identifier", "<alert-88271@northbridge.example>") in entities
    assert ("email_address", "alert-88271@northbridge.example") not in entities
    assert ("email_address", "alice@northbridge.example") in entities
    assert ("domain", "northbridge.example") in entities
    assert (
        not {
            ("domain", "header.from"),
            ("domain", "smtp.mailfrom"),
            ("email_address", "smtp.mailfrom=alice@northbridge.example"),
        }
        & entities
    )
    northbridge = next(
        item
        for item in result["entities"]
        if item["type"] == "domain" and item["value"] == "northbridge.example"
    )
    assert "authentication-results:smtp.mailfrom" in northbridge["sources"]
    assert "authentication-results:header.from" in northbridge["sources"]
    assert "message-id" in northbridge["sources"]


def test_spoofed_sender_rules_have_exact_relevant_evidence(settings: Settings) -> None:
    raw = _headers(
        "From: Security <alerts@northbridge.example>",
        "Reply-To: Help <help@evil-example.test>",
        "Return-Path: <mailer@evil-example.test>",
        "Message-ID: <alert-88271@evil-example.test>",
        "Authentication-Results: mx.recipient.example; spf=fail smtp.mailfrom=mailer@evil-example.test; dmarc=fail header.from=northbridge.example",
    )
    result = parse_evidence(raw, "headers", settings)

    assert {"ID-001", "ID-002", "ID-004", "AUTH-SPF-FAIL", "AUTH-DMARC-FAIL"} <= {
        item["rule_id"] for item in result["observations"]
    }
    assert _observation(result, "AUTH-SPF-FAIL")["supporting_headers"] == ["Authentication-Results"]
    assert _observation(result, "AUTH-DMARC-FAIL")["supporting_headers"] == [
        "Authentication-Results"
    ]
    assert _observation(result, "AUTH-SPF-ALIGN")["supporting_headers"] == [
        "Authentication-Results",
        "From",
    ]
    for observation in result["observations"]:
        assert observation["supporting_headers"] == list(
            dict.fromkeys(observation["supporting_headers"])
        )
        assert observation["evidence_reference"] == observation["supporting_headers"]

    entities = {(item["type"], item["value"]) for item in result["entities"]}
    assert ("email_address", "mailer@evil-example.test") in entities
    assert ("email_address", "smtp.mailfrom=mailer@evil-example.test") not in entities
    assert ("domain", "smtp.mailfrom") not in entities
    assert ("domain", "header.from") not in entities


def test_legitimate_reply_to_mismatch_is_review_evidence_not_verdict(settings: Settings) -> None:
    result = parse_evidence(
        _headers(
            "From: Billing <billing@northbridge.example>",
            "Reply-To: Support <ticket@support-vendor.example>",
            "Message-ID: <invoice@northbridge.example>",
            "Authentication-Results: mx.example; spf=pass smtp.mailfrom=billing@northbridge.example; dkim=pass header.d=northbridge.example; dmarc=pass header.from=northbridge.example",
        ),
        "headers",
        settings,
    )
    assert [result["authentication"][name]["result"] for name in ("spf", "dkim", "dmarc")] == [
        "pass",
        "pass",
        "pass",
    ]
    observation = _observation(result, "ID-001")
    assert observation["supporting_headers"] == ["From", "Reply-To"]
    assert "ticketing" in observation["benign_alternatives"]
    assert "malicious" not in " ".join(
        str(observation[key]).lower()
        for key in ("title", "description", "explanation", "recommended_action")
    )


@pytest.mark.parametrize(
    ("value", "classification", "is_private", "is_global"),
    [
        ("10.0.0.5", "private", True, False),
        ("172.16.20.10", "private", True, False),
        ("192.168.1.10", "private", True, False),
        ("127.0.0.1", "loopback", False, False),
        ("169.254.10.10", "link_local", False, False),
        ("8.8.8.8", "global", False, True),
        ("192.0.2.25", "documentation", False, False),
        ("198.51.100.88", "documentation", False, False),
        ("203.0.113.45", "documentation", False, False),
        ("2001:db8::25", "documentation", False, False),
        ("fd00::5", "private", True, False),
        ("::1", "loopback", False, False),
    ],
)
def test_forensic_ip_classification(
    value: str, classification: str, is_private: bool, is_global: bool
) -> None:
    result = parser._ip_classification(value)  # noqa: SLF001
    assert result["classification"] == classification
    assert result["is_private"] is is_private
    assert result["is_global"] is is_global


def test_multi_hop_order_utc_and_documentation_classification(settings: Settings) -> None:
    result = parse_evidence(
        _headers(
            "Received: from relay.example (relay.example [8.8.8.8]) by mx.example with ESMTP; Tue, 18 Aug 2026 10:02:00 +0800",
            "Received: from client.example (client.example [203.0.113.45]) by relay.example with ESMTP; Tue, 18 Aug 2026 02:00:00 +0000",
            "From: Alice <alice@example.com>",
            "Message-ID: <one@example.com>",
            "Authentication-Results: mx.example; spf=pass smtp.mailfrom=alice@example.com; dkim=pass header.d=example.com; dmarc=pass header.from=example.com",
        ),
        "headers",
        settings,
    )
    assert [hop["sequence"] for hop in result["hops"]] == [1, 2]
    assert result["hops"][0]["utc_time"] == "2026-08-18T02:00:00+00:00"
    assert result["hops"][0]["is_private_ip"] is False
    assert result["hops"][0]["ip_classification"]["classification"] == "documentation"
    assert result["hops"][1]["ip_classification"]["classification"] == "global"


@pytest.mark.parametrize(
    ("value", "from_host", "from_ip", "by_host"),
    [
        ("by mx.example.test; Tue, 18 Aug 2026 02:00:00 +0000", None, None, "mx.example.test"),
        (
            "by 2002:a05:620a:100::10 with SMTP id abc123; Tue, 18 Aug 2026 02:00:00 +0000",
            None,
            None,
            "2002:a05:620a:100::10",
        ),
        (
            "from relay.example (relay.example [203.0.113.45]) by mx.example.test; Tue, 18 Aug 2026 02:00:00 +0000",
            "relay.example",
            "203.0.113.45",
            "mx.example.test",
        ),
        (
            "from relay.example 198.51.100.88 by mx.example.test; Tue, 18 Aug 2026 02:00:00 +0000",
            "relay.example",
            "198.51.100.88",
            "mx.example.test",
        ),
        (
            "from relay.example [2001:db8::25] by mx.example.test; Tue, 18 Aug 2026 02:00:00 +0000",
            "relay.example",
            "2001:db8::25",
            "mx.example.test",
        ),
    ],
)
def test_received_source_ip_is_limited_to_from_clause(
    value: str, from_host: str | None, from_ip: str | None, by_host: str
) -> None:
    hop = parser._parse_received(value, 1)  # noqa: SLF001
    assert hop["from_host"] == from_host
    assert hop["from_ip"] == from_ip
    assert hop["by_host"] == by_host


def test_forwarded_results_remain_independent(settings: Settings) -> None:
    result = parse_evidence(
        _headers(
            "From: Alice <alice@origin.example>",
            "Message-ID: <forwarded@origin.example>",
            "Authentication-Results: mx.example; spf=fail smtp.mailfrom=forwarder@relay.example; dkim=pass header.d=origin.example; dmarc=pass header.from=origin.example",
            "List-Id: Forwarding List <list.relay.example>",
        ),
        "headers",
        settings,
    )
    assert result["authentication"]["spf"]["result"] == "fail"
    assert result["authentication"]["dkim"]["result"] == "pass"
    assert result["authentication"]["dmarc"]["result"] == "pass"
    assert "spf fail = malicious" not in json.dumps(result).lower()
    assert "Forwarding" in _observation(result, "AUTH-SPF-FAIL")["benign_alternatives"]


def test_full_eml_reports_mime_link_mismatch_and_attachment_without_network(
    db: Session, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("report generation must not use the network")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(urllib.request, "urlopen", fail_network)
    raw = (
        b"From: Security <alerts@northbridge.example>\r\n"
        b"To: User <user@recipient.example>\r\n"
        b"Subject: Account notice\r\n"
        b"Message-ID: <notice@northbridge.example>\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: multipart/mixed; boundary=mailtrace-boundary\r\n\r\n"
        b"--mailtrace-boundary\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
        b'<p>Review:</p><a href="https://login-northbridge.example.net/verify">'
        b"https://portal.northbridge.example</a><script>alert(1)</script>\r\n"
        b"--mailtrace-boundary\r\n"
        b"Content-Type: application/octet-stream; name=notice.txt\r\n"
        b"Content-Disposition: attachment; filename=notice.txt\r\n"
        b"Content-ID: <attachment-1>\r\n"
        b"Content-Transfer-Encoding: base64\r\n\r\naGFybWxlc3M=\r\n"
        b"--mailtrace-boundary--\r\n"
    )
    result = parse_evidence(raw, "eml", settings)
    link = next(
        item
        for item in result["urls"]
        if item["url"] == "https://login-northbridge.example.net/verify"
    )
    assert link["displayed_destination"] == "portal.northbridge.example"
    assert link["host"] == "login-northbridge.example.net"
    assert link["display_href_mismatch"] is True
    assert link["fetched"] is False
    assert result["mime_structure"]["part_count"] == 3
    assert result["mime_structure"]["html_available"] is True
    assert result["mime_structure"]["html_rendered"] is False

    attachment = result["attachments"][0]
    assert attachment == {
        "filename": "notice.txt",
        "declared_filename": "notice.txt",
        "content_type": "application/octet-stream",
        "content_disposition": "attachment",
        "content_id": "attachment-1",
        "extension": "txt",
        "size": 8,
        "sha256": hashlib.sha256(b"harmless").hexdigest(),
        "executed": False,
        "stored": False,
    }

    case = Case(title="Full phishing regression", description="Synthetic safe evidence")
    db.add(case)
    db.commit()
    ingest_evidence(db, case, raw, "synthetic-phishing.eml", "eml", False, settings)
    html = html_report(case).decode()
    assert "MIME structure" in html
    assert "notice.txt" in html
    assert attachment["sha256"] in html
    assert "Displayed destination" in html
    assert "portal.northbridge.example" in html
    assert "login-northbridge.example.net" in html
    assert "Mismatch" in html and ">Yes<" in html
    assert "<script>alert(1)</script>" not in html
    assert pdf_report(case).startswith(b"%PDF-")


def test_header_only_report_states_body_evidence_is_unavailable(
    db: Session, settings: Settings
) -> None:
    case = Case(title="Headers only", description="")
    db.add(case)
    db.commit()
    ingest_evidence(
        db,
        case,
        _headers("From: Alice <alice@example.com>", "Message-ID: <one@example.com>"),
        "headers.txt",
        "headers",
        False,
        settings,
    )
    html = html_report(case).decode()
    assert "MIME/body evidence unavailable because only headers were supplied." in html
    assert "No attachments identified" not in html
    assert "No HTTP or HTTPS URLs identified" not in html
