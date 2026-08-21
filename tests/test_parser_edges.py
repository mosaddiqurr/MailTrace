from __future__ import annotations

from email import policy
from email.parser import BytesParser

import pytest

from mailtrace import parser
from mailtrace.config import Settings


def test_header_limit_and_malformed_line_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings()
    settings.max_header_line_bytes = 8
    with pytest.raises(parser.ParseLimitError, match="Header line"):
        parser.parse_evidence(b"Subject: too long\r\n\r\n", "headers", settings)

    settings = Settings()
    settings.max_headers = 1
    with pytest.raises(parser.ParseLimitError, match="Header count"):
        parser.parse_evidence(b"From: a@b.test\r\nTo: c@d.test\r\n\r\n", "headers", settings)

    records, warnings, _ = parser._extract_raw_headers(  # noqa: SLF001
        b" orphan\r\nbroken\r\nBad Name: value\r\nFrom: a@b.test\rSubject: x\n\n",
        Settings(),
    )
    assert records
    assert {"orphan-fold", "malformed-line", "invalid-name", "mixed-newlines"} <= {
        warning["code"] for warning in warnings
    }

    monkeypatch.setattr(parser, "make_header", lambda _value: (_ for _ in ()).throw(ValueError()))
    assert parser._decode("unchanged") == "unchanged"  # noqa: SLF001
    assert parser._normalise_domain("\ud800.example") == "\ud800.example"  # noqa: SLF001
    assert parser._normalise_domain("...") is None  # noqa: SLF001


def test_received_and_assessment_edge_branches() -> None:
    no_separator = parser._parse_received("from lone-host", 1)  # noqa: SLF001
    assert "No timestamp separator found" in no_separator["warnings"]
    assert no_separator["confidence"] == "medium"

    naive = parser._parse_received(  # noqa: SLF001
        "from a.test by b.test; Wed, 01 Jan 2025 12:00:00", 1
    )
    assert "Timestamp has no timezone" in naive["warnings"]

    invalid = parser._parse_received("from a.test by b.test; not-a-date", 1)  # noqa: SLF001
    assert "Timestamp could not be parsed" in invalid["warnings"]

    assessment, _ = parser._assessment(  # noqa: SLF001
        [], [{"code": "malformed", "message": "Malformed"}], {"methods": []}
    )
    assert assessment["label"] == "Parsing incomplete"


def test_observation_edge_branches() -> None:
    raw = (
        b"From: bank.example <one@a.b.c.d.e.f.example>\r\n"
        b"From: duplicate@other.test\r\n"
        b"Message-ID: <one@example.test>\r\n"
        b"Message-ID: <two@example.test>\r\n"
        b"X-Originating-IP: 192.0.2.1\r\n"
        b"X-Client-IP: 192.0.2.2\r\n"
        b"X-Mailer: Bulk Mailer\r\n"
        b"Received: unstructured hop\r\n\r\n"
    )
    result = parser.parse_evidence(raw, "headers", Settings())
    rule_ids = {item["rule_id"] for item in result["observations"]}
    assert {
        "ID-006",
        "DOM-003",
        "HOP-003",
        "HOP-004",
        "HOP-005",
        "META-002",
        "META-005",
        "ID-007",
    } <= rule_ids


def test_mime_limit_branches() -> None:
    message = BytesParser(policy=policy.default).parsebytes(  # type: ignore[arg-type]
        b"Content-Type: multipart/mixed; boundary=x\r\n\r\n"
        b"--x\r\nContent-Type: text/plain\r\n\r\none\r\n"
        b"--x\r\nContent-Type: text/plain\r\n\r\ntwo\r\n--x--\r\n"
    )
    with pytest.raises(parser.ParseLimitError, match="part count"):
        parser._mime_and_urls(message, "eml", Settings(max_mime_parts=1))  # noqa: SLF001
    nested = BytesParser(policy=policy.default).parsebytes(  # type: ignore[arg-type]
        b"Content-Type: multipart/mixed; boundary=outer\r\n\r\n"
        b"--outer\r\nContent-Type: multipart/mixed; boundary=inner\r\n\r\n"
        b"--inner\r\nContent-Type: text/plain\r\n\r\ntext\r\n--inner--\r\n"
        b"--outer--\r\n"
    )
    with pytest.raises(parser.ParseLimitError, match="nesting"):
        parser._mime_and_urls(nested, "eml", Settings(max_mime_depth=1))  # noqa: SLF001
    part_limited = Settings()
    part_limited.max_part_bytes = 1
    with pytest.raises(parser.ParseLimitError, match="decoded MIME part"):
        parser._mime_and_urls(message, "eml", part_limited)  # noqa: SLF001
    total_limited = Settings()
    total_limited.max_part_bytes = 10
    total_limited.max_decoded_bytes = 2
    with pytest.raises(parser.ParseLimitError, match="Decoded MIME content"):
        parser._mime_and_urls(message, "eml", total_limited)  # noqa: SLF001

    url_message = BytesParser(policy=policy.default).parsebytes(  # type: ignore[arg-type]
        b"Content-Type: text/plain\r\n\r\nhttps://one.test https://two.test"
    )
    with pytest.raises(parser.ParseLimitError, match="URL count"):
        parser._mime_and_urls(url_message, "eml", Settings(max_urls=1))  # noqa: SLF001
