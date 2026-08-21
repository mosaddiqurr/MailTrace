from __future__ import annotations

import csv
import html
import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from mailtrace.models import Case
from mailtrace.parser import safe_filename


def investigation_dict(case: Case) -> dict[str, Any]:
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "case": {
            "id": case.id,
            "title": case.title,
            "description": case.description,
            "status": case.status,
            "analyst_conclusion": case.conclusion,
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
        },
        "evidence": [
            {
                "id": item.id,
                "filename": item.original_filename,
                "sha256": item.sha256,
                "file_size": item.file_size,
                "input_type": item.input_type,
                "uploaded_at": item.uploaded_at.isoformat(),
                "parser_version": item.parser_version,
                "parse_status": item.parse_status,
                "parse_warnings": item.parse_warnings,
                "parsed_message": item.parsed_message,
                "authentication": item.authentication,
                "delivery_hops": item.hops,
                "entities": item.entities,
                "observations": item.observations,
                "attachments": item.attachments,
                "mime_structure": item.mime_structure,
                "urls": item.urls,
                "assessment": item.assessment,
                "limitations": item.limitations,
                "timings": item.timings,
            }
            for item in case.evidence
        ],
        "analyst_notes": [
            {
                "id": note.id,
                "note": note.note,
                "author_label": note.author_label,
                "timestamp": note.created_at.isoformat(),
            }
            for note in case.notes
        ],
        "audit_history": [
            {
                "action": entry.action,
                "timestamp": entry.created_at.isoformat(),
                "evidence_id": entry.evidence_id,
                "metadata": entry.metadata_json,
            }
            for entry in case.audit_entries
        ],
        "methodology_notice": "MailTrace separates raw facts, receiver-recorded authentication, derived alignment observations, heuristic review signals, and analyst conclusions. It does not assign a maliciousness verdict.",
        "limitations": [
            "Recorded authentication headers are not fresh cryptographic verification.",
            "Header fields can be forged outside a trusted mail-server boundary.",
            "Offline organisational-domain comparison uses a conservative suffix approximation.",
            "Live DNS, when requested separately, cannot reproduce historical DNS state.",
        ],
    }


def json_report(case: Case) -> bytes:
    return json.dumps(investigation_dict(case), ensure_ascii=False, indent=2).encode("utf-8")


def text_report(case: Case) -> bytes:
    data = investigation_dict(case)
    lines = [
        "MAILTRACE FORENSIC REPORT",
        f"Case: {case.title}",
        f"Generated: {data['exported_at']}",
        "",
        data["methodology_notice"],
    ]
    for evidence in data["evidence"]:
        parsed = evidence["parsed_message"]
        assessment = evidence.get("assessment") or {}
        lines.extend(
            [
                "",
                f"Evidence: {evidence['filename']}",
                f"SHA-256: {evidence['sha256']}",
                f"Subject: {parsed.get('subject') or 'Not present'}",
                f"Assessment: {assessment.get('label', 'Insufficient evidence')}",
                f"Confidence: {assessment.get('confidence', 'low')}",
                "Observations:",
            ]
        )
        lines.extend(
            f"- [{item.get('severity', 'info')}] {item.get('title')}: {item.get('description')}"
            for item in evidence["observations"]
        )
        lines.append("Limitations:")
        lines.extend(f"- {item}" for item in evidence.get("limitations", []))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _mime_parts(node: dict[str, Any], path: str = "1") -> list[dict[str, Any]]:
    parts = [
        {
            "path": path,
            "content_type": node.get("content_type"),
            "disposition": node.get("disposition"),
            "filename": node.get("filename"),
            "decoded_size": node.get("decoded_size"),
        }
    ]
    for index, child in enumerate(node.get("children", []), 1):
        parts.extend(_mime_parts(child, f"{path}.{index}"))
    return parts


