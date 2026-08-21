from __future__ import annotations

import json
from pathlib import Path

from mailtrace.config import Settings
from mailtrace.parser import parse_evidence

ROOT = Path(__file__).parents[1] / "mailtrace" / "fixtures"


def test_versioned_ground_truth_covers_and_validates_24_fixtures(
    settings: Settings,
) -> None:
    truth = json.loads((ROOT / "ground-truth.json").read_text(encoding="utf-8"))
    assert truth["version"] == 1
    assert len(truth["fixtures"]) == 24
    for slug, expected in truth["fixtures"].items():
        result = parse_evidence((ROOT / f"{slug}.eml").read_bytes(), "eml", settings)
        rules = {item["rule_id"] for item in result["observations"]}
        assert set(expected.get("expected_observations", [])) <= rules, slug
        assert not set(expected.get("expected_absent", [])) & rules, slug
        if "expected_subject" in expected:
            assert result["parsed_message"]["subject"] == expected["expected_subject"]
        if "expected_attachment" in expected:
            assert result["attachments"][0]["filename"] == expected["expected_attachment"]
        if "expected_urls" in expected:
            assert len(result["urls"]) == expected["expected_urls"]
