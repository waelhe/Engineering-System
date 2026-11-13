#!/usr/bin/env python3
"""Safely synchronize GitHub PR reviews/comments into the EGM Signal inbox."""

from __future__ import annotations
import argparse, json, os, subprocess, sys, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from tools.egm_knowledge import KnowledgeError, receive_signal

API = "https://api.github.com"
API_VERSION = "2022-11-28"
CAPTURE_WORKFLOW = "Review Signal Capture"
MAX_SOURCE_BODY = 250_000

class IntakeError(Exception):
    pass

def api_request(method: str, path: str, token: str, payload: dict[str, Any] | None = None) -> Any:
    url = path if path.startswith("https://") else API + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION, "User-Agent": "egm-engineering-knowledge-intake",
        **({"Content-Type": "application/json"} if data is not None else {}),
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read(2000).decode("utf-8", errors="replace")
        raise IntakeError(f"GitHub API {method} {url} returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise IntakeError(f"GitHub API request failed for {url}: {exc}") from exc

def api_pages(path: str, token: str) -> list[dict[str, Any]]:
    """Fetch every REST page; default page-size is not a complete snapshot."""
    result: list[dict[str, Any]] = []
    page = 1
    while True:
        separator = "&" if "?" in path else "?"
        batch = api_request("GET", f"{path}{separator}per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise IntakeError(f"Expected paginated array from {path}")
        result.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < 100:
            return result
        page += 1
        if page > 100:
            raise IntakeError(f"Pagination safety limit reached for {path}")

def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *args], check=False, capture_output=True, text=True)
    if check and result.returncode:
        raise IntakeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result

