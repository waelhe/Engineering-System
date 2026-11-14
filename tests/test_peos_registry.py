from pathlib import Path
import json

from tools.peos_validate import validate_registry


def test_w0_inventory_is_consistent():
    assert validate_registry(Path(__file__).resolve().parents[1]) == []


def test_tracking_shards_are_not_merge_candidates():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "registry/peos/app-java-v3.open-prs.json").read_text(encoding="utf-8"))
    by_number = {record["number"]: record for record in payload["records"]}
    assert all(by_number[number]["merge_policy"] == "tracking_only" for number in range(806, 812))
    assert all(by_number[number]["allowed_to_merge"] is False for number in range(806, 812))


def test_journey_j29_source_anomaly_is_retained():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "registry/peos/app-java-v3.journeys.json").read_text(encoding="utf-8"))
    assert any(item["id"] == "W0-JOURNEY-001" and "J29" in item["affected_journeys"]
               for item in payload["anomalies"])
    j29 = next(item for item in payload["records"] if item["journey_id"] == "J29")
    assert j29["source_occurrences"] == 2
