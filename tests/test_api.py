from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from mailtrace.config import Settings, get_settings
from mailtrace.db import Base, get_db
from mailtrace.main import SPAStaticFiles, create_app

FIXTURES = Path(__file__).parents[1] / "mailtrace" / "fixtures"


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(data_dir=tmp_path / "data")
    settings.ensure_directories()

    def db_override() -> Generator[Session, None, None]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app, raise_server_exceptions=False) as value:
        yield value


def create_headers(client: TestClient) -> str:
    response = client.post(
        "/api/analyses/headers",
        json={
            "raw_headers": (
                "From: Alice <alice@example.com>\r\n"
                "To: Bob <bob@example.net>\r\n"
                "Subject: API analysis\r\n"
                "Message-ID: <one@example.com>\r\n\r\n"
            ),
            "retain_original": True,
        },
    )
    assert response.status_code == 202, response.text
    return str(response.json()["id"])


def test_health_settings_methodology_and_security_headers(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.json()["status"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-request-id"]
    settings = client.get("/api/settings").json()
    assert settings["local_first"] is True
    assert settings["preferences"]["dns_enrichment_enabled"] is False
    changed = client.put(
        "/api/settings",
        json={"retention_days": 30, "dns_enrichment_enabled": True},
    )
    assert changed.json()["retention_days"] == 30
    assert client.get("/api/methodology").json()["network_default"] == "disabled"


def test_spa_deep_link_and_missing_asset(tmp_path: Path) -> None:
    static_dir = tmp_path / "dist"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("MailTrace test shell", encoding="utf-8")
    app = FastAPI()
    app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="spa")

    test_client = TestClient(app)
    deep_link = test_client.get("/settings", headers={"accept": "text/html"})
    assert deep_link.status_code == 200
    assert "MailTrace" in deep_link.text

    missing_asset = test_client.get("/missing.js")
    assert missing_asset.status_code == 404


def test_analysis_header_lifecycle_and_exports(client: TestClient) -> None:
    analysis_id = create_headers(client)
    state = client.get(f"/api/analyses/{analysis_id}/state")
    assert state.json()["status"] == "complete"
    result = client.get(f"/api/analyses/{analysis_id}").json()
    assert result["summary"]["subject"] == "API analysis"
    assert result["raw_available"] is True
    assert result["mime_structure"]["available"] is False
    assert len(client.get("/api/analyses").json()) == 1
    raw = client.get(f"/api/analyses/{analysis_id}/raw")
    assert raw.status_code == 200 and b"From: Alice" in raw.content
    for format_name, prefix in (
        ("json", b"{"),
        ("csv", b"\xef\xbb\xbf"),
        ("pdf", b"%PDF-"),
        ("html", b"<!doctype html>"),
        ("txt", b"MAILTRACE"),
        ("bundle", b"PK"),
    ):
        exported = client.get(f"/api/analyses/{analysis_id}/exports/{format_name}")
        assert exported.status_code == 200
        assert exported.content.startswith(prefix)
    assert client.delete(f"/api/analyses/{analysis_id}").status_code == 204
    assert client.get(f"/api/analyses/{analysis_id}").status_code == 404


def test_analysis_upload_validation_and_mime(client: TestClient) -> None:
    raw = (FIXTURES / "incomplete-auth.eml").read_bytes()
    response = client.post(
        "/api/analyses/upload",
        files={"file": ("message.eml", raw, "message/rfc822")},
        data={"retain_original": "true"},
    )
    assert response.status_code == 202
    result = client.get(f"/api/analyses/{response.json()['id']}").json()
    assert result["attachments"][0]["filename"] == "agenda.txt"
    assert result["mime_structure"]["available"] is True
    assert result["summary"]["assessment"]["label"]
    wrong = client.post(
        "/api/analyses/upload",
        files={"file": ("message.exe", b"test", "application/octet-stream")},
        data={"retain_original": "true"},
    )
    assert wrong.status_code == 415
    empty = client.post(
        "/api/analyses/headers",
        json={"raw_headers": "", "retain_original": True},
    )
    assert empty.status_code == 422


def test_case_note_conclusion_and_report_compatibility(client: TestClient) -> None:
    created = client.post(
        "/api/cases", json={"title": "Compatibility case", "description": "Existing API"}
    )
    assert created.status_code == 201
    case_id = created.json()["id"]
    assert client.get(f"/api/cases/{case_id}").status_code == 200
    assert len(client.get("/api/cases?search=Compatibility").json()) == 1
    updated = client.patch(
        f"/api/cases/{case_id}", json={"title": "Updated case", "status": "closed"}
    )
    assert updated.json()["status"] == "closed"
    note = client.post(
        f"/api/cases/{case_id}/notes",
        json={"note": "Reviewed locally", "author_label": "Analyst"},
    )
    assert note.status_code == 201
    note_id = note.json()["id"]
    assert (
        client.put(
            f"/api/cases/{case_id}/conclusion",
            json={"conclusion": "inconclusive"},
        ).status_code
        == 200
    )
    assert client.get(f"/api/cases/{case_id}/reports/json").status_code == 200
    upload = client.post(
        f"/api/cases/{case_id}/evidence/upload",
        files={"file": ("headers.txt", b"From: upload@example.com\r\n\r\n", "text/plain")},
        data={"retain_original": "false"},
    )
    assert upload.status_code == 201
    rejected = client.post(
        f"/api/cases/{case_id}/evidence/upload",
        files={"file": ("bad.exe", b"bad", "application/octet-stream")},
        data={"retain_original": "false"},
    )
    assert rejected.status_code == 415
    pasted = client.post(
        f"/api/cases/{case_id}/evidence/paste",
        json={"raw_headers": "From: one@example.com\r\n\r\n", "retain_original": True},
    )
    assert pasted.status_code == 201
    evidence_id = pasted.json()["id"]
    assert client.get(f"/api/cases/{case_id}/evidence/{evidence_id}").status_code == 200
    assert client.delete(f"/api/cases/{case_id}/evidence/{evidence_id}/original").status_code == 204
    assert client.get(f"/api/cases/{case_id}/evidence/{evidence_id}/raw").status_code == 410
    assert client.delete(f"/api/cases/{case_id}/notes/missing").status_code == 404
    assert client.delete(f"/api/cases/{case_id}/notes/{note_id}").status_code == 204
    assert client.delete(f"/api/cases/{case_id}").status_code == 204


def test_demo_dns_guard_and_missing_resources(client: TestClient) -> None:
    demos = client.get("/api/demos").json()
    assert len(demos) == 10
    demo = client.post("/api/demos/aligned-business/load")
    assert demo.status_code == 201
    assert client.post("/api/demos/not-a-demo/load").status_code == 404
    assert client.get("/api/cases/missing").status_code == 404
    assert client.get("/api/analyses/missing/state").status_code == 404
    assert client.delete("/api/analyses/missing").status_code == 404
    assert client.get("/api/analyses/missing/raw").status_code == 404
    assert client.post("/api/dns/lookup", json={"domain": "invalid"}).status_code in {
        403,
        422,
    }
    client.put(
        "/api/settings",
        json={"retention_days": None, "dns_enrichment_enabled": True},
    )
    assert client.post("/api/dns/lookup", json={"domain": "invalid"}).status_code == 422
    assert client.get("/api/cases?status=closed").status_code == 200