def read_event(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntakeError(f"Cannot read GitHub event payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise IntakeError("GitHub event payload must be an object")
    return payload

def recent_open_prs(repo: str, token: str, since_days: int, maximum: int) -> list[int]:
    if not 1 <= since_days <= 90:
        raise IntakeError("since_days must be between 1 and 90")
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    pulls = api_pages(f"/repos/{repo}/pulls?state=open&sort=updated&direction=desc", token)
    selected = []
    for pull in pulls:
        try:
            updated = datetime.fromisoformat(str(pull.get("updated_at")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if updated < cutoff:
            break
        if isinstance(pull.get("number"), int):
            selected.append(pull["number"])
        if len(selected) >= maximum:
            break
    return selected

def resolve_pr_numbers(repo: str, token: str, event_name: str, payload: dict[str, Any],
                       explicit_pr: int | None, since_days: int, maximum: int) -> list[int]:
    if explicit_pr is not None:
        if explicit_pr < 1:
            raise IntakeError("PR number must be positive")
        pr = api_request("GET", f"/repos/{repo}/pulls/{explicit_pr}", token)
        if pr.get("base", {}).get("repo", {}).get("full_name", "").lower() != repo.lower():
            raise IntakeError("PR base repository does not match configured repository")
        return [explicit_pr]
    if event_name == "workflow_run":
        run_id = (payload.get("workflow_run") or {}).get("id")
        if not isinstance(run_id, int):
            raise IntakeError("workflow_run event has no run ID")
        run = api_request("GET", f"/repos/{repo}/actions/runs/{run_id}", token)
        if run.get("name") != CAPTURE_WORKFLOW:
            raise IntakeError("workflow_run did not originate from trusted review-capture workflow")
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            raise IntakeError("capture workflow did not complete successfully")
        if run.get("repository", {}).get("full_name", "").lower() != repo.lower():
            raise IntakeError("capture workflow belongs to another repository")
        numbers = [x["number"] for x in run.get("pull_requests", [])
                   if isinstance(x, dict) and isinstance(x.get("number"), int)]
        return sorted(set(numbers)) if numbers else recent_open_prs(repo, token, min(since_days, 7), maximum)
    if event_name in {"schedule", "workflow_dispatch"}:
        return recent_open_prs(repo, token, since_days, maximum)
    raise IntakeError(f"Unsupported collector event: {event_name}")

def source_payload(repo: str, project_id: str, pr: dict[str, Any], item: dict[str, Any],
                   source_kind: str, event_action: str) -> dict[str, Any]:
    number = int(pr["number"])
    user = item.get("user") or {}
    login = str(user.get("login") or "unknown")
    created = item.get("submitted_at") or item.get("created_at") or datetime.now(timezone.utc).isoformat()
    updated = item.get("updated_at") or created
    if item.get("id") is None:
        raise IntakeError(f"GitHub {source_kind} object on PR #{number} has no stable ID")
    url = item.get("html_url") or f"https://github.com/{repo}/pull/{number}"
    commit_sha = item.get("commit_id")
    if not (isinstance(commit_sha, str) and len(commit_sha) == 40
            and all(c in "0123456789abcdef" for c in commit_sha)):
        commit_sha = None
    body_data = {
        "state": item.get("state"), "body": item.get("body") or "", "path": item.get("path"),
        "line": item.get("line"), "original_line": item.get("original_line"),
        "diff_hunk": item.get("diff_hunk"), "commit_id": commit_sha,
        "created_at": created, "updated_at": updated, "author_login": login,
        "author_association": item.get("author_association"),
    }
    body = json.dumps(body_data, ensure_ascii=False, separators=(",", ":"))
    if len(body) > MAX_SOURCE_BODY:
        body = body[:MAX_SOURCE_BODY] + " [source payload truncated by intake limit]"
    noun = "review" if source_kind == "github_review" else "review comment"
    return {
        "project_id": project_id, "provider": "github", "repository": repo,
        "source_id": f"{source_kind}-{item['id']}", "source_url": url, "source_kind": source_kind,
        "source_actor": login, "author_association": item.get("author_association"),
        "source_created_at": created, "source_updated_at": updated, "event_action": event_action,
        "commit_sha": commit_sha, "pr_number": number,
        "title": f"PR #{number} {noun} ({item.get('state') or 'comment'}) by {login}",
        "body": body, "tags": ["github", "review", "untrusted-source"],
    }

def collect_one_pr(repo: str, project_id: str, token: str, number: int,
                   event_action: str) -> dict[str, int]:
    pr = api_request("GET", f"/repos/{repo}/pulls/{number}", token)
    if pr.get("base", {}).get("repo", {}).get("full_name", "").lower() != repo.lower():
        raise IntakeError(f"PR #{number} is not based in {repo}")
    endpoints = (
        ("github_review", f"/repos/{repo}/pulls/{number}/reviews"),
        ("github_comment", f"/repos/{repo}/pulls/{number}/comments"),
        ("github_comment", f"/repos/{repo}/issues/{number}/comments"),
    )
    counts = {"created": 0, "duplicate": 0, "objects": 0}
    for kind, endpoint in endpoints:
        for item in api_pages(endpoint, token):
            outcome, _ = receive_signal(source_payload(repo, project_id, pr, item, kind, event_action))
            counts[outcome] = counts.get(outcome, 0) + 1
            counts["objects"] += 1
    return counts

def open_intake_prs(repo: str, token: str, base_branch: str) -> list[dict[str, Any]]:
    return [p for p in api_pages(f"/repos/{repo}/pulls?state=open&base={base_branch}", token)
            if str(p.get("head", {}).get("ref", "")).startswith("automation/knowledge-intake")
            and p.get("head", {}).get("repo", {}).get("full_name", "").lower() == repo.lower()]

def prepare_branch(repo: str, token: str, run_id: str) -> tuple[str, int | None, str]:
    repository = api_request("GET", f"/repos/{repo}", token)
    base_branch = repository.get("default_branch")
    if not isinstance(base_branch, str) or not base_branch:
        raise IntakeError("repository API did not return a default branch")
    git("fetch", "origin", base_branch, "--no-tags")
    existing = open_intake_prs(repo, token, base_branch)
    if existing:
        existing.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
        pr = existing[0]
        branch = pr["head"]["ref"]
        git("fetch", "origin", f"+refs/heads/{branch}:refs/remotes/origin/{branch}")
        git("checkout", "-B", branch, f"refs/remotes/origin/{branch}")
        git("merge", "--no-edit", f"refs/remotes/origin/{base_branch}")
        return branch, int(pr["number"]), base_branch
    suffix = "".join(c for c in run_id if c.isalnum() or c == "-")[:50] or "manual"
    branch = f"automation/knowledge-intake-{suffix}"
    git("checkout", "-B", branch, f"refs/remotes/origin/{base_branch}")
    return branch, None, base_branch

def publish_batch(repo: str, token: str, branch: str, existing_pr: int | None, base_branch: str) -> dict[str, Any] | None:
    git("add", "knowledge/inbox", "knowledge/index.json")
    staged = git("diff", "--cached", "--quiet", check=False)
    if staged.returncode == 0:
        return None
    if staged.returncode != 1:
        raise IntakeError(staged.stderr.strip() or "Cannot inspect staged intake changes")
    git("config", "user.name", "EGM Knowledge Intake Bot")
    git("config", "user.email", "egm-knowledge-intake@users.noreply.github.com")
    git("commit", "-m", "Capture trusted GitHub review signals")
    git("push", "--set-upstream", "origin", branch)
    if existing_pr:
        pr = api_request("GET", f"/repos/{repo}/pulls/{existing_pr}", token)
    else:
        pr = api_request("POST", f"/repos/{repo}/pulls", token, {
            "title": "Engineering knowledge intake sync", "head": branch, "base": base_branch,
            "body": ("## Automated intake batch\n\n"
                     "Source-linked GitHub reviews/comments are stored as untrusted Signals. "
                     "No Finding, Pattern, Rule or closure is auto-approved.\n\n"
                     "Review and merge only through normal protections. This bot never auto-merges."),
            "draft": True,
        })
    try:
        api_request("POST", f"/repos/{repo}/actions/workflows/knowledge-validation.yml/dispatches",
                    token, {"ref": branch})
        dispatch = "requested"
    except IntakeError as exc:
        dispatch = f"not_requested: {exc}"
    return {"number": pr.get("number"), "url": pr.get("html_url"), "branch": branch, "validation_dispatch": dispatch}

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-file", type=Path, required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--since-days", type=int, default=7)
    parser.add_argument("--max-prs", type=int, default=50)
    parser.add_argument("--project-id", default=os.environ.get("EGM_PROJECT_ID", "egm-engineering-system"))
    args = parser.parse_args(argv)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if "/" not in repo or not token:
        print("GITHUB_REPOSITORY and GITHUB_TOKEN are required", file=sys.stderr)
        return 2
    try:
        payload = read_event(args.event_file)
        numbers = resolve_pr_numbers(repo, token, args.event_name, payload,
                                     args.pr_number, args.since_days, args.max_prs)
        if not numbers:
            print(json.dumps({"message": "No recently updated PRs selected; no changes made."}))
            return 0
        branch, existing_pr, base_branch = prepare_branch(repo, token, args.run_id)
        totals = {"created": 0, "duplicate": 0, "objects": 0, "prs": 0}
        for number in numbers:
            counts = collect_one_pr(repo, args.project_id, token, number, args.event_name)
            totals["prs"] += 1
            for key in ("created", "duplicate", "objects"):
                totals[key] += counts[key]
        subprocess.run([sys.executable, "tools/egm_knowledge.py", "validate"], check=True)
        subprocess.run([sys.executable, "tools/egm_knowledge.py", "index"], check=True)
        subprocess.run([sys.executable, "tools/egm_knowledge.py", "validate-receipts"], check=True)
        subprocess.run([sys.executable, "-m", "pytest", "-q"], check=True)
        published = publish_batch(repo, token, branch, existing_pr, base_branch)
        print(json.dumps({"selected_prs": numbers, "totals": totals, "intake_pr": published}, ensure_ascii=False))
        return 0
    except (IntakeError, KnowledgeError, OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
