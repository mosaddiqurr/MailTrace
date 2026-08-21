from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import dns.exception
import dns.resolver
from sqlalchemy.orm import Session

from mailtrace.config import Settings
from mailtrace.models import DNSCache

LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.I)


def validate_domain(value: str) -> str:
    domain = value.strip().rstrip(".").lower()
    try:
        ascii_domain = domain.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("Domain is not valid IDNA") from exc
    if len(ascii_domain) > 253 or not all(
        LABEL_RE.fullmatch(label) for label in ascii_domain.split(".")
    ):
        raise ValueError("Domain syntax is invalid")
    if "." not in ascii_domain:
        raise ValueError("A fully qualified domain is required")
    return ascii_domain


def _query(
    resolver: dns.resolver.Resolver, name: str, record_type: str, max_values: int = 30
) -> dict[str, Any]:
    started = datetime.now(UTC)
    try:
        answer = resolver.resolve(name, record_type, lifetime=resolver.lifetime)
        values = [item.to_text()[:4096] for item in list(answer)[:max_values]]
        status = "ok"
        error = None
    except dns.resolver.NXDOMAIN:
        values, status, error = [], "nxdomain", "The queried name does not exist"
    except dns.resolver.NoAnswer:
        values, status, error = [], "no_answer", "The name has no record of this type"
    except dns.resolver.NoNameservers:
        values, status, error = [], "servfail", "No nameserver returned a usable answer"
    except dns.exception.Timeout:
        values, status, error = [], "timeout", "The lookup timed out"
    elapsed = (datetime.now(UTC) - started).total_seconds() * 1000
    return {
        "name": name,
        "type": record_type,
        "status": status,
        "values": values,
        "error": error,
        "elapsed_ms": round(elapsed, 2),
    }


def lookup_dns(
    db: Session, domain_value: str, selector: str | None, settings: Settings
) -> dict[str, Any]:
    domain = validate_domain(domain_value)
    safe_selector = None
    if selector:
        safe_selector = selector.strip().lower()
        if not LABEL_RE.fullmatch(safe_selector):
            raise ValueError("DKIM selector syntax is invalid")
    cache_key = f"{domain}|{safe_selector or ''}"
    now = datetime.now(UTC)
    cached = db.get(DNSCache, cache_key)
    if cached and cached.expires_at.replace(tzinfo=UTC) > now:
        result = dict(cached.result)
        result["cache"] = "hit"
        return result

    resolver = dns.resolver.Resolver(configure=True)
    resolver.timeout = settings.dns_timeout_seconds
    resolver.lifetime = settings.dns_timeout_seconds
    queries = [
        _query(resolver, domain, "TXT"),
        _query(resolver, f"_dmarc.{domain}", "TXT"),
        _query(resolver, domain, "MX"),
        _query(resolver, domain, "A"),
        _query(resolver, domain, "AAAA"),
    ]
    if safe_selector:
        queries.append(_query(resolver, f"{safe_selector}._domainkey.{domain}", "TXT"))
    result = {
        "domain": domain,
        "selector": safe_selector,
        "looked_up_at": now.isoformat(),
        "cache": "miss",
        "notice": "Live DNS reflects lookup-time state, not the historical state when the message was sent.",
        "queries": queries,
    }
    expires = now + timedelta(seconds=settings.dns_cache_seconds)
    if cached:
        cached.result = result
        cached.expires_at = expires
    else:
        db.add(DNSCache(key=cache_key, result=result, expires_at=expires))
    db.commit()
    return result
