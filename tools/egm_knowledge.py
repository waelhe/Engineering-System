#!/usr/bin/env python3
"""Deterministic knowledge intake, validation, indexing and retrieval for EGM."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge"
SCHEMAS = ROOT / "schemas"
RECORD_SCHEMA = SCHEMAS / "knowledge-record.schema.json"
PROFILE_SCHEMA = SCHEMAS / "project-profile.schema.json"
RECEIPT_SCHEMA = SCHEMAS / "execution-receipt.schema.json"
RECORD_DIRS = (
    "inbox", "evidence", "findings", "cases", "patterns", "decisions",
    "rules", "controls", "actions", "risk-acceptances", "verifications",
)
SOURCE_KINDS = {
    "github_issue", "github_pr", "github_review", "github_comment",
    "ci_run", "test_result", "incident", "commit", "document",
    "human_report", "official_documentation", "other",
}
RELATION_TYPES = {
    "reconstructed_as": {("finding", "case")},
    "exhibits": {("case", "pattern")},
    "motivates": {("pattern", "rule")},
    "constrains": {("decision", "project"), ("decision", "rule")},
    "enforced_by": {("rule", "control")},
    "verified_by": {("control", "verification")},
    "resolved_by": {("finding", "action"), ("case", "action")},
    "proven_by": {("action", "verification")},
    "reopens": {
        ("signal", "finding"), ("signal", "case"),
        ("finding", "finding"), ("finding", "case"),
        ("case", "case"),
    },
}
SECRET_PATTERNS = (
    (re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]{16,}"), "Bearer [REDACTED]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_ACCESS_KEY]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{15,}\b"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"(?i)(password|passwd|secret|token)\s*[:=]\s*[^\s,;]{8,}"), r"\1=[REDACTED]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
)


class KnowledgeError(Exception):
    """Raised when a knowledge operation cannot safely continue."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KnowledgeError(f"{path}: cannot read valid JSON: {exc}") from exc


def load_schema(path: Path) -> dict[str, Any]:
    schema = read_json(path)
    Draft202012Validator.check_schema(schema)
    return schema


def schema_errors(instance: Any, schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        f"{'/'.join(str(x) for x in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda e: list(map(str, e.absolute_path)))
    ]


def iter_records() -> list[tuple[Path, dict[str, Any]]]:
    result: list[tuple[Path, dict[str, Any]]] = []
    for folder in RECORD_DIRS:
        directory = KNOWLEDGE / folder
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.json")):
            value = read_json(path)
            if not isinstance(value, dict):
                raise KnowledgeError(f"{path}: record must be a JSON object")
            result.append((path, value))
    return result


def validate_all() -> list[dict[str, str]]:
    record_schema = load_schema(RECORD_SCHEMA)
    profile_schema = load_schema(PROFILE_SCHEMA)
    records = iter_records()
    errors: list[dict[str, str]] = []
    by_id: dict[str, dict[str, Any]] = {}
    project_ids: set[str] = set()

    for path in sorted((KNOWLEDGE / "projects").rglob("*.json")) if (KNOWLEDGE / "projects").exists() else []:
        profile = read_json(path)
        for message in schema_errors(profile, profile_schema):
            errors.append({"path": path.relative_to(ROOT).as_posix(), "error": message})
        project_id = profile.get("project_id") if isinstance(profile, dict) else None
        if isinstance(project_id, str):
            if project_id in project_ids:
                errors.append({"path": path.relative_to(ROOT).as_posix(), "error": f"duplicate project_id: {project_id}"})
            project_ids.add(project_id)
            by_id[project_id] = {"type": "project", **profile}

    for path, record in records:
        for message in schema_errors(record, record_schema):
            errors.append({"path": path.relative_to(ROOT).as_posix(), "error": message})
        record_id = record.get("id")
        if isinstance(record_id, str):
            if record_id in by_id:
                errors.append({"path": path.relative_to(ROOT).as_posix(), "error": f"duplicate record id: {record_id}"})
            else:
                by_id[record_id] = record

    for path, record in records:
        if record.get("project_id") not in project_ids:
            errors.append({"path": path.relative_to(ROOT).as_posix(), "error": f"unknown project_id: {record.get('project_id')}"})
        for relation in record.get("relations", []):
            target_id = relation.get("target_id")
            target = by_id.get(target_id)
            if target is None:
                errors.append({"path": path.relative_to(ROOT).as_posix(), "error": f"unresolved relation target: {target_id}"})
                continue
            if target_id == record.get("id"):
                errors.append({"path": path.relative_to(ROOT).as_posix(), "error": "self-referential relation is not allowed"})
                continue
            allowed = RELATION_TYPES.get(relation.get("type"))
            if allowed and (record.get("type"), target.get("type")) not in allowed:
                errors.append({
                    "path": path.relative_to(ROOT).as_posix(),
                    "error": f"relation {relation.get('type')} is not valid from {record.get('type')} to {target.get('type')}",
                })

    for path, record in records:
        if record.get("type") != "finding" or record.get("lifecycle") != "closed":
            continue
        resolved = [
            by_id.get(rel.get("target_id"))
            for rel in record.get("relations", [])
            if rel.get("type") == "resolved_by"
        ]
        direct_proof = any(rel.get("type") == "proven_by" for rel in record.get("relations", []))
        action_proof = any(
            isinstance(action, dict) and any(rel.get("type") == "proven_by" for rel in action.get("relations", []))
            for action in resolved
        )
        if not (direct_proof or action_proof):
            errors.append({
                "path": path.relative_to(ROOT).as_posix(),
                "error": "closed Finding requires direct proof or a resolved Action linked to Verification",
            })
    return errors


