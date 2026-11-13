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
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge"
SCHEMAS = ROOT / "schemas"
RECORD_SCHEMA = SCHEMAS / "knowledge-record.schema.json"
PROFILE_SCHEMA = SCHEMAS / "project-profile.schema.json"
RECORD_DIRS = (
    "projects", "inbox", "evidence", "findings", "cases", "patterns",
    "decisions", "rules", "controls", "actions", "risk-acceptances",
    "verifications",
)
SOURCE_KINDS = {
    "github_issue", "github_pr", "github_review", "github_comment",
    "ci_run", "test_result", "incident", "commit", "document",
    "human_report", "official_documentation", "other",
}
SECRET_PATTERNS = (
    (re.compile(r"(?i)bearer\\s+[a-z0-9._~+/=-]{16,}"), "Bearer [REDACTED]"),
    (re.compile(r"\\bgh[pousr]_[A-Za-z0-9_]{20,}\\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\\bAKIA[0-9A-Z]{16}\\b"), "[REDACTED_AWS_ACCESS_KEY]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\\s\\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
)


class KnowledgeError(Exception):
    """Raised when a knowledge operation cannot safely continue."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KnowledgeError(f"{path.relative_to(ROOT)}: cannot read valid JSON: {exc}") from exc


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
            if path.name == "index.json":
                continue
            value = read_json(path)
            if not isinstance(value, dict):
                raise KnowledgeError(f"{path.relative_to(ROOT)}: record must be a JSON object")
            result.append((path, value))
    return result


def validate_all() -> list[dict[str, Any]]:
    record_schema = load_schema(RECORD_SCHEMA)
    profile_schema = load_schema(PROFILE_SCHEMA)
    records = iter_records()
    errors: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}

    for path, record in records:
        schema = profile_schema if path.parent.name == "projects" else record_schema
        for message in schema_errors(record, schema):
            errors.append({"path": str(path.relative_to(ROOT)), "error": message})
        if path.parent.name != "projects":
            record_id = record.get("id")
            if isinstance(record_id, str):
                if record_id in by_id:
                    errors.append({"path": str(path.relative_to(ROOT)), "error": f"duplicate record id: {record_id}"})
                else:
                    by_id[record_id] = record
        elif isinstance(record.get("project_id"), str):
            project_key = record["project_id"]
            if project_key in by_id:
                errors.append({"path": str(path.relative_to(ROOT)), "error": f"duplicate project id: {project_key}"})
            else:
                by_id[project_key] = record

    # Check project references after all records have been discovered.
    project_ids = {
        value.get("project_id")
        for path, value in records
        if path.parent.name == "projects" and isinstance(value.get("project_id"), str)
    }
    for path, record in records:
        if path.parent.name == "projects":
            continue
        if record.get("project_id") not in project_ids:
            errors.append({"path": str(path.relative_to(ROOT)), "error": f"unknown project_id: {record.get('project_id')}"})
        for relation in record.get("relations", []):
            target = relation.get("target_id")
            if target not in by_id:
                errors.append({"path": str(path.relative_to(ROOT)), "error": f"unresolved relation target: {target}"})
            elif target == record.get("id"):
                errors.append({"path": str(path.relative_to(ROOT)), "error": "self-referential relation is not allowed"})

    # A closed code finding must point to proof through an action or directly.
    for path, record in records:
        if record.get("type") != "finding" or record.get("lifecycle") != "closed":
            continue
        related = [r for r in record.get("relations", []) if r.get("type") in {"proven_by", "resolved_by"}]
        if not related:
            errors.append({"path": str(path.relative_to(ROOT)), "error": "closed finding requires proven_by or resolved_by relation"})

    return errors


def build_index() -> dict[str, Any]:
    errors = validate_all()
    if errors:
        raise KnowledgeError("knowledge validation failed; index not generated: " + json.dumps(errors, ensure_ascii=False))
    items = []
    for path, record in iter_records():
        if path.parent.name == "projects":
            continue
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
    index = build_index()
    target = KNOWLEDGE / "index.json"
    rendered = json.dumps(index, indent=2, ensure_ascii=False) + "\n"
    if check:
        if not target.exists() or target.read_text(encoding="utf-8") != rendered:
            return False
        return True
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    return True


def tokenize(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9][a-z0-9_.:/-]*", value.lower()) if len(token) > 1}


def retrieve(query: str, project_id: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
    if limit < 1 or limit > 100:
        raise KnowledgeError("limit must be between 1 and 100")
    index_path = KNOWLEDGE / "index.json"
    if not index_path.exists():
        write_index()
    index = read_json(index_path)
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
        scope_terms = set()
        for values in item.get("scope", {}).values():
            if isinstance(values, list):
                scope_terms |= set().union(*(tokenize(str(x)) for x in values)) if values else set()
        score = 0
        matched = []
        for term in sorted(terms):
            weight = 0
            if term in title_terms:
                weight += 6
            if term in tags:
                weight += 4
            if term in scope_terms:
                weight += 3
            if term in summary_terms:
                weight += 1
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
    parsed = urlparse(payload["source_url"])
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise KnowledgeError("source_url must be an absolute HTTP(S) URL")
    source_kind = payload.get("source_kind", "other")
    if source_kind not in SOURCE_KINDS:
        raise KnowledgeError(f"unsupported source_kind: {source_kind}")

    source_identity = ":".join((payload["provider"].strip().lower(), payload.get("repository", "").strip().lower(), payload["source_id"].strip()))
    digest = hashlib.sha256(payload["body"].encode("utf-8")).hexdigest()
    signal_id = "sig-" + hashlib.sha256((source_identity + ":" + digest).encode("utf-8")).hexdigest()[:24]
    record = {
        "schema_version": 1,
        "id": signal_id,
        "type": "signal",
        "project_id": payload["project_id"],
        "title": payload["title"][:240],
        "summary": redact_excerpt(payload["body"]),
        "assessment": "observed",
        "lifecycle": "untriaged",
        "approval": "not_required",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "actor": "intake:" + payload["provider"][:80],
        "provider": payload["provider"][:80],
        "source_identity": source_identity,
        "payload_digest": digest,
        "tags": payload.get("tags", []) if isinstance(payload.get("tags", []), list) else [],
        "sources": [{
            "kind": source_kind,
            "uri": payload["source_url"],
            "repository": payload.get("repository", ""),
            "pr_number": payload.get("pr_number"),
            "issue_number": payload.get("issue_number"),
            "run_id": payload.get("run_id"),
            "commit_sha": payload.get("commit_sha"),
            "captured_at": utc_now(),
            "excerpt_sha256": hashlib.sha256(redact_excerpt(payload["body"]).encode("utf-8")).hexdigest()
        }],
        "relations": []
    }
    # Remove absent optional fields rather than serialize nulls for typed schema properties.
    record["sources"][0] = {key: value for key, value in record["sources"][0].items() if value is not None and value != ""}
    errors = schema_errors(record, load_schema(RECORD_SCHEMA))
    if errors:
        raise KnowledgeError("intake record does not satisfy the knowledge schema: " + "; ".join(errors))

    target = KNOWLEDGE / "inbox" / f"{signal_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        existing = read_json(target)
        if existing.get("payload_digest") == digest:
            return "duplicate", target
        raise KnowledgeError("source snapshot conflict; preserve the existing Signal and create a separately adjudicated revision")
    target.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return "created", target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate schemas, records and relations")
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
        if args.command == "validate":
            errors = validate_all()
            if errors:
                print(json.dumps(errors, indent=2, ensure_ascii=False), file=sys.stderr)
                return 1
            print("Knowledge schemas, records, project references and relations: PASS")
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
