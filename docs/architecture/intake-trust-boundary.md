# GitHub Review Intake Trust Boundary

## Security invariant

The privileged collector executes only code from the trusted default-branch revision. Review bodies, issue comments, PR heads and automation branch contents are untrusted data. They may be parsed, bounded, redacted and stored, but must never supply executable code to a job holding a write-capable token.

This is especially important for \`workflow_run\`: the collector has permissions unavailable to the low-privilege capture workflow. It checks out the repository default branch and verifies the originating capture workflow through the GitHub API before collecting review data.

## Processing sequence

1. The capture workflow has no repository permissions and emits only a completion signal.
2. The collector checks the workflow-run ID, workflow ID, workflow path, event type, successful conclusion and source repository.
3. The collector reads review/comment state through the GitHub API. Source bodies are untrusted payloads; intake redacts the complete body before truncation and stores immutable snapshots.
4. Validation, indexing and tests run from the checked-out trusted default-branch worktree. Child processes do not inherit GitHub Actions token environment variables.
5. Each run creates a new \`automation/knowledge-intake-<run-id>-<attempt>\` branch from the fetched trusted default branch. The collector never fetches, checks out, merges or reuses a user-writable intake PR branch.
6. Only generated \`knowledge/inbox\` records and the deterministic knowledge index are committed. The collector opens a draft PR; ordinary \`pull_request\` CI validates it and a human reviews/merges it.

## Permissions

The collector requires:
- \`contents: write\` to publish the generated branch;
- \`pull-requests: write\` to open a draft PR;
- \`issues: read\` to retrieve issue-comment events.

It does not dispatch a workflow through the Actions API. The draft PR triggers the existing \`pull_request\` validation workflow, so \`actions: write\` is unnecessary and is not granted.

## Operational constraints

- The collector never auto-merges.
- An intake Signal is not a Finding, Pattern, Rule, Control or closure.
- Snapshot identity includes the source payload digest; changed content becomes a new immutable Signal.
- A failed trust check aborts collection. Caller-supplied workflow metadata is never trusted as a fallback.
- Existing intake PR branches are never merged into the privileged collector worktree.