def build_index() -> dict[str, Any]:
    errors = validate_all()
    if errors:
        raise KnowledgeError("knowledge validation failed; index not generated: " + json.dumps(errors, ensure_ascii=False))
    items = []
    for path, record in iter_records():
        items.append({
            "id": record["id"],
            "type": record["type"],
            "project_id": record["project_id"],
            "title": record["title"],
            "summary": record["summary"],
            "assessment": record["assessment"],
            "lifecycle": record["lifecycle"],
            "approval": record["approval"],
            "tags": record.get("tags", []),
            "scope": record.get("scope", {}),
            "relations": record.get("relations", []),
            "sources": record.get("sources", []),
            "path": path.relative_to(ROOT).as_posix(),
        })
    items.sort(key=lambda item: (item["project_id"], item["type"], item["id"]))
    return {"index_version": 1, "record_count": len(items), "records": items}


def write_index(check: bool = False) -> bool:
    rendered = json.dumps(build_index(), indent=2, ensure_ascii=False) + "\n"
    target = KNOWLEDGE / "index.json"
    if check:
        return target.exists() and target.read_text(encoding="utf-8") == rendered
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    return True


def tokenize(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9][a-z0-9_.:/-]*", value.lower()) if len(token) > 1}


def retrieve(query: str, project_id: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
    if limit < 1 or limit > 100:
        raise KnowledgeError("limit must be between 1 and 100")
    # Read canonical records, not a possibly stale generated index.
    index = build_index()
    terms = tokenize(query)
    ranked = []
    for item in index.get("records", []):
        if project_id and item["project_id"] != project_id:
            continue
        if item.get("approval") == "rejected" or item.get("assessment") == "superseded":
            continue
        title_terms = tokenize(item["title"])
        summary_terms = tokenize(item["summary"])
        tags = set().union(*(tokenize(tag) for tag in item.get("tags", [])))
        scope_terms: set[str] = set()
        for values in item.get("scope", {}).values():
            if isinstance(values, list):
                for value in values:
                    scope_terms |= tokenize(str(value))
        score = 0
        matched = []
        for term in sorted(terms):
            weight = (6 if term in title_terms else 0) + (4 if term in tags else 0) + (3 if term in scope_terms else 0) + (1 if term in summary_terms else 0)
            if weight:
                score += weight
                matched.append(term)
        if score:
            ranked.append({**item, "score": score, "matched_terms": matched})
    ranked.sort(key=lambda item: (-item["score"], item["type"], item["id"]))
    return ranked[:limit]


def redact_excerpt(value: str, maximum: int = 1200) -> str:
    result = value[:maximum]
    for pattern, replacement in SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def receive_signal(payload: dict[str, Any]) -> tuple[str, Path]:
    required = ("project_id", "provider", "source_id", "source_url", "title", "body")
    missing = [key for key in required if not isinstance(payload.get(key), str) or not payload[key].strip()]
    if missing:
        raise KnowledgeError("missing non-empty intake fields: " + ", ".join(missing))
    if len(payload["body"]) > 300_000:
        raise KnowledgeError("source body exceeds the 300 KB intake limit")
    parsed = urlparse(payload["source_url"])
    if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password:
        raise KnowledgeError("source_url must be an absolute HTTP(S) URL without embedded credentials")
    # Signed query strings are omitted to avoid persisting bearer-style URL credentials.
    safe_url = urlunparse(parsed._replace(query=""))
    source_kind = payload.get("source_kind", "other")
    if source_kind not in SOURCE_KINDS:
        raise KnowledgeError(f"unsupported source_kind: {source_kind}")

    provider = payload["provider"].strip().lower()
    repository = payload.get("repository", "").strip().lower()
    source_id = payload["source_id"].strip()
    source_identity = ":".join((provider, repository, source_id))
    if len(source_identity) > 512:
        raise KnowledgeError("provider/repository/source identity exceeds 512 characters")
    digest = hashlib.sha256(payload["body"].encode("utf-8")).hexdigest()
    signal_id = "sig-" + hashlib.sha256((source_identity + ":" + digest).encode("utf-8")).hexdigest()[:24]
    captured_at = utc_now()
    excerpt = redact_excerpt(payload["body"])
    source = {
        "kind": source_kind,
        "uri": safe_url,
        "repository": payload.get("repository", ""),
        "pr_number": payload.get("pr_number"),
        "issue_number": payload.get("issue_number"),
        "run_id": payload.get("run_id"),
        "commit_sha": payload.get("commit_sha"),
        "captured_at": captured_at,
        "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
    }
    source = {key: value for key, value in source.items() if value is not None and value != ""}
    record = {
        "schema_version": 1,
        "id": signal_id,
        "type": "signal",
        "project_id": payload["project_id"],
        "title": payload["title"][:240],
        "summary": excerpt,
        "assessment": "observed",
        "lifecycle": "untriaged",
        "approval": "not_required",
        "created_at": captured_at,
        "updated_at": captured_at,
        "actor": "intake:" + provider[:80],
        "provider": provider[:80],
        "source_identity": source_identity,
        "payload_digest": digest,
        "tags": payload.get("tags", []) if isinstance(payload.get("tags", []), list) else [],
        "sources": [source],
        "relations": [],
    }
    errors = schema_errors(record, load_schema(RECORD_SCHEMA))
    if errors:
        raise KnowledgeError("intake record does not satisfy the knowledge schema: " + "; ".join(errors))

    target = KNOWLEDGE / "inbox" / f"{signal_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        existing = read_json(target)
        if existing.get("payload_digest") == digest and existing.get("source_identity") == source_identity:
            return "duplicate", target
        raise KnowledgeError("existing Signal snapshot failed integrity comparison; do not overwrite it")
    target.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return "created", target


def validate_receipts() -> list[dict[str, str]]:
    schema = load_schema(RECEIPT_SCHEMA)
    directory = KNOWLEDGE / "execution-receipts"
    if not directory.exists():
        return []
    errors: list[dict[str, str]] = []
    for path in sorted(directory.rglob("*.json")):
        receipt = read_json(path)
        for message in schema_errors(receipt, schema):
            errors.append({"path": path.relative_to(ROOT).as_posix(), "error": message})
        if receipt.get("status") in {"verified", "merged", "deployed"}:
            tested_sha = receipt.get("tested_sha")
            if not tested_sha:
                errors.append({"path": path.relative_to(ROOT).as_posix(), "error": "verified/merged/deployed receipt requires tested_sha"})
            successful = [
                check for check in receipt.get("checks", [])
                if check.get("status") == "success" and check.get("tested_sha") == tested_sha
            ]
            if not successful:
                errors.append({"path": path.relative_to(ROOT).as_posix(), "error": "no successful check is tied to receipt tested_sha"})
        if receipt.get("status") in {"merged", "deployed"} and not receipt.get("target_sha"):
            errors.append({"path": path.relative_to(ROOT).as_posix(), "error": "merged/deployed receipt requires target_sha"})
        if receipt.get("tier") in {"T2", "T3"}:
            goldfish = [
                review for review in receipt.get("reviews", [])
                if "goldfish" in review.get("role", "").lower() and review.get("status") == "completed" and review.get("independence_proof")
            ]
            if not goldfish:
                errors.append({"path": path.relative_to(ROOT).as_posix(), "error": "T2/T3 receipt requires completed Goldfish review with independence evidence"})
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate schemas, records and relations")
    sub.add_parser("validate-receipts", help="validate execution receipts and SHA-bound proof")
    index_parser = sub.add_parser("index", help="generate or check the deterministic index")
    index_parser.add_argument("--check", action="store_true")
    search_parser = sub.add_parser("retrieve", help="retrieve relevant approved knowledge")
    search_parser.add_argument("query")
    search_parser.add_argument("--project")
    search_parser.add_argument("--limit", type=int, default=12)
    intake_parser = sub.add_parser("intake", help="ingest one untrusted source event from JSON")
    intake_parser.add_argument("--file", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command in {"validate", "validate-receipts"}:
            errors = validate_all() if args.command == "validate" else validate_receipts()
            if errors:
                print(json.dumps(errors, indent=2, ensure_ascii=False), file=sys.stderr)
                return 1
            print("Knowledge validation: PASS" if args.command == "validate" else "Execution receipt validation: PASS")
            return 0
        if args.command == "index":
            if args.check:
                if not write_index(check=True):
                    print("knowledge/index.json is missing or stale", file=sys.stderr)
                    return 1
                print("Knowledge index is current: PASS")
            else:
                write_index()
                print("Generated knowledge/index.json")
            return 0
        if args.command == "retrieve":
            matches = retrieve(args.query, args.project, args.limit)
            print(json.dumps({"query": args.query, "count": len(matches), "matches": matches}, indent=2, ensure_ascii=False))
            return 0
        if args.command == "intake":
            payload = json.loads(args.file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise KnowledgeError("intake input must be a JSON object")
            outcome, path = receive_signal(payload)
            print(json.dumps({"outcome": outcome, "path": path.relative_to(ROOT).as_posix()}))
            return 0
    except (KnowledgeError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