def _html_message_evidence(evidence: dict[str, Any]) -> str:
    mime = evidence.get("mime_structure") or {}
    if not mime.get("available"):
        return (
            "<h3>MIME, body, attachment and URL evidence</h3>"
            f"<p>{_e(mime.get('reason') or 'MIME/body evidence unavailable because only headers were supplied.')}</p>"
        )

    parts = _mime_parts(mime.get("root") or {})
    part_rows = "".join(
        "<tr>"
        f"<td>{_e(part['path'])}</td><td>{_e(part['content_type'])}</td>"
        f"<td>{_e(part['disposition'] or 'body')}</td><td>{_e(part['filename'])}</td>"
        f"<td>{_e(part['decoded_size'])}</td>"
        "</tr>"
        for part in parts
    )
    attachment_rows = (
        "".join(
            "<tr>"
            f"<td>{_e(item.get('filename'))}</td><td>{_e(item.get('content_type'))}</td>"
            f"<td>{_e(item.get('size'))}</td><td><code>{_e(item.get('sha256'))}</code></td>"
            f"<td>{_e(item.get('content_disposition'))}</td><td>{_e(item.get('content_id'))}</td>"
            f"<td>{_e(item.get('extension'))}</td>"
            "</tr>"
            for item in evidence.get("attachments", [])
        )
        or "<tr><td colspan='7'>No attachments identified.</td></tr>"
    )
    url_rows = (
        "".join(
            "<tr>"
            f"<td><code>{_e(item.get('url'))}</code></td>"
            f"<td>{_e(item.get('source_mime_part') or item.get('source'))}</td>"
            f"<td>{_e(item.get('displayed_text'))}</td>"
            f"<td>{_e(item.get('displayed_destination'))}</td>"
            f"<td>{_e(item.get('actual_href') or item.get('url'))}</td>"
            f"<td>{_e(item.get('host'))}</td>"
            f"<td>{'Yes' if item.get('display_href_mismatch') else 'No'}</td>"
            "</tr>"
            for item in evidence.get("urls", [])
        )
        or "<tr><td colspan='7'>No HTTP or HTTPS URLs identified.</td></tr>"
    )
    preview = mime.get("plain_text_preview")
    body_summary = (
        f"<pre>{_e(preview)}</pre>"
        if preview
        else "<p>No safe text body preview was available.</p>"
    )
    return f"""
        <h3>MIME structure</h3>
        <dl><dt>Root Content-Type</dt><dd>{_e((mime.get("root") or {}).get("content_type"))}</dd>
        <dt>Part count</dt><dd>{_e(mime.get("part_count"))}</dd>
        <dt>Maximum depth</dt><dd>{_e(mime.get("max_depth"))}</dd>
        <dt>text/plain present</dt><dd>{"Yes" if mime.get("text_plain_available") else "No"}</dd>
        <dt>text/html present</dt><dd>{"Yes" if mime.get("html_available") else "No"}</dd>
        <dt>HTML rendered</dt><dd>No</dd><dt>Remote resources loaded</dt><dd>No</dd></dl>
        <table><thead><tr><th>Part</th><th>Content-Type</th><th>Disposition</th><th>Filename</th><th>Decoded bytes</th></tr></thead><tbody>{part_rows}</tbody></table>
        <h3>Attachments</h3><table><thead><tr><th>Filename</th><th>MIME type</th><th>Bytes</th><th>SHA-256</th><th>Disposition</th><th>Content-ID</th><th>Extension</th></tr></thead><tbody>{attachment_rows}</tbody></table>
        <h3>URLs</h3><p>URLs were inventoried as text only; none were fetched.</p>
        <table><thead><tr><th>URL</th><th>Source MIME part</th><th>Displayed text</th><th>Displayed destination</th><th>Actual destination</th><th>Host/domain</th><th>Mismatch</th></tr></thead><tbody>{url_rows}</tbody></table>
        <h3>Body evidence summary</h3>{body_summary}"""


