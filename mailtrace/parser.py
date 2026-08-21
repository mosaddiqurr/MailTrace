from __future__ import annotations

import hashlib
import ipaddress
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from email import policy
from email.header import decode_header, make_header
from email.message import Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import PurePath
from typing import Any, Literal
from urllib.parse import urlsplit

from mailtrace.config import Settings

PARSER_VERSION = "1.2.0"
AUTH_RESULTS = {
    "pass",
    "fail",
    "softfail",
    "neutral",
    "none",
    "temperror",
    "permerror",
    "policy",
    "unknown",
}
EMAIL_RE = re.compile(r"(?<![\w.+-])([\w.!#$%&'*+/=?^`{|}~-]+)@([A-Za-z0-9._-]+|\[[^\]]+\])")
DOMAIN_RE = re.compile(
    r"(?<![\w@-])(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}(?![\w-])"
)
IP_RE = re.compile(
    r"(?<![\w:])(?:\d{1,3}\.){3}\d{1,3}(?![\w:])|(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])"
)
FREE_MAIL = {
    "freemail.example",
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "yahoo.com",
    "icloud.com",
    "proton.me",
    "protonmail.com",
    "aol.com",
}
URL_RE = re.compile(r"https?://[^\s<>'\"\])}]+", re.I)
PRIVATE_IP_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)
DOCUMENTATION_IP_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32")
)
STRUCTURED_ENTITY_HEADERS = {
    "authentication-results",
    "received-spf",
    "dkim-signature",
    "arc-authentication-results",
    "arc-seal",
    "arc-message-signature",
    "message-id",
    "received",
    "from",
    "sender",
    "reply-to",
    "return-path",
    "to",
    "cc",
}


class ParseLimitError(ValueError):
    """Raised when evidence crosses a configured security boundary."""


@dataclass(frozen=True)
class Address:
    display_name: str
    address: str
    domain: str | None

    def as_dict(self) -> dict[str, str | None]:
        return {"display_name": self.display_name, "address": self.address, "domain": self.domain}


