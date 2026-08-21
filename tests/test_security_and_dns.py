from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import dns.exception
import dns.resolver
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from mailtrace.config import Settings
from mailtrace.db import Base
from mailtrace.dns_lookup import _query, lookup_dns, validate_domain
from mailtrace.models import DNSCache
from mailtrace.parser import ParseLimitError, parse_evidence, safe_filename


class Answer:
    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter([SimpleNamespace(to_text=lambda: '"v=spf1 -all"')])


class Resolver:
    timeout = 1.0
    lifetime = 1.0

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def resolve(self, _name: str, _type: str, lifetime: float):  # type: ignore[no-untyped-def]
        assert lifetime == self.lifetime
        if self.error:
            raise self.error
        return Answer()


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (dns.resolver.NXDOMAIN(), "nxdomain"),  # type: ignore[no-untyped-call]
        (dns.resolver.NoAnswer(), "no_answer"),  # type: ignore[no-untyped-call]
        (dns.resolver.NoNameservers(), "servfail"),  # type: ignore[no-untyped-call]
        (dns.exception.Timeout(), "timeout"),  # type: ignore[no-untyped-call]
    ],
)
def test_dns_query_statuses(error: Exception, status: str) -> None:
    assert _query(Resolver(error), "example.com", "TXT")["status"] == status  # type: ignore[arg-type]


def test_dns_validation_lookup_and_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert validate_domain("Example.COM.") == "example.com"
    for invalid in ("localhost", "-bad.example", "bad..example"):
        with pytest.raises(ValueError):
            validate_domain(invalid)
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    settings = Settings(data_dir=tmp_path / "data")
    monkeypatch.setattr(dns.resolver, "Resolver", lambda configure=True: Resolver())
    with Session(engine) as db:
        first = lookup_dns(db, "example.com", "selector", settings)
        assert first["cache"] == "miss"
        assert len(first["queries"]) == 6
        second = lookup_dns(db, "example.com", "selector", settings)
        assert second["cache"] == "hit"
        assert db.get(DNSCache, "example.com|selector") is not None
        with pytest.raises(ValueError):
            lookup_dns(db, "example.com", "bad selector!", settings)


def test_parser_security_boundaries_and_url_inventory(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", max_upload_bytes=2048)
    assert safe_filename("CON:<bad>.eml").endswith(".eml")
    assert safe_filename("...") == "evidence"
    with pytest.raises(ValueError, match="empty"):
        parse_evidence(b"", "headers", settings)
    with pytest.raises(ParseLimitError, match="Null"):
        parse_evidence(b"From: a@example.com\x00\r\n\r\n", "headers", settings)
    with pytest.raises(ParseLimitError, match="exceeds"):
        parse_evidence(b"x" * 2049, "headers", settings)
    raw = (
        b"From: Alice <alice@example.com>\r\n"
        b"Subject: URL test\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n\r\n"
        b"<script>alert(1)</script><a href='https://example.com'>visit</a> "
        b"https://example.net/path"
    )
    result = parse_evidence(raw, "eml", settings)
    assert result["mime_structure"]["html_available"] is True
    assert result["mime_structure"]["html_rendered"] is False
    assert {item["url"] for item in result["urls"]} == {
        "https://example.com",
        "https://example.net/path",
    }
