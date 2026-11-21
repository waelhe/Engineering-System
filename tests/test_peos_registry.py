from pathlib import Path
import json

from jsonschema import Draft202012Validator

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

def test_w3_capability_candidates_are_source_linked_and_not_current_proof():
    root = Path(__file__).resolve().parents[1]
    capabilities = json.loads((root / "registry/peos/app-java-v3.capabilities.json").read_text(encoding="utf-8"))
    journeys = json.loads((root / "registry/peos/app-java-v3.journeys.json").read_text(encoding="utf-8"))
    by_journey = {item["journey_id"]: item for item in journeys["records"]}

    assert capabilities["kind"] == "capability_registry"
    assert capabilities["anomalies"] == []
    assert capabilities["source"]["repository"] == "waelhe/app-java-v3"
    assert capabilities["source"]["commit_sha"] == journeys["source"]["commit_sha"]
    assert len(capabilities["records"]) == 35
    assert {item["source_journey_id"] for item in capabilities["records"]} == set(by_journey)

    for item in capabilities["records"]:
        journey = by_journey[item["source_journey_id"]]
        assert item["title"] == journey["title"]
        assert item["documented_module_names"] == journey.get("owning_modules_as_documented", [])
        assert item["source_journey_status_authority"] == "historical_source_snapshot_only"
        assert item["acceptance_state"] == "candidate_not_adjudicated"
        assert item["module_mapping_status"] == "not_adjudicated"
        assert set(item["verification"][surface] for surface in ("backend", "android", "admin", "provider", "production")) == {"not_revalidated"}
        assert item["verification"]["tested_head_sha"] is None
        assert item["verification"]["workflow_run_ids"] == []


def test_w3_schema_rejects_promoting_historical_candidate_to_verified():
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "schemas/peos-capabilities.schema.json").read_text(encoding="utf-8"))
    payload = json.loads((root / "registry/peos/app-java-v3.capabilities.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert not list(Draft202012Validator(schema).iter_errors(payload))

    payload["records"][0]["acceptance_state"] = "verified"
    assert list(Draft202012Validator(schema).iter_errors(payload))


def test_w4_critical_risk_snapshot_is_exact_sha_bound_and_conservative():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "registry/peos/app-java-v3.critical-risks.json").read_text(encoding="utf-8"))
    assert payload["kind"] == "critical_risk_registry"
    assert payload["source"]["commit_sha"] == "8b1d2a82bf5c870d88ffc7d5d05e36bb06175c26"
    assert len(payload["records"]) == 7
    by_id = {item["risk_id"]: item for item in payload["records"]}
    assert len(by_id) == 7
    for item in payload["records"]:
        assert item["pull_request"]["head_sha"] == item["checks"]["head_sha"]
        assert item["closure_evidence"] is None
        assert item["status"] != "closed_verified"
        if item["review"]["approval_on_current_head"]:
            assert item["review"]["latest_sha"] == item["pull_request"]["head_sha"]

    a1 = by_id["W4-A1-001"]
    assert a1["status"] == "blocked_owner_decision"
    assert a1["pull_request"]["number"] == 832
    assert any("owner-gate recommendation" in fact for fact in a1["assessment"]["confirmed_facts"])

    a3 = by_id["W4-A3-001"]
    assert a3["status"] == "partial_candidate"
    assert a3["pull_request"]["behind_by"] == 2
    assert any("recognize()" in gap for gap in a3["assessment"]["blocking_gaps"])

    g3 = by_id["W4-G3-001"]
    assert g3["status"] == "partial_candidate"
    assert any("version" in gap.lower() for gap in g3["assessment"]["blocking_gaps"])
    assert any("provider" in unknown for unknown in g3["assessment"]["unknowns"])


def test_w4_schema_rejects_closing_a_risk_without_post_merge_evidence():
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "schemas/peos-critical-risks.schema.json").read_text(encoding="utf-8"))
    payload = json.loads((root / "registry/peos/app-java-v3.critical-risks.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert not list(Draft202012Validator(schema).iter_errors(payload))

    payload["records"][0]["status"] = "closed_verified"
    assert list(Draft202012Validator(schema).iter_errors(payload))

    payload["records"][0]["status"] = "blocked_owner_decision"
    payload["records"][0]["closure_evidence"] = {
        "merged_pr_number": 832,
        "merge_commit_sha": "1" * 40,
        "verified_main_sha": payload["source"]["commit_sha"],
        "main_contains_merge_commit": True,
        "post_merge_workflow_url": "https://github.com/waelhe/app-java-v3/actions/runs/1",
        "post_merge_conclusion": "success"
    }
    assert list(Draft202012Validator(schema).iter_errors(payload))



def test_w5_w6_w7_snapshots_are_schema_valid_and_keep_unknowns_explicit():
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "schemas/peos-current-evidence.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    paths = {
        "w5_backend_commerce_snapshot": "registry/peos/app-java-v3.w5-backend-commerce.json",
        "w6_client_delivery_snapshot": "registry/peos/clients.w6-current.json",
        "w7_operations_snapshot": "registry/peos/operations.w7-current.json",
    }
    payloads = {}
    for kind, relative_path in paths.items():
        payload = json.loads((root / relative_path).read_text(encoding="utf-8"))
        assert payload["kind"] == kind
        assert payload["snapshot_date"] == "2026-11-21"
        assert not list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload))
        payloads[kind] = payload

    w5 = {item["pr_number"]: item for item in payloads["w5_backend_commerce_snapshot"]["records"]}
    assert w5[787]["state"] == "open"
    assert w5[842]["state"] == "merged"
    assert any(item["conclusion"] == "failure" for item in w5[840]["checks"])
    assert w5[832]["state"] == "open"

    w6 = {item["surface"]: item for item in payloads["w6_client_delivery_snapshot"]["records"]}
    assert "Expo SDK" in w6["android"]["runtime"]
    assert w6["android"]["journey_state"] == "not_revalidated"
    assert w6["admin"]["journey_state"] == "not_revalidated"

    w7 = {item["surface"]: item for item in payloads["w7_operations_snapshot"]["records"]}
    assert w7["production_backend"]["service_state"] == "online"
    assert w7["production_backend"]["latest_attempt"]["state"] == "failed"
    assert w7["alerting_and_routing"]["notification_policy_receiver"] == "empty"
    assert w7["alerting_and_routing"]["alert_rules_read_result"] == "null"


def test_current_evidence_validator_rejects_false_production_recovery():
    root = Path(__file__).resolve().parents[1]
    production = json.loads((root / "registry/peos/operations.w7-current.json").read_text(encoding="utf-8"))
    target = next(item for item in production["records"] if item["surface"] == "production_backend")
    target["latest_attempt"]["state"] = "success"
    assert target["service_state"] == "online"
    # A healthy active replica does not convert the latest failed deployment attempt into success.
    assert target["latest_attempt"]["state"] == "success"
    original = json.loads((root / "registry/peos/operations.w7-current.json").read_text(encoding="utf-8"))
    assert original["records"][0]["latest_attempt"]["state"] == "failed"
