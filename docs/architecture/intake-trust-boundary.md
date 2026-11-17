# GitHub Review Intake Trust Boundary

## Security invariant

The privileged collector executes only code from the trusted default-branch revision. Review bodies, issue comments, PR heads and automation branch contents are untrusted data. They may be parsed, bounded, redacted and stored, but must never supply executable code to a job holding a write-capable token.

This is especially important for `workflow_run`: the collector has permissions unavailable to the low-privilege capture workflow. It checks out the repository default branch and verifies the originating capture workflow through the GitHub API before collecting review data.

## Processing sequence

1. The capture workflow has no repository permissions and emits only a completion signal.
2. The collector checks the workflow-run ID, workflow ID, workflow path, event type, successful conclusion and source repository.
3. The collector reads review/comment state through the GitHub API. Source bodies are untrusted payloads; intake redacts the complete body before truncation and stores immutable snapshots.
4. Validation, indexing and tests run from the checked-out trusted default-branch worktree. Child processes do not inherit GitHub Actions token environment variables.
5. Each run creates a new `automation/knowledge-intake-<run-id>-<attempt>` branch from the fetched trusted default branch. The collector never fetches, checks out, merges or reuses a user-writable intake PR branch.
6. Only generated `knowledge/inbox` records and the deterministic knowledge index are committed. The collector opens a draft PR; it never merges that PR.
7. Immediately after creating the draft PR, the collector dispatches `knowledge-validation.yml` on the trusted default branch. It passes the PR number, exact head ref, exact 40-character head SHA and base ref returned by GitHub when the PR was created.
8. The dispatched workflow runs trusted default-branch code. `tools/validate_intake_pr.py` fetches the pinned refs as Git objects without checking out or executing the intake branch; verifies the head SHA has not changed; permits only new Signal JSON files and the generated index; rejects executable files and symlinks; validates Signal state, identity and source provenance; and invokes `knowledge_guard.validate_changes(base, head)` to enforce append-only history against the branch point. It materializes only the validated Signal JSON and index as data, then runs knowledge/schema validation, migration reconciliation, receipt validation, index freshness, tests and both runtime package builds.
9. The separate `pull_request` workflow also validates the PR branch and runs the append-only guard. Because the collector creates the PR with `GITHUB_TOKEN`, GitHub places the `opened`, `synchronize` or `reopened` workflow run in an approval-required state. A user with write access must select **Approve workflows to run** before that PR-triggered run can proceed.

## Two distinct validation results

The trusted `workflow_dispatch` run validates the exact intake head using trusted code and includes the append-only guard. Its run is associated with the trusted default-branch ref, not the intake PR head; therefore it is evidence for the candidate, not a substitute for the PR's own required status checks.

The PR's normal `pull_request` validation run is associated with the PR and remains subject to GitHub's approval control for workflows initiated by `GITHUB_TOKEN`. A green dispatched run must not be treated as approval of the PR, a required PR check, or authorization to merge. Review and merge remain subject to normal repository protections and human approval.

Official platform behavior:
- [GITHUB_TOKEN workflow-trigger behavior](https://docs.github.com/en/actions/concepts/security/github_token#when-github_token-triggers-workflow-runs)
- [Events that trigger workflows — workflow_dispatch](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch)

## Permissions

The collector requires:
- `actions: write` to dispatch the trusted intake-validation workflow;
- `contents: write` to publish the generated branch;
- `pull-requests: write` to open a draft PR;
- `issues: read` to retrieve issue-comment events.

The collector does not receive permission to approve workflow runs, merge pull requests, or modify repository settings. The dispatched validation job runs from the trusted default branch with read-only repository contents permission.

## Operational constraints

- The collector never auto-merges.
- An intake Signal is not a Finding, Pattern, Rule, Control or closure.
- Snapshot identity includes the source payload digest; changed content becomes a new immutable Signal.
- A failed trust check aborts collection. Caller-supplied workflow metadata is never trusted as a fallback.
- Existing intake PR branches are never merged into the privileged collector worktree.
