import json
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "task.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)
MANDATORY_T3_TRIGGERS = (
    "security", "identity", "money", "ledger", "concurrency",
    "data_migration", "destructive_data", "external_side_effect",
    "public_contract", "production", "architecture",
)


def task(tier: str, risk_triggers: list[str]) -> dict:
    return {
        "task_id": "task-001",
        "project_id": "sample-project",
        "description": "Test task risk classification.",
        "tier": tier,
        "risk_triggers": risk_triggers,
        "affected_scope": {},
        "requested_outcome": "Validate the schema invariant.",
    }


def test_each_mandatory_t3_trigger_rejects_lower_tiers():
    for trigger in MANDATORY_T3_TRIGGERS:
        assert not VALIDATOR.is_valid(task("T1", [trigger])), trigger
        assert not VALIDATOR.is_valid(task("T2", [trigger])), trigger
        assert VALIDATOR.is_valid(task("T3", [trigger])), trigger


def test_tasks_without_mandatory_t3_triggers_can_remain_t1():
    assert VALIDATOR.is_valid(task("T1", []))