class _HTMLLinkParser(HTMLParser):
    """Collect anchor metadata without rendering content or loading resources."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self._current: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = next((value for name, value in attrs if name.lower() == "href"), None)
        self._current = {"href": href or "", "text": []}

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current is None:
            return
        self.links.append(
            {
                "href": str(self._current["href"]).strip(),
                "text": re.sub(r"\s+", " ", "".join(self._current["text"])).strip(),
            }
        )
        self._current = None


def safe_filename(value: str, fallback: str = "evidence") -> str:
    name = PurePath(value.replace("\\", "/")).name.replace("\x00", "")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return (cleaned or fallback)[:120]


def _decode(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except (LookupError, UnicodeError, ValueError):
        return value


def _normalise_domain(value: str | None) -> str | None:
    if not value:
        return None
    domain = value.strip().strip("<>[]().,;:\"'").rstrip(".").lower()
    if not domain:
        return None
    try:
        return domain.encode("idna").decode("ascii")
    except UnicodeError:
        return domain


def _addresses(values: list[str]) -> list[Address]:
    parsed: list[Address] = []
    for display, addr in getaddresses(values):
        decoded_display = _decode(display)
        address = addr.strip()
        domain = _normalise_domain(address.rsplit("@", 1)[1]) if "@" in address else None
        parsed.append(Address(decoded_display, address, domain))
    return parsed


def _extract_raw_headers(
    data: bytes, settings: Settings
) -> tuple[list[dict[str, Any]], list[dict[str, str]], bytes]:
    normalised = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    header_blob = normalised.split(b"\n\n", 1)[0]
    physical = header_blob.split(b"\n")
    if any(len(line) > settings.max_header_line_bytes for line in physical):
        raise ParseLimitError(f"Header line exceeds {settings.max_header_line_bytes} bytes")

    warnings: list[dict[str, str]] = []
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line_number, raw_line in enumerate(physical, 1):
        text = raw_line.decode("utf-8", errors="replace")
        if raw_line[:1] in {b" ", b"\t"}:
            if current is None:
                warnings.append(
                    {
                        "code": "orphan-fold",
                        "message": f"Continuation line {line_number} has no parent header",
                    }
                )
                continue
            current["raw_value"] += "\n" + text
            current["unfolded_value"] += " " + text.strip()
            continue
        if b":" not in raw_line:
            if raw_line:
                warnings.append(
                    {
                        "code": "malformed-line",
                        "message": f"Header line {line_number} has no colon",
                        "raw": text[:500],
                    }
                )
            continue
        name_bytes, value_bytes = raw_line.split(b":", 1)
        name = name_bytes.decode("ascii", errors="replace").strip()
        if not name or not re.fullmatch(r"[!-9;-~]+", name):
            warnings.append(
                {
                    "code": "invalid-name",
                    "message": f"Header line {line_number} has an invalid field name",
                    "raw": text[:500],
                }
            )
        current = {
            "name": name,
            "name_lower": name.lower(),
            "raw_value": value_bytes.decode("utf-8", errors="replace").lstrip(),
            "unfolded_value": value_bytes.decode("utf-8", errors="replace").strip(),
            "decoded_value": "",
            "position": len(records),
            "line": line_number,
        }
        records.append(current)
        if len(records) > settings.max_headers:
            raise ParseLimitError(f"Header count exceeds {settings.max_headers}")
    for record in records:
        record["decoded_value"] = _decode(record["unfolded_value"])
    if b"\r\n" in data and (
        b"\n" in data.replace(b"\r\n", b"") or b"\r" in data.replace(b"\r\n", b"")
    ):
        warnings.append(
            {
                "code": "mixed-newlines",
                "message": "Mixed newline formats were normalised for parsing",
            }
        )
    return records, warnings, header_blob


def _values(headers: list[dict[str, Any]], name: str) -> list[str]:
    key = name.lower()
    return [str(h["decoded_value"]) for h in headers if h["name_lower"] == key]


def _first(headers: list[dict[str, Any]], name: str) -> str | None:
    values = _values(headers, name)
    return values[0] if values else None


def _address_field(headers: list[dict[str, Any]], name: str) -> list[dict[str, str | None]]:
    return [item.as_dict() for item in _addresses(_values(headers, name))]


def _domain_from_identity(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"@([A-Za-z0-9._-]+)", value)
    if not match:
        match = re.search(r"(?:^|\s)([A-Za-z0-9][A-Za-z0-9.-]+\.[A-Za-z]{2,63})(?:\s|$)", value)
    return _normalise_domain(match.group(1)) if match else None


def _organisational_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    labels = domain.rstrip(".").lower().split(".")
    if len(labels) <= 2:
        return domain.lower()
    common_second_level = {"co.uk", "com.au", "co.nz", "co.jp", "com.sg", "com.br"}
    suffix2 = ".".join(labels[-2:])
    return ".".join(labels[-3:]) if suffix2 in common_second_level else suffix2


def _aligned(left: str | None, right: str | None) -> bool | None:
    if not left or not right:
        return None
    return _organisational_domain(left) == _organisational_domain(right)


def _ip_classification(value: str) -> dict[str, Any]:
    address = ipaddress.ip_address(value)
    is_private = any(address in network for network in PRIVATE_IP_NETWORKS)
    is_documentation = any(address in network for network in DOCUMENTATION_IP_NETWORKS)
    is_reserved = address.is_reserved and not is_documentation
    flags = {
        "is_private": is_private,
        "is_loopback": address.is_loopback,
        "is_link_local": address.is_link_local,
        "is_reserved": is_reserved,
        "is_multicast": address.is_multicast,
        "is_unspecified": address.is_unspecified,
        "is_global": address.is_global and not is_documentation,
        "is_documentation": is_documentation,
    }
    classification = next(
        (
            label
            for label, matched in (
                ("unspecified", flags["is_unspecified"]),
                ("loopback", flags["is_loopback"]),
                ("link_local", flags["is_link_local"]),
                ("multicast", flags["is_multicast"]),
                ("documentation", flags["is_documentation"]),
                ("private", flags["is_private"]),
                ("reserved", flags["is_reserved"]),
                ("global", flags["is_global"]),
            )
            if matched
        ),
        "non_global",
    )
    return {"ip": str(address), "classification": classification, **flags}


def _url_host(value: str) -> str | None:
    try:
        return _normalise_domain(urlsplit(value).hostname)
    except ValueError:
        return None


def _display_destination(value: str) -> str | None:
    candidate = value.strip().strip("<>[](){}.,;:\"'")
    if not candidate:
        return None
    if re.match(r"https?://", candidate, re.I):
        return _url_host(candidate)
    return _normalise_domain(candidate) if DOMAIN_RE.fullmatch(candidate) else None


def _auth_analysis(headers: list[dict[str, Any]], parsed: dict[str, Any]) -> dict[str, Any]:
    auth_headers = _values(headers, "Authentication-Results")
    received_spf = _values(headers, "Received-SPF")
    dkim_headers = _values(headers, "DKIM-Signature")
    arc_auth = _values(headers, "ARC-Authentication-Results")
    arc_seals = _values(headers, "ARC-Seal")
    arc_messages = _values(headers, "ARC-Message-Signature")

    methods: list[dict[str, Any]] = []
    servers: list[str] = []
    for header_index, value in enumerate(auth_headers):
        parts = [part.strip() for part in value.split(";")]
        if parts and parts[0]:
            servers.append(parts[0].split()[0])
        for part in parts[1:]:
            method_match = re.match(
                r"(?P<method>spf|dkim|dmarc|arc)\s*=\s*(?P<result>[A-Za-z]+)", part, re.I
            )
            if not method_match:
                continue
            method = method_match.group("method").lower()
            raw_result = method_match.group("result").lower()
            result = raw_result if raw_result in AUTH_RESULTS else "unknown"
            props = {
                key.lower(): val.strip(" <>\"')(")
                for key, val in re.findall(r"([A-Za-z][\w.-]*)\s*=\s*([^\s;]+)", part)
            }
            methods.append(
                {
                    "method": method,
                    "result": result,
                    "raw_result": raw_result,
                    "properties": props,
                    "header_index": header_index,
                    "raw": part,
                    "source": "Authentication-Results",
                }
            )

    if not any(item["method"] == "spf" for item in methods):
        for value in received_spf:
            match = re.match(r"\s*([A-Za-z]+)", value)
            raw_result = match.group(1).lower() if match else "unknown"
            methods.append(
                {
                    "method": "spf",
                    "result": raw_result if raw_result in AUTH_RESULTS else "unknown",
                    "raw_result": raw_result,
                    "properties": {
                        key.lower(): val.strip(" <>;")
                        for key, val in re.findall(r"([A-Za-z][\w.-]*)=([^\s;]+)", value)
                    },
                    "header_index": None,
                    "raw": value,
                    "source": "Received-SPF",
                }
            )

    dkim_signatures: list[dict[str, Any]] = []
    for value in dkim_headers:
        tags = {
            key.lower(): val.strip()
            for key, val in re.findall(r"(?:^|;)\s*([A-Za-z][A-Za-z0-9]*)\s*=\s*([^;]+)", value)
        }
        dkim_signatures.append(
            {
                "domain": _normalise_domain(tags.get("d")),
                "selector": tags.get("s"),
                "algorithm": tags.get("a"),
                "identity": tags.get("i"),
                "raw": value,
            }
        )

    arc_methods: list[dict[str, Any]] = []
    for header_index, value in enumerate(arc_auth):
        for part in (item.strip() for item in value.split(";")):
            method_match = re.match(
                r"(?P<method>spf|dkim|dmarc|arc)\s*=\s*(?P<result>[A-Za-z]+)", part, re.I
            )
            if not method_match:
                continue
            raw_result = method_match.group("result").lower()
            arc_methods.append(
                {
                    "method": method_match.group("method").lower(),
                    "result": raw_result if raw_result in AUTH_RESULTS else "unknown",
                    "raw_result": raw_result,
                    "properties": {
                        key.lower(): val.strip(" <>\"')(")
                        for key, val in re.findall(r"([A-Za-z][\w.-]*)\s*=\s*([^\s;]+)", part)
                    },
                    "header_index": header_index,
                    "raw": part,
                    "source": "ARC-Authentication-Results",
                }
            )

    def last_method(name: str) -> dict[str, Any] | None:
        candidates = [item for item in methods if item["method"] == name]
        return candidates[-1] if candidates else None

    spf = last_method("spf")
    dkim = last_method("dkim")
    dmarc = last_method("dmarc")
    spf_props = spf.get("properties", {}) if spf else {}
    dkim_props = dkim.get("properties", {}) if dkim else {}
    dmarc_props = dmarc.get("properties", {}) if dmarc else {}
    spf_identity = (
        spf_props.get("smtp.mailfrom")
        or spf_props.get("smtp.helo")
        or spf_props.get("envelope-from")
    )
    spf_domain = _domain_from_identity(spf_identity)
    dkim_domain = _normalise_domain(dkim_props.get("header.d"))
    dkim_domain_source = "Authentication-Results"
    if not dkim_domain and dkim_signatures:
        dkim_domain = dkim_signatures[0]["domain"]
        dkim_domain_source = "DKIM-Signature"
    from_domain = parsed.get("from", [{}])[0].get("domain") if parsed.get("from") else None
    return_path_domain = (
        parsed.get("return_path", [{}])[0].get("domain") if parsed.get("return_path") else None
    )
    reply_domain = parsed.get("reply_to", [{}])[0].get("domain") if parsed.get("reply_to") else None
    sender_domain = parsed.get("sender", [{}])[0].get("domain") if parsed.get("sender") else None
    message_id_domain = _domain_from_identity(parsed.get("message_id"))

    return {
        "source_notice": "Results are recorded message evidence, not fresh cryptographic verification.",
        "authentication_servers": servers,
        "methods": methods,
        "spf": {
            "result": spf["result"] if spf else "none",
            "domain": spf_domain,
            "identity": spf_identity,
            "raw": spf.get("raw") if spf else None,
            "source": spf.get("source") if spf else None,
        },
        "dkim": {
            "result": dkim["result"] if dkim else "none",
            "domain": dkim_domain,
            "selector": dkim_signatures[0].get("selector") if dkim_signatures else None,
            "raw": dkim.get("raw") if dkim else None,
            "signatures": dkim_signatures,
            "domain_source": dkim_domain_source if dkim_domain else None,
        },
        "dmarc": {
            "result": dmarc["result"] if dmarc else "none",
            "domain": _normalise_domain(dmarc_props.get("header.from")) or from_domain,
            "policy": dmarc_props.get("policy.dmarc") or dmarc_props.get("p"),
            "raw": dmarc.get("raw") if dmarc else None,
            "source": dmarc.get("source") if dmarc else None,
        },
        "arc": {
            "authentication_results": arc_auth,
            "methods": arc_methods,
            "seals": arc_seals,
            "message_signatures": arc_messages,
            "chain_instances": sorted(
                {
                    int(v)
                    for value in arc_seals
                    for v in re.findall(r"(?:^|;)\s*i\s*=\s*(\d+)", value)
                }
            ),
        },
        "alignment": {
            "header_from_domain": from_domain,
            "spf_domain": spf_domain,
            "spf_aligned": _aligned(from_domain, spf_domain),
            "dkim_domain": dkim_domain,
            "dkim_aligned": _aligned(from_domain, dkim_domain),
            "return_path_domain": return_path_domain,
            "return_path_aligned": _aligned(from_domain, return_path_domain),
            "reply_to_domain": reply_domain,
            "reply_to_aligned": _aligned(from_domain, reply_domain),
            "sender_domain": sender_domain,
            "sender_aligned": _aligned(from_domain, sender_domain),
            "message_id_domain": message_id_domain,
            "message_id_aligned": _aligned(from_domain, message_id_domain),
        },
    }


def _parse_received(value: str, index: int) -> dict[str, Any]:
    before, separator, date_text = value.rpartition(";")
    transport = before if separator else value
    parsed_time: datetime | None = None
    warning_list: list[str] = []
    if separator and date_text.strip():
        try:
            parsed_time = parsedate_to_datetime(date_text.strip())
            if parsed_time.tzinfo is None:
                warning_list.append("Timestamp has no timezone")
                parsed_time = parsed_time.replace(tzinfo=UTC)
        except (TypeError, ValueError, OverflowError):
            warning_list.append("Timestamp could not be parsed")
    else:
        warning_list.append("No timestamp separator found")

    def token_after(keyword: str) -> str | None:
        match = re.search(rf"\b{keyword}\s+([^\s(;]+)", transport, re.I)
        return match.group(1).strip("[]") if match else None

    from_match = re.search(r"\bfrom\s+", transport, re.I)
    from_clause = from_match and transport[from_match.end() :]
    if from_clause:
        boundary = re.search(r"\s+\b(?:by|via|with|id|for)\b\s+", from_clause, re.I)
        if boundary:
            from_clause = from_clause[: boundary.start()]

    ips: list[str] = []
    for candidate in IP_RE.findall(from_clause or ""):
        try:
            ips.append(str(ipaddress.ip_address(candidate)))
        except ValueError:
            continue
    from_host = token_after("from")
    by_host = token_after("by")
    if not from_host or not by_host:
        warning_list.append("Hop is missing from or by host information")
    protocol = token_after("with")
    queue_id = token_after("id")
    source_ip = ips[0] if ips else None
    classification = _ip_classification(source_ip) if source_ip else None
    return {
        "sequence": index,
        "from_host": from_host,
        "from_ip": source_ip,
        "by_host": by_host,
        "transport": protocol,
        "protocol": protocol,
        "queue_id": queue_id,
        "timestamp": date_text.strip() if separator else None,
        "timezone": parsed_time.strftime("%z") if parsed_time else None,
        "utc_time": parsed_time.astimezone(UTC).isoformat() if parsed_time else None,
        "raw": value,
        "confidence": "high"
        if from_host and by_host and parsed_time
        else "medium"
        if from_host or by_host
        else "low",
        "warnings": warning_list,
        # Compatibility field retained with strict RFC1918/ULA semantics.
        "is_private_ip": classification["is_private"] if classification else None,
        "ip_classification": classification,
    }


def _hops(headers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    received = _values(headers, "Received")
    hops = [_parse_received(value, index) for index, value in enumerate(reversed(received), 1)]
    previous: datetime | None = None
    for hop in hops:
        current = datetime.fromisoformat(hop["utc_time"]) if hop["utc_time"] else None
        hop["delay_from_previous_seconds"] = None
        if current and previous:
            delay = (current - previous).total_seconds()
            hop["delay_from_previous_seconds"] = delay
            if delay < -60:
                hop["warnings"].append("Timestamp occurs before the preceding hop")
            elif delay > 4 * 60 * 60:
                hop["warnings"].append("Delivery gap exceeds four hours")
        if current:
            previous = current
    return hops


def _mime_depth(part: Message, depth: int = 0) -> int:
    if not part.is_multipart():
        return depth
    children = list(part.iter_parts()) if hasattr(part, "iter_parts") else []
    return max((_mime_depth(child, depth + 1) for child in children), default=depth)


def _attachment_metadata(message: Message, settings: Settings) -> list[dict[str, Any]]:
    if _mime_depth(message) > settings.max_mime_depth:
        raise ParseLimitError(f"MIME nesting exceeds {settings.max_mime_depth}")
    attachments: list[dict[str, Any]] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        disposition = part.get_content_disposition()
        if filename is None and disposition != "attachment":
            continue
        payload = part.get_payload(decode=True) or b""
        decoded_filename = _decode(filename) if filename else None
        safe_name = safe_filename(decoded_filename or "unnamed-attachment", "unnamed-attachment")
        content_id = part.get("Content-ID")
        attachments.append(
            {
                "filename": safe_name,
                "declared_filename": decoded_filename,
                "content_type": part.get_content_type(),
                "content_disposition": disposition,
                "content_id": _decode(content_id).strip("<>") if content_id else None,
                "extension": PurePath(safe_name).suffix.lower().lstrip(".") or None,
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),  # type: ignore[arg-type]
                "executed": False,
                "stored": False,
            }
        )
        if len(attachments) > settings.max_attachments:
            raise ParseLimitError(f"Attachment count exceeds {settings.max_attachments}")
    return attachments


def _mime_and_urls(
    message: Message, input_type: str, settings: Settings
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if input_type != "eml":
        return (
            {
                "available": False,
                "reason": "MIME/body evidence unavailable because only headers were supplied.",
            },
            [],
        )
    part_count = 0
    decoded_total = 0
    plain_preview = ""
    plain_present = False
    html_present = False
    encodings: set[str] = set()
    charsets: set[str] = set()
    urls: dict[str, dict[str, Any]] = {}

    def add_url(
        value: str,
        content_type: str,
        part_path: str,
        *,
        displayed_text: str | None = None,
        actual_href: str | None = None,
    ) -> None:
        if not re.match(r"^https?://", value, re.I):
            return
        if value not in urls and len(urls) >= settings.max_urls:
            raise ParseLimitError(f"URL count exceeds {settings.max_urls}")
        host = _url_host(value)
        displayed_destination = _display_destination(displayed_text or "")
        item = {
            "url": value,
            "scheme": value.split(":", 1)[0].lower(),
            "source": content_type,
            "source_mime_part": part_path,
            "displayed_text": displayed_text,
            "displayed_destination": displayed_destination,
            "actual_href": actual_href,
            "host": host,
            "domain": host,
            "display_href_mismatch": bool(
                displayed_destination and host and displayed_destination != host
            ),
            "fetched": False,
        }
        if value in urls:
            for key, field_value in item.items():
                if field_value not in {None, "", False}:
                    urls[value][key] = field_value
        else:
            urls[value] = item

    def visit(part: Message, depth: int, part_path: str) -> dict[str, Any]:
        nonlocal part_count, decoded_total, plain_preview, plain_present, html_present
        part_count += 1
        if part_count > settings.max_mime_parts:
            raise ParseLimitError(f"MIME part count exceeds {settings.max_mime_parts}")
        if depth > settings.max_mime_depth:
            raise ParseLimitError(f"MIME nesting depth exceeds {settings.max_mime_depth}")
        content_type = part.get_content_type()
        charset = part.get_content_charset()
        transfer = part.get("Content-Transfer-Encoding")
        if charset:
            charsets.add(charset.lower())
        if transfer:
            encodings.add(transfer.lower())
        node: dict[str, Any] = {
            "content_type": content_type,
            "disposition": part.get_content_disposition(),
            "filename": safe_filename(part.get_filename() or "", "") or None,
            "charset": charset,
            "transfer_encoding": transfer,
            "children": [],
        }
        if part.is_multipart():
            payload = part.get_payload()
            children = payload if isinstance(payload, list) else []
            node["children"] = [
                visit(child, depth + 1, f"{part_path}.{child_index}")
                for child_index, child in enumerate(children, 1)
            ]
            return node
        raw_payload = part.get_payload(decode=True)
        payload_bytes = raw_payload if isinstance(raw_payload, bytes) else b""
        if len(payload_bytes) > settings.max_part_bytes:
            raise ParseLimitError(f"A decoded MIME part exceeds {settings.max_part_bytes} bytes")
        decoded_total += len(payload_bytes)
        if decoded_total > settings.max_decoded_bytes:
            raise ParseLimitError(
                f"Decoded MIME content exceeds {settings.max_decoded_bytes} bytes"
            )
        node["decoded_size"] = len(payload_bytes)
        node["sha256"] = hashlib.sha256(payload_bytes).hexdigest()
        if content_type in {"text/plain", "text/html"} and payload_bytes:
            try:
                text = payload_bytes.decode(charset or "utf-8", errors="replace")
            except LookupError:
                text = payload_bytes.decode("utf-8", errors="replace")
            if content_type == "text/plain" and not plain_preview:
                plain_preview = text[:4000]
            if content_type == "text/plain":
                plain_present = True
            if content_type == "text/html":
                html_present = True
                if not plain_preview:
                    plain_preview = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))[:4000]
                link_parser = _HTMLLinkParser()
                try:
                    link_parser.feed(text)
                    link_parser.close()
                except (AssertionError, ValueError):
                    link_parser.links = []
                for link in link_parser.links:
                    href = link["href"].rstrip(".,;:")
                    add_url(
                        href,
                        content_type,
                        part_path,
                        displayed_text=link["text"] or None,
                        actual_href=href,
                    )
            for match in URL_RE.finditer(text):
                value = match.group(0).rstrip(".,;:")
                add_url(value, content_type, part_path)
        return node

    root = visit(message, 0, "1")
    return (
        {
            "available": True,
            "root": root,
            "part_count": part_count,
            "max_depth": _mime_depth(message),
            "decoded_bytes": decoded_total,
            "plain_text_preview": plain_preview,
            "text_plain_available": plain_present,
            "html_available": html_present,
            "html_rendered": False,
            "remote_resources_loaded": False,
            "charsets": sorted(charsets),
            "transfer_encodings": sorted(encodings),
        },
        list(urls.values()),
    )


def _assessment(
    observations: list[dict[str, Any]], warnings: list[dict[str, Any]], auth: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    for item in observations:
        item.setdefault("explanation", item.get("description", ""))
        item.setdefault("evidence_reference", item.get("supporting_headers", []))
        item.setdefault("why_it_matters", item.get("why_matters", ""))
        item.setdefault(
            "analyst_action", item.get("recommended_action", "Review the raw evidence.")
        )
    high = [item for item in observations if item.get("severity") == "high"]
    medium = [item for item in observations if item.get("severity") == "medium"]
    if warnings and not observations:
        label, risk = "Parsing incomplete", "unknown"
    elif not auth.get("methods") and len(observations) <= 1:
        label, risk = "Insufficient evidence", "unknown"
    elif any(item.get("confidence") in {"high", "medium"} for item in high):
        label, risk = "Concerning evidence found", "high"
    elif medium or high:
        label, risk = "Some evidence needs review", "medium"
    else:
        label, risk = "No clear concern found", "low"
    direct = sum(
        item.get("evidence_level") in {"Direct header fact", "Recorded authentication result"}
        for item in observations
    )
    confidence = "low" if warnings else "high" if direct or not observations else "medium"
    basis = [
        f"{len(observations)} distinct observation(s) were evaluated.",
        "Risk describes seriousness; confidence describes strength and completeness of evidence.",
    ]
    limitations = [
        "Authentication results are claims recorded in the message; MailTrace did not independently verify SPF, DKIM, DMARC, or ARC.",
        "Headers added before a trusted receiving system may have been altered or forged.",
        "URLs and attachments were inspected as data and were not opened, executed, or fetched.",
    ]
    if warnings:
        limitations.append("Parser warnings reduce confidence; review the preserved raw evidence.")
    return (
        {
            "label": label,
            "risk": risk,
            "confidence": confidence,
            "basis": basis,
            "observation_count": len(observations),
        },
        limitations,
    )


def _entities(
    parsed: dict[str, Any],
    headers: list[dict[str, Any]],
    hops: list[dict[str, Any]],
    auth: dict[str, Any],
) -> list[dict[str, Any]]:
    found: dict[tuple[str, str], set[str]] = {}

    def add(kind: str, value: str | None, source: str) -> None:
        if not value:
            return
        found.setdefault((kind, value), set()).add(source)

    for field in ("from", "sender", "reply_to", "return_path", "to", "cc"):
        for address in parsed.get(field, []):
            add("email_address", address.get("address"), field)
            add("domain", address.get("domain"), field)
    add("message_identifier", parsed.get("message_id"), "message-id")
    add("domain", _domain_from_identity(parsed.get("message_id")), "message-id")

    def add_auth_entities(method: dict[str, Any]) -> None:
        source_header = str(method.get("source") or "authentication-results").lower()
        for property_name, raw_value in method.get("properties", {}).items():
            value = str(raw_value).strip()
            source = f"{source_header}:{property_name}"
            if property_name in {"smtp.mailfrom", "envelope-from"}:
                match = EMAIL_RE.fullmatch(value)
                if match:
                    add("email_address", value, source)
                    add("domain", _normalise_domain(match.group(2)), source)
                else:
                    add("domain", _domain_from_identity(value), source)
            elif property_name == "smtp.helo":
                try:
                    add("ip_address", str(ipaddress.ip_address(value.strip("[]"))), source)
                except ValueError:
                    add("domain", _normalise_domain(value), source)
            elif property_name in {"header.from", "header.d"}:
                add("domain", _normalise_domain(value), source)

    for method in auth.get("methods", []):
        add_auth_entities(method)
    for method in auth.get("arc", {}).get("methods", []):
        add_auth_entities(method)
    for signature in auth.get("dkim", {}).get("signatures", []):
        add("domain", signature.get("domain"), "dkim-signature:d")

    for header in headers:
        if header["name_lower"] in STRUCTURED_ENTITY_HEADERS:
            continue
        value = str(header["decoded_value"])
        for local, domain in EMAIL_RE.findall(value):
            add("email_address", f"{local}@{domain}", header["name_lower"])
            add("domain", _normalise_domain(domain), header["name_lower"])
        for domain in DOMAIN_RE.findall(value):
            add("domain", _normalise_domain(domain), header["name_lower"])
        for candidate in IP_RE.findall(value):
            try:
                add("ip_address", str(ipaddress.ip_address(candidate)), header["name_lower"])
            except ValueError:
                continue
    for hop in hops:
        add("mail_server", hop.get("from_host"), "received")
        add("mail_server", hop.get("by_host"), "received")
        add("ip_address", hop.get("from_ip"), "received")
    return [
        {"type": kind, "value": value, "sources": sorted(sources)}
        for (kind, value), sources in sorted(found.items())
    ]


def _script_groups(value: str) -> set[str]:
    groups: set[str] = set()
    for char in value:
        if not char.isalpha():
            continue
        name = unicodedata.name(char, "")
        for group in ("LATIN", "CYRILLIC", "GREEK", "HEBREW", "ARABIC"):
            if group in name:
                groups.add(group)
                break
    return groups


def _observations(
    parsed: dict[str, Any],
    auth: dict[str, Any],
    hops: list[dict[str, Any]],
    headers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []

    def add(
        rule_id: str,
        title: str,
        category: str,
        severity: Literal["info", "low", "medium", "high"],
        confidence: Literal["low", "medium", "high"],
        evidence_level: str,
        description: str,
        supporting: list[str],
        explanation: str,
        benign: str,
        action: str,
    ) -> None:
        evidence_headers = list(dict.fromkeys(item for item in supporting if item))
        if evidence_level == "Recorded authentication result":
            limitation = (
                "The result was recorded by a receiver; MailTrace did not replay historical "
                "authentication."
            )
        elif evidence_level == "Derived alignment observation":
            limitation = (
                "Alignment uses parsed domains and an offline organisational-domain approximation."
            )
        elif evidence_level == "Heuristic review signal":
            limitation = "This review signal does not establish sender intent or maliciousness."
        else:
            limitation = "Header facts can be forged outside a trusted receiving boundary."
        observations.append(
            {
                "rule_id": rule_id,
                "title": title,
                "category": category,
                "severity": severity,
                "confidence": confidence,
                "evidence_level": evidence_level,
                "description": description,
                "supporting_headers": evidence_headers,
                "evidence_reference": evidence_headers,
                "explanation": explanation,
                "benign_alternatives": benign,
                "limitation": limitation,
                "recommended_action": action,
            }
        )

    def present_headers(*names: str) -> list[str]:
        return [name for name in names if _values(headers, name)]

    def domain_headers(domain: str) -> list[str]:
        names: list[str] = []
        fields = {
            "From": parsed.get("from", []),
            "Reply-To": parsed.get("reply_to", []),
            "Return-Path": parsed.get("return_path", []),
            "Sender": parsed.get("sender", []),
            "To": parsed.get("to", []),
            "Cc": parsed.get("cc", []),
        }
        for name, addresses in fields.items():
            if any(item.get("domain") == domain for item in addresses):
                names.append(name)
        if _domain_from_identity(parsed.get("message_id")) == domain:
            names.append("Message-ID")
        if any(
            domain
            in {
                auth.get(method, {}).get("domain"),
                auth.get("alignment", {}).get(f"{method}_domain"),
            }
            for method in ("spf", "dkim", "dmarc")
        ):
            names.extend(
                present_headers("Authentication-Results", "Received-SPF", "DKIM-Signature")
            )
        if any(domain in {hop.get("from_host"), hop.get("by_host")} for hop in hops):
            names.append("Received")
        return list(dict.fromkeys(names)) or ["Parsed entity provenance"]

    alignment = auth["alignment"]
    checks = [
        (
            "reply_to_aligned",
            "ID-001",
            "From and Reply-To domains differ",
            "Reply-To may intentionally direct responses through a ticketing, campaign, or delegated service.",
            ["From", "Reply-To"],
        ),
        (
            "return_path_aligned",
            "ID-002",
            "From and Return-Path domains differ",
            "Legitimate senders frequently use a third-party bounce-handling service.",
            ["From", "Return-Path"],
        ),
        (
            "sender_aligned",
            "ID-003",
            "Sender and From domains differ",
            "The Sender field can legitimately identify an agent sending on behalf of another mailbox.",
            ["From", "Sender"],
        ),
        (
            "message_id_aligned",
            "ID-004",
            "Message-ID and From domains differ",
            "Mail platforms often generate Message-IDs under infrastructure domains.",
            ["From", "Message-ID"],
        ),
    ]
    for key, rule, title, benign, supporting in checks:
        if alignment.get(key) is False:
            add(
                rule,
                title,
                "sender_identity",
                "medium" if key == "reply_to_aligned" else "low",
                "high",
                "Derived alignment observation",
                title,
                supporting,
                "Organisational domains were compared using a documented offline approximation.",
                benign,
                "Confirm the alternate domain's relationship to the claimed sender.",
            )

    from_addresses = parsed.get("from", [])
    if not from_addresses or not from_addresses[0].get("address"):
        add(
            "ID-005",
            "Sender is missing or malformed",
            "sender_identity",
            "medium",
            "high",
            "Direct header fact",
            "No usable From mailbox was parsed.",
            ["From"],
            "A usable sender identity is normally expected.",
            "Some automated or malformed legacy messages omit it.",
            "Inspect the raw From header and source system.",
        )
    if len(_values(headers, "From")) > 1:
        add(
            "ID-006",
            "Multiple From headers",
            "sender_identity",
            "high",
            "high",
            "Direct header fact",
            "More than one From header is present.",
            ["From"],
            "Multiple singleton identity headers create ambiguity.",
            "Malformed gateways can accidentally duplicate fields.",
            "Inspect the raw header order and acquisition source.",
        )

    for name in ("spf", "dkim", "dmarc"):
        result = auth[name]["result"]
        if result in {"fail", "softfail", "permerror", "temperror", "policy"}:
            severity: Literal["low", "medium", "high"] = (
                "high" if name == "dmarc" and result == "fail" else "medium"
            )
            add(
                f"AUTH-{name.upper()}-{result.upper()}",
                f"Recorded {name.upper()} result: {result}",
                "authentication",
                severity,
                "high",
                "Recorded authentication result",
                f"The receiving system recorded {name.upper()}={result}.",
                [str(auth[name].get("source") or "Authentication-Results")],
                "This reports evidence written into the message; MailTrace did not re-run historical authentication.",
                "Forwarding, DNS outages, mailing lists, or receiver policy can affect authentication.",
                "Validate the trusted header boundary and correlate with the other authentication methods.",
            )
    if not auth["methods"]:
        add(
            "AUTH-001",
            "Authentication results are absent",
            "authentication",
            "low",
            "high",
            "Direct header fact",
            "No parseable Authentication-Results or Received-SPF evidence was found.",
            ["Authentication-Results", "Received-SPF"],
            "The message lacks receiver-recorded authentication evidence.",
            "Internal mail or exported messages may omit these headers.",
            "Obtain the message from the original mailbox or mail gateway if possible.",
        )
    for method, key in (("SPF", "spf_aligned"), ("DKIM", "dkim_aligned")):
        if alignment.get(key) is False:
            if method == "SPF":
                method_headers = [str(auth["spf"].get("source") or "Authentication-Results")]
            else:
                method_headers = [
                    str(auth["dkim"].get("domain_source") or "Authentication-Results")
                ]
            add(
                f"AUTH-{method}-ALIGN",
                f"{method} domain does not align with Header From",
                "authentication",
                "medium",
                "high",
                "Derived alignment observation",
                f"The recorded {method} identity uses a different organisational domain.",
                [*method_headers, "From"],
                "Alignment is distinct from the underlying authentication result.",
                "Delegated infrastructure can authenticate successfully without strict alignment.",
                "Check DMARC handling and the sending service relationship.",
            )

    method_results: dict[str, set[str]] = {}
    for item in auth["methods"]:
        method_results.setdefault(item["method"], set()).add(item["result"])
    conflicts = [method for method, values in method_results.items() if len(values) > 1]
    if conflicts:
        add(
            "AUTH-002",
            "Conflicting authentication result headers",
            "authentication",
            "medium",
            "high",
            "Recorded authentication result",
            f"Different results were recorded for: {', '.join(conflicts)}.",
            ["Authentication-Results"],
            "Multiple receivers or trust boundaries may add results at different stages.",
            "Forwarding and nested gateway processing commonly create multiple results.",
            "Identify which Authentication-Results header was added by the trusted final receiver.",
        )
    if auth["arc"]["seals"] and any(
        "cv=fail" in seal.replace(" ", "").lower() for seal in auth["arc"]["seals"]
    ):
        add(
            "AUTH-ARC-FAIL",
            "ARC chain records a failure",
            "authentication",
            "medium",
            "medium",
            "Recorded authentication result",
            "An ARC-Seal contains cv=fail.",
            ["ARC-Seal"],
            "ARC can preserve authentication context through intermediaries, but MailTrace does not cryptographically validate the chain.",
            "Broken or partially implemented ARC chains occur on legitimate forwarded mail.",
            "Have a capable mail system validate the ARC chain cryptographically.",
        )

    all_domains = [
        item["value"] for item in _entities(parsed, headers, hops, auth) if item["type"] == "domain"
    ]
    for domain in all_domains:
        if domain.startswith("xn--") or ".xn--" in domain:
            add(
                "DOM-001",
                "Punycode domain requires review",
                "domain_address",
                "medium",
                "high",
                "Direct header fact",
                f"The domain {domain} contains an IDNA punycode label.",
                domain_headers(domain),
                "Punycode is valid but can encode visually confusable internationalised names.",
                "Many organisations legitimately use internationalised domains.",
                "Decode and compare the domain visually in a safe offline tool.",
            )
        try:
            unicode_domain = domain.encode("ascii").decode("idna")
        except (UnicodeError, UnicodeEncodeError):
            unicode_domain = domain
        if len(_script_groups(unicode_domain)) > 1:
            add(
                "DOM-002",
                "Mixed-script domain requires review",
                "domain_address",
                "medium",
                "medium",
                "Heuristic review signal",
                f"The Unicode form of {domain} mixes writing systems.",
                domain_headers(domain),
                "Mixed scripts may create visually confusable domains.",
                "Some legitimate internationalised names mix scripts.",
                "Compare the exact code points with the expected domain.",
            )
        labels = domain.split(".")
        if len(labels) > 5:
            add(
                "DOM-003",
                "Deeply nested domain",
                "domain_address",
                "low",
                "high",
                "Heuristic review signal",
                f"The domain {domain} has {len(labels)} labels.",
                domain_headers(domain),
                "Long subdomain chains can obscure the registrable domain.",
                "Cloud services often use deep hostnames.",
                "Read the domain from right to left and identify its registrable portion.",
            )

    if from_addresses and from_addresses[0].get("domain", "").startswith("["):
        add(
            "DOM-004",
            "IP-literal sender domain",
            "domain_address",
            "medium",
            "high",
            "Direct header fact",
            "The visible sender uses an IP-literal domain.",
            ["From"],
            "IP literals are unusual for person-to-person email addresses.",
            "Testing and closed systems may use them.",
            "Confirm the sender system and expected addressing convention.",
        )
    reply_domain = alignment.get("reply_to_domain")
    from_domain = alignment.get("header_from_domain")
    if reply_domain in FREE_MAIL and from_domain and from_domain not in FREE_MAIL:
        add(
            "DOM-005",
            "Free-mail Reply-To with organisational From",
            "domain_address",
            "medium",
            "high",
            "Derived alignment observation",
            f"Replies are directed to {reply_domain} rather than {from_domain}.",
            ["From", "Reply-To"],
            "This pattern can redirect conversation away from an organisation-controlled mailbox.",
            "Small organisations and contractors sometimes use free-mail accounts.",
            "Verify the Reply-To using an independently known contact channel.",
        )

    for hop in hops:
        for warning in hop["warnings"]:
            if "before" in warning:
                add(
                    "HOP-001",
                    "Delivery timestamp reversal",
                    "delivery_path",
                    "medium",
                    "high",
                    "Derived alignment observation",
                    f"Hop {hop['sequence']} predates the previous parsed hop.",
                    ["Received"],
                    "Received headers are expected to progress forward in time when read from earliest to latest.",
                    "Clock skew, bad timezone data, and header reordering can cause benign reversals.",
                    "Compare raw timestamps, timezones, and server clock sources.",
                )
            elif "four hours" in warning:
                add(
                    "HOP-002",
                    "Long delivery delay",
                    "delivery_path",
                    "low",
                    "high",
                    "Heuristic review signal",
                    f"Hop {hop['sequence']} follows a gap longer than four hours.",
                    ["Received"],
                    "A long gap may indicate queueing or interrupted delivery.",
                    "Greylisting, outages, and recipient throttling commonly delay legitimate mail.",
                    "Inspect queue identifiers and adjacent mail-server logs.",
                )
        if hop["confidence"] == "low":
            add(
                "HOP-003",
                "Malformed Received hop",
                "delivery_path",
                "low",
                "high",
                "Direct header fact",
                f"Hop {hop['sequence']} could not be structured reliably.",
                ["Received"],
                "Missing from/by information limits route reconstruction.",
                "Non-standard MTAs emit unusual but legitimate Received formats.",
                "Read the raw hop and compare with the emitting MTA format.",
            )
    origin_headers = [
        name
        for name in ("X-Originating-IP", "X-Client-IP", "X-Forwarded-For")
        if _values(headers, name)
    ]
    if origin_headers:
        add(
            "HOP-004",
            "Client-supplied origin header present",
            "delivery_path",
            "info",
            "high",
            "Direct header fact",
            f"Origin-style headers are present: {', '.join(origin_headers)}.",
            origin_headers,
            "These headers may be inserted before the trusted mail boundary and are not inherently authoritative.",
            "Trusted webmail and gateways also add them.",
            "Corroborate origin values with trusted Received hops.",
        )
    origin_values = {
        ip
        for name in origin_headers
        for value in _values(headers, name)
        for ip in IP_RE.findall(value)
    }
    if len(origin_values) > 1:
        add(
            "HOP-005",
            "Conflicting originating IP headers",
            "delivery_path",
            "medium",
            "high",
            "Direct header fact",
            "Origin-style headers contain different IP addresses.",
            origin_headers,
            "Conflicting values weaken attribution.",
            "Multiple proxies or forwarding layers can add different addresses.",
            "Use only headers added inside the trusted mail infrastructure.",
        )

    if not parsed.get("message_id"):
        add(
            "META-001",
            "Message-ID is missing",
            "content_metadata",
            "low",
            "high",
            "Direct header fact",
            "No Message-ID header was found.",
            ["Message-ID"],
            "Most production mail systems generate a Message-ID.",
            "Some automated, draft, or malformed messages omit it.",
            "Check acquisition completeness and source application.",
        )
    if len(_values(headers, "Message-ID")) > 1:
        add(
            "META-002",
            "Duplicate Message-ID headers",
            "content_metadata",
            "medium",
            "high",
            "Direct header fact",
            "Multiple Message-ID headers are present.",
            ["Message-ID"],
            "Message-ID is normally a singleton field.",
            "Gateways may preserve an old identifier incorrectly.",
            "Compare identifiers and raw header order.",
        )
    if any(
        _values(headers, name)
        for name in ("List-Id", "List-Unsubscribe", "List-Post", "Precedence")
    ):
        add(
            "META-003",
            "Bulk or mailing-list indicators",
            "content_metadata",
            "info",
            "high",
            "Direct header fact",
            "List or precedence metadata indicates automated distribution.",
            present_headers("List-Id", "List-Unsubscribe", "List-Post", "Precedence"),
            "Mailing-list processing can legitimately rewrite sender and authentication data.",
            "This is informational, not a negative verdict.",
            "Interpret authentication in the context of list forwarding.",
        )
    if any(_values(headers, name) for name in ("Auto-Submitted", "X-Auto-Response-Suppress")):
        add(
            "META-004",
            "Automated-message indicators",
            "content_metadata",
            "info",
            "high",
            "Direct header fact",
            "Automation-specific headers are present.",
            present_headers("Auto-Submitted", "X-Auto-Response-Suppress"),
            "The message declares automated generation or response suppression.",
            "Legitimate notifications commonly use these fields.",
            "Confirm the automation is expected for the claimed sender.",
        )
    mailer = (parsed.get("user_agent") or "").lower()
    if any(
        token in mailer for token in ("bulk mailer", "mass mail", "email extractor", "smtp cracker")
    ):
        add(
            "META-005",
            "Mailer identifier requires review",
            "content_metadata",
            "medium",
            "medium",
            "Heuristic review signal",
            f"The mailer identifies itself as {parsed.get('user_agent')}.",
            present_headers("User-Agent", "X-Mailer"),
            "The declared software name is associated with bulk or questionable sending.",
            "Header values are self-declared and can be spoofed or used legitimately.",
            "Correlate the identifier with volume and sending infrastructure.",
        )

    display = from_addresses[0].get("display_name", "") if from_addresses else ""
    if (
        re.search(r"(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}", display)
        and from_domain
        and from_domain not in display.lower()
    ):
        add(
            "ID-007",
            "Display name resembles a different domain",
            "sender_identity",
            "medium",
            "medium",
            "Heuristic review signal",
            "The display name contains domain-like text that differs from the mailbox domain.",
            ["From"],
            "A domain in the display name can influence how a sender appears in compact mail clients.",
            "Departments or service names may legitimately contain a domain.",
            "Expand and compare the complete mailbox address.",
        )
    return observations


def parse_evidence(data: bytes, input_type: str, settings: Settings) -> dict[str, Any]:
    started = time.perf_counter()
    if not data:
        raise ValueError("Evidence is empty")
    if len(data) > settings.max_upload_bytes:
        raise ParseLimitError(f"Evidence exceeds {settings.max_upload_bytes} bytes")
    if b"\x00" in data:
        raise ParseLimitError("Null bytes are not permitted")

    headers, warnings, _header_blob = _extract_raw_headers(data, settings)
    try:
        message = BytesParser(policy=policy.default).parsebytes(data)  # type: ignore[arg-type]
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Email parser rejected the evidence: {exc}") from exc
    for defect in message.defects:
        warnings.append(
            {"code": defect.__class__.__name__, "message": str(defect) or defect.__class__.__name__}
        )

    parsed: dict[str, Any] = {
        "subject": _first(headers, "Subject"),
        "date": _first(headers, "Date"),
        "from": _address_field(headers, "From"),
        "sender": _address_field(headers, "Sender"),
        "reply_to": _address_field(headers, "Reply-To"),
        "return_path": _address_field(headers, "Return-Path"),
        "message_id": _first(headers, "Message-ID"),
        "to": _address_field(headers, "To"),
        "cc": _address_field(headers, "Cc"),
        "mime_version": _first(headers, "MIME-Version"),
        "content_type": _first(headers, "Content-Type") or message.get_content_type(),
        "user_agent": _first(headers, "User-Agent") or _first(headers, "X-Mailer"),
        "list_headers": {
            name: _values(headers, name)
            for name in ("List-Id", "List-Post", "List-Unsubscribe", "List-Help", "Precedence")
            if _values(headers, name)
        },
        "authentication_headers": {
            name: _values(headers, name)
            for name in (
                "Authentication-Results",
                "Received-SPF",
                "DKIM-Signature",
                "ARC-Authentication-Results",
                "ARC-Seal",
                "ARC-Message-Signature",
            )
            if _values(headers, name)
        },
        "received_headers": _values(headers, "Received"),
        "headers": headers,
        "header_counts": dict(Counter(str(item["name_lower"]) for item in headers)),
        "input_type": input_type,
    }
    hops = _hops(headers)
    authentication = _auth_analysis(headers, parsed)
    attachments = _attachment_metadata(message, settings) if input_type == "eml" else []
    mime_structure, urls = _mime_and_urls(message, input_type, settings)
    entities = _entities(parsed, headers, hops, authentication)
    observations = _observations(parsed, authentication, hops, headers)
    assessment, limitations = _assessment(observations, warnings, authentication)
    parsed["review_priority"] = assessment["risk"]
    parsed["review_priority_basis"] = {
        "method": "Deterministic evidence categories; not a maliciousness score."
    }
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    if elapsed_ms > settings.analysis_timeout_seconds * 1000:
        raise ParseLimitError("Analysis exceeded the configured processing deadline")
    return {
        "parser_version": PARSER_VERSION,
        "warnings": warnings,
        "parsed_message": parsed,
        "authentication": authentication,
        "hops": hops,
        "entities": entities,
        "observations": observations,
        "attachments": attachments,
        "mime_structure": mime_structure,
        "urls": urls,
        "assessment": assessment,
        "limitations": limitations,
        "timings": {"total_ms": elapsed_ms},
    }
