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


def test_w1_operations_snapshot_keeps_runtime_and_observability_truth():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "registry/peos/app-java-v3.operations.json").read_text(encoding="utf-8"))
    by_id = {record["id"]: record for record in payload["records"]}
    assert by_id["OPS-RAILWAY-001"]["state"] == "offline"
    assert by_id["OPS-GRAFANA-001"]["state"] == "no_series"
    assert by_id["OPS-GRAFANA-003"]["state"] == "no_alert_rules"
    assert by_id["OPS-GRAFANA-004"]["state"] == "no_notification_destination"
    assert by_id["OPS-GITHUB-002"]["state"] == "open_incident"
    # OAuth secrets and service-account tokens must never enter PEOS source control.
    serialized = json.dumps(payload).lower()
    assert "client_secret" not in serialized
    assert "service_account_token" not in serialized


def test_w2_module_boundary_inventory_preserves_maven_and_modulith_graphs():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "registry/peos/app-java-v3.module-boundaries.json").read_text(encoding="utf-8"))
    by_logical = {record["module_name"]: record for record in payload["records"]}
    by_maven = {record["module_id"]: record for record in payload["maven_modules"]}

    assert payload["source"]["commit_sha"] == "8b1d2a82bf5c870d88ffc7d5d05e36bb06175c26"
    assert len(by_logical) == 30
    assert len(by_maven) == 30
    assert by_maven["marketplace-platform-infra"]["modulith_modules"] == ["shared"]
    assert set(by_maven["marketplace-app"]["modulith_modules"]) == {"app", "admin", "config"}
    assert by_maven["marketplace-edge"]["modulith_modules"] == []
    assert by_logical["admin"]["declaration"]["path"] == "marketplace-app/src/main/java/com/marketplace/admin/package-info.java"
    assert by_logical["config"]["declaration"]["path"] == "marketplace-app/src/main/java/com/marketplace/config/package-info.java"
    assert by_maven["marketplace-edge"]["reactor_role"] == "standalone_edge_bff"
    assert {name for name, item in by_logical.items()
            if item["declaration"]["placement"] == "type"} == {
                "availability", "disputes", "ledger", "notifications", "provider"
            }
    assert all(item["domain_ownership"] == "not_adjudicated" for item in payload["records"])
    assert "catalog :: catalog-spi" in by_logical["messaging"]["allowed_dependencies"]
    assert "catalog :: catalog-spi" in by_logical["realestate"]["allowed_dependencies"]


def test_w1_recheck_records_partial_recovery_without_claiming_operational_readiness():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "registry/peos/app-java-v3.operations.json").read_text(encoding="utf-8"))
    by_id = {record["id"]: record for record in payload["records"]}

    railway = by_id["OPS-RAILWAY-003"]
    assert railway["state"] == "deployment_succeeded_last_aggregate_probe_degraded"
    http = next(item["value"] for item in railway["evidence"] if item["kind"] == "http_probe_log")
    statuses = {item["path"]: item["status"] for item in http["probes"]}
    assert statuses["/actuator/health/liveness"] == 200
    assert statuses["/actuator/health/readiness"] == 200
    assert statuses["/actuator/health"] == 503
    eventbus = next(item["value"] for item in railway["evidence"] if item["kind"] == "application_metric")
    assert eventbus["metric"] == "marketplace_eventbus_stale"
    assert eventbus["value"] == 3

    grafana = by_id["OPS-GRAFANA-005"]
    assert grafana["state"] == "metrics_ingested_alert_delivery_unconfigured"
    alerting = next(item["value"] for item in grafana["evidence"] if item["kind"] == "grafana_alerting_read")
    assert alerting["grafana_managed_alert_rule_count"] == 0
    assert alerting["contact_point_count"] == 0
    assert alerting["root_notification_receiver"] == "empty"

    pr = by_id["OPS-GITHUB-003"]
    assert pr["state"] == "repair_pr_deployed_open_unreviewed"
    details = pr["evidence"][0]["value"]
    assert details["merged"] is False
    assert details["review_count"] == 0

    serialized = json.dumps(payload).lower()
    assert "client_secret" not in serialized
    assert "service_account_token" not in serialized