def html_report(case: Case) -> bytes:
    data = investigation_dict(case)
    sections: list[str] = []
    for evidence in data["evidence"]:
        parsed = evidence["parsed_message"]
        sender = (
            ", ".join(item.get("address", "") for item in parsed.get("from", [])) or "Not present"
        )
        obs_rows = (
            "".join(
                f"<tr><td>{_e(obs['severity'])}</td><td>{_e(obs['title'])}</td><td>{_e(obs['evidence_level'])}</td><td>{_e(', '.join(obs.get('evidence_reference', obs.get('supporting_headers', []))))}</td><td>{_e(obs['description'])}</td><td>{_e(obs['recommended_action'])}</td></tr>"
                for obs in evidence["observations"]
            )
            or "<tr><td colspan='6'>No observations generated.</td></tr>"
        )
        hop_rows = (
            "".join(
                f"<tr><td>{_e(hop['sequence'])}</td><td>{_e(hop['from_host'])}</td><td>{_e(hop['from_ip'])}</td><td>{_e(hop['by_host'])}</td><td>{_e(hop['utc_time'])}</td></tr>"
                for hop in evidence["delivery_hops"]
            )
            or "<tr><td colspan='5'>No Received hops parsed.</td></tr>"
        )
        entity_items = "".join(
            f"<li><strong>{_e(entity['type'])}</strong>: {_e(entity['value'])}</li>"
            for entity in evidence["entities"]
        )
        warning_items = (
            "".join(
                f"<li>{_e(warning.get('message'))}</li>" for warning in evidence["parse_warnings"]
            )
            or "<li>None</li>"
        )
        sections.append(f"""
        <section><h2>Evidence: {_e(evidence["filename"])}</h2>
        <dl><dt>SHA-256</dt><dd><code>{_e(evidence["sha256"])}</code></dd><dt>Parser</dt><dd>{_e(evidence["parser_version"])}</dd><dt>Sender</dt><dd>{_e(sender)}</dd><dt>Subject</dt><dd>{_e(parsed.get("subject"))}</dd><dt>Review priority</dt><dd>{_e(parsed.get("review_priority"))}</dd></dl>
        <h3>Parse warnings</h3><ul>{warning_items}</ul>
        <h3>Recorded authentication and alignment</h3><pre>{_e(json.dumps(evidence["authentication"], ensure_ascii=False, indent=2))}</pre>
        <h3>Delivery path</h3><table><thead><tr><th>#</th><th>From</th><th>IP</th><th>By</th><th>UTC time</th></tr></thead><tbody>{hop_rows}</tbody></table>
        <h3>Entities</h3><ul>{entity_items}</ul>
        {_html_message_evidence(evidence)}
        <h3>Observations</h3><table><thead><tr><th>Severity</th><th>Observation</th><th>Evidence level</th><th>Evidence reference</th><th>Explanation</th><th>Next action</th></tr></thead><tbody>{obs_rows}</tbody></table></section>""")
    notes = (
        "".join(
            f"<li><strong>{_e(n['author_label'])}</strong> ({_e(n['timestamp'])}): {_e(n['note'])}</li>"
            for n in data["analyst_notes"]
        )
        or "<li>No analyst notes.</li>"
    )
    limitations = "".join(f"<li>{_e(item)}</li>" for item in data["limitations"])
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:"><title>MailTrace report — {_e(case.title)}</title><style>
    body{{font:14px/1.5 system-ui,sans-serif;color:#1f2933;background:#fff;max-width:1100px;margin:auto;padding:32px}}h1,h2,h3{{color:#142b3a}}section{{border-top:1px solid #ccd5db;padding-top:20px;margin-top:28px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #c8d1d8;padding:7px;text-align:left;vertical-align:top}}th{{background:#eef2f4}}code,pre{{white-space:pre-wrap;word-break:break-word;background:#f6f7f8;padding:2px 4px}}dl{{display:grid;grid-template-columns:140px 1fr;gap:5px}}dt{{font-weight:700}}dd{{margin:0}}</style></head><body>
    <h1>MailTrace investigation report</h1><p><strong>Case:</strong> {_e(case.title)}<br><strong>Status:</strong> {_e(case.status)}<br><strong>Analyst conclusion:</strong> {_e(case.conclusion)}<br><strong>Generated:</strong> {_e(data["exported_at"])}</p><p>{_e(data["methodology_notice"])}</p>{"".join(sections)}<section><h2>Analyst notes</h2><ul>{notes}</ul><h2>Limitations</h2><ul>{limitations}</ul></section></body></html>"""
    return document.encode("utf-8")


def _pdf_message_evidence(evidence: dict[str, Any], styles: dict[str, Any]) -> list[Any]:
    mime = evidence.get("mime_structure") or {}
    blocks: list[Any] = []
    if not mime.get("available"):
        blocks.extend(
            [
                Paragraph("MIME, body, attachment and URL evidence", styles["Heading2"]),
                Paragraph(
                    _e(
                        mime.get("reason")
                        or "MIME/body evidence unavailable because only headers were supplied."
                    ),
                    styles["BodyText"],
                ),
            ]
        )
        return blocks

    root = mime.get("root") or {}
    blocks.extend(
        [
            Paragraph("MIME structure", styles["Heading2"]),
            Paragraph(
                f"Root Content-Type: <b>{_e(root.get('content_type'))}</b><br/>"
                f"Part count: {_e(mime.get('part_count'))}; maximum depth: {_e(mime.get('max_depth'))}<br/>"
                f"text/plain present: {'Yes' if mime.get('text_plain_available') else 'No'}; "
                f"text/html present: {'Yes' if mime.get('html_available') else 'No'}<br/>"
                "HTML rendered: No; remote resources loaded: No",
                styles["SmallBody"],
            ),
        ]
    )
    for part in _mime_parts(root):
        blocks.append(
            Paragraph(
                f"Part {_e(part['path'])}: {_e(part['content_type'])}; "
                f"disposition={_e(part['disposition'] or 'body')}; "
                f"filename={_e(part['filename'] or 'none')}; "
                f"decoded bytes={_e(part['decoded_size'])}",
                styles["SmallBody"],
            )
        )

    blocks.append(Paragraph("Attachments", styles["Heading2"]))
    if evidence.get("attachments"):
        for item in evidence["attachments"]:
            blocks.extend(
                [
                    Paragraph(
                        f"<b>{_e(item.get('filename'))}</b> - {_e(item.get('content_type'))}; "
                        f"{_e(item.get('size'))} bytes; disposition={_e(item.get('content_disposition'))}; "
                        f"extension={_e(item.get('extension'))}; Content-ID={_e(item.get('content_id'))}",
                        styles["SmallBody"],
                    ),
                    Paragraph(f"SHA-256: {_e(item.get('sha256'))}", styles["SmallBody"]),
                    Spacer(1, 4),
                ]
            )
    else:
        blocks.append(Paragraph("No attachments identified.", styles["BodyText"]))

    url_heading = [
        Paragraph("URLs", styles["Heading2"]),
        Paragraph("URLs were inventoried as text only; none were fetched.", styles["SmallBody"]),
    ]
    if evidence.get("urls"):
        for index, item in enumerate(evidence["urls"]):
            url_details = Paragraph(
                f"<b>URL:</b> {_e(item.get('url'))}<br/>"
                f"<b>Source MIME part:</b> {_e(item.get('source_mime_part') or item.get('source'))}<br/>"
                f"<b>Displayed text:</b> {_e(item.get('displayed_text') or 'Not captured')}<br/>"
                f"<b>Displayed destination:</b> {_e(item.get('displayed_destination') or 'Not identified')}<br/>"
                f"<b>Actual destination:</b> {_e(item.get('actual_href') or item.get('url'))}<br/>"
                f"<b>Host/domain:</b> {_e(item.get('host'))}<br/>"
                f"<b>Mismatch:</b> {'Yes' if item.get('display_href_mismatch') else 'No'}",
                styles["SmallBody"],
            )
            blocks.append(
                KeepTogether(
                    [
                        *(url_heading if index == 0 else []),
                        url_details,
                        Spacer(1, 5),
                    ]
                )
            )
    else:
        blocks.extend(url_heading)
        blocks.append(Paragraph("No HTTP or HTTPS URLs identified.", styles["BodyText"]))

    blocks.append(Paragraph("Body evidence summary", styles["Heading2"]))
    preview = str(mime.get("plain_text_preview") or "")
    if preview:
        blocks.append(Paragraph(_e(preview[:1500]).replace("\n", "<br/>"), styles["SmallBody"]))
    else:
        blocks.append(Paragraph("No safe text body preview was available.", styles["BodyText"]))
    return blocks


def pdf_report(case: Case) -> bytes:
    data = investigation_dict(case)
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"MailTrace report - {case.title}",
        author="MailTrace",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SmallBody", parent=styles["BodyText"], fontSize=8, leading=10, alignment=TA_LEFT
        )
    )
    story: list[Any] = [
        Paragraph("MailTrace investigation report", styles["Title"]),
        Paragraph(f"Case: {_e(case.title)}", styles["Heading2"]),
        Paragraph(
            f"Status: {_e(case.status)} &nbsp;&nbsp; Analyst conclusion: {_e(case.conclusion)}",
            styles["BodyText"],
        ),
        Spacer(1, 8),
        Paragraph(_e(data["methodology_notice"]), styles["BodyText"]),
    ]
    for index, evidence in enumerate(data["evidence"]):
        if index:
            story.append(PageBreak())
        parsed = evidence["parsed_message"]
        story.extend(
            [
                Paragraph(f"Evidence: {_e(evidence['filename'])}", styles["Heading1"]),
                Paragraph(f"SHA-256: {_e(evidence['sha256'])}", styles["SmallBody"]),
                Paragraph(f"Parser: {_e(evidence['parser_version'])}", styles["BodyText"]),
                Paragraph(f"Subject: {_e(parsed.get('subject'))}", styles["BodyText"]),
                Paragraph("Recorded authentication and alignment", styles["Heading2"]),
                Paragraph(
                    _e(json.dumps(evidence["authentication"], ensure_ascii=False, indent=2)),
                    styles["SmallBody"],
                ),
                Paragraph("Delivery path", styles["Heading2"]),
            ]
        )
        hop_data = [["#", "From / IP", "By", "UTC time"]] + [
            [
                str(h["sequence"]),
                f"{h.get('from_host') or ''}\n{h.get('from_ip') or ''}\n{(h.get('ip_classification') or {}).get('classification', '')}",
                h.get("by_host") or "",
                h.get("utc_time") or "",
            ]
            for h in evidence["delivery_hops"]
        ]
        table = Table(hop_data, colWidths=[10 * mm, 55 * mm, 45 * mm, 55 * mm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef1")),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(table)
        story.extend(_pdf_message_evidence(evidence, styles))
        story.append(Paragraph("Observations", styles["Heading2"]))
        if evidence["observations"]:
            for obs in evidence["observations"]:
                story.append(
                    Paragraph(
                        f"<b>{_e(obs['severity']).upper()} - {_e(obs['title'])}</b><br/>"
                        f"{_e(obs['description'])}<br/><i>Evidence:</i> "
                        f"{_e(', '.join(obs.get('evidence_reference', obs.get('supporting_headers', []))))}<br/>"
                        f"<i>Next action:</i> {_e(obs['recommended_action'])}",
                        styles["SmallBody"],
                    )
                )
                story.append(Spacer(1, 5))
        else:
            story.append(Paragraph("No observations generated.", styles["BodyText"]))
    story.extend([Spacer(1, 12), Paragraph("Analyst notes", styles["Heading1"])])
    for note in data["analyst_notes"]:
        story.append(
            Paragraph(
                f"<b>{_e(note['author_label'])}</b> - {_e(note['timestamp'])}<br/>{_e(note['note'])}",
                styles["BodyText"],
            )
        )
    story.append(Paragraph("Limitations", styles["Heading1"]))
    for limitation in data["limitations"]:
        story.append(Paragraph(f"• {_e(limitation)}", styles["BodyText"]))
    doc.build(story)
    return output.getvalue()


def _csv_safe(value: object) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in {"=", "+", "-", "@", "\t", "\r"} else text


def csv_report(case: Case) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(
        [
            "case_id",
            "evidence_id",
            "rule_id",
            "severity",
            "confidence",
            "evidence_level",
            "title",
            "description",
            "supporting_headers",
            "recommended_action",
        ]
    )
    for evidence in case.evidence:
        for obs in evidence.observations:
            writer.writerow(
                [
                    _csv_safe(case.id),
                    _csv_safe(evidence.id),
                    _csv_safe(obs.get("rule_id")),
                    _csv_safe(obs.get("severity")),
                    _csv_safe(obs.get("confidence")),
                    _csv_safe(obs.get("evidence_level")),
                    _csv_safe(obs.get("title")),
                    _csv_safe(obs.get("description")),
                    _csv_safe("; ".join(obs.get("supporting_headers", []))),
                    _csv_safe(obs.get("recommended_action")),
                ]
            )
    return b"\xef\xbb\xbf" + stream.getvalue().encode("utf-8")


def bundle_report(case: Case, originals: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    base = safe_filename(case.title, "case")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(f"{base}/investigation.json", json_report(case))
        bundle.writestr(f"{base}/report.html", html_report(case))
        bundle.writestr(f"{base}/report.pdf", pdf_report(case))
        bundle.writestr(f"{base}/observations.csv", csv_report(case))
        for evidence in case.evidence:
            content = originals.get(evidence.id)
            if content is not None:
                bundle.writestr(
                    f"{base}/originals/{evidence.id}-{safe_filename(evidence.original_filename)}",
                    content,
                )
    return output.getvalue()
