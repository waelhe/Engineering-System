# Cross-Repository GitHub Review Intake

**Status:** Proposed; fresh-context EGM review and human approval are pending.  
**Implementation status:** Not implemented. The existing same-repository collector remains the only active path.  
**Target destination:** `waelhe/Engineering-System`, the canonical EGM knowledge store.

## Problem and observed boundary

The current collector obtains `GITHUB_REPOSITORY` and `GITHUB_TOKEN` from the repository hosting the workflow. It uses that same repository identity for PR discovery, review/comment retrieval, publishing the data-only intake branch, opening the draft intake PR, and dispatching trusted validation.

This works for reviews in `waelhe/Engineering-System`, but it does not collect source reviews from the other platform repositories. GitHub documents that a workflow's `GITHUB_TOKEN` is scoped to the repository containing the workflow; cross-repository access requires a separately authorized credential. The existing collector must not silently broaden the destination token.

The source repositories observed through the GitHub API on 2026-11-22 are:

| Repository | Visibility | Default branch | Observed main SHA | Source profile |
|---|---|---|---|---|
| `waelhe/app-java-v3` | Public | `main` | `8ab2c667aef190b58d88cb116d8ce004bf948cf9` | `knowledge/projects/app-java-v3.json` exists |
| `waelhe/marketplace-admin` | Public | `main` | `982ecf3667d2242cab941737cb6a0bceaee7ffcb` | Missing; must be added as a candidate profile |
| `waelhe/mobile-marketplace` | Private | `main` | `3e2357ac3f5ed00cfffc51b2909c60f9f214f1f4` | Missing; must be added as a candidate profile |

These SHAs are dated repository observations, not live references or capability/readiness claims. The Android client is private; its inclusion requires explicit GitHub App installation access.

## Goals

1. Read PR reviews, PR review comments and issue-level PR comments from an explicit repository allowlist.
2. Preserve each source repository's project identity and map every source observation to an existing canonical project profile.
3. Write only generated Signal JSON and the deterministic index into the destination EGM repository.
4. Keep source access read-only and destination publication permissions separate.
5. Retain pagination, immutable snapshot deduplication, source redaction, append-only validation and the trusted workflow-dispatch boundary already implemented.

## Proposed trust and permission model

### Two distinct tokens

**Source token — GitHub App installation token**

- Create it in the trusted collector job only when the external-source integration is explicitly enabled.
- Restrict its installation to the three listed repositories; do not request access to all repositories owned by `waelhe`.
- Request only repository permissions required by the current read API calls:
  - `pull-requests: read` for listing PRs, reviews and PR review comments.
  - `issues: read` for issue-level comments attached to PRs.
- Do not request `contents`, `actions`, `checks`, `statuses`, `workflows`, or any write permission for source repositories.
- Use the official `actions/create-github-app-token` action pinned to the immutable v3.4.0 release commit `f418cff399f7aef4c2f0ad47e25ca7a6abbdd6fc`. GitHub's release API reports that commit's signature as verified and the release as immutable (published 2026-11-18).
- The installation token is short-lived (one hour) and the action revokes it in its post step unless configured otherwise. Do not persist it, store it in repository files, or pass it to subprocesses.

**Destination token — existing Actions GITHUB_TOKEN**

- Keep it scoped to `waelhe/Engineering-System`.
- Use it only to read trusted destination state, create the generated intake branch, push the generated data, open the draft intake PR, and dispatch trusted validation.
- Do not pass it to source-repository requests.
- Do not allow the source token to push branches, create PRs, dispatch workflows, merge, change repository settings or deploy.

The Python collector must receive distinct `source_token` and `destination_token` arguments. Source API functions must use only the former; branch preparation, publication, PR creation and validation dispatch must use only the latter. Tests must assert this separation, not merely that a token exists.

### Source registry and project profiles

Add a versioned, schema-validated registry under `registry/` with one entry per allowed source:

- `repository`
- `project_id`
- `expected_default_branch`
- `enabled`
- `capture_mode` (initially scheduled/manual sweep)
- `observed_main_sha` and `observed_at` as provenance only

Validation must fail closed when a repository is duplicated, a project ID is unknown, the project profile does not list that repository, or the live repository identity/default branch does not match the configured mapping. The two missing profiles must be minimal candidate profiles with empty module maps and no inferred technology or domain capabilities. They exist to establish project identity for intake, not to certify feature completeness.

### Capture mode

Version 1 should use the existing scheduled and manual sweep to discover recent PRs in each configured source repository. The current `workflow_run` event is generated by the destination repository's capture workflow; it must not be treated as proof of an event in another repository.

If event-driven capture is later required, install a separate zero-permission capture workflow in each source repository and verify its exact workflow ID, path, allowed event, conclusion and source repository before the trusted collector reads current API state. Never trust caller-supplied event bodies or workflow metadata as authorization evidence.

## Processing sequence

1. Load and validate the checked-in repository registry and project profiles from the trusted destination default branch.
2. Validate the exact configured source repository set against the App token's repository allowlist.
3. For each enabled repository, re-fetch repository metadata and confirm its default branch and full repository identity.
4. Discover recent open PRs with bounded time and per-repository count limits; paginate all review/comment endpoints.
5. Convert source objects into redacted, immutable Signals using the existing project-scoped source identity and payload digest.
6. Preserve partial failures explicitly. If a configured source cannot be read or validated, do not publish a batch that silently omits it.
7. Rebuild the index and run knowledge, migration, receipt and append-only validation from trusted destination code.
8. Stage only `knowledge/inbox/*.json` and `knowledge/index.json`; do not checkout or execute source repository branches.
9. Use the destination token to publish the data-only draft PR and dispatch trusted validation against the exact returned head ref and SHA.
10. Require ordinary human review and repository protections. Never auto-promote Signals to Findings or merge the intake PR.

## Failure and rollback behavior

- Missing App configuration: keep the existing same-repository mode; report external intake as disabled, not successful.
- App enabled but installation, repository access, profile mapping or API request fails: abort the external batch and report the exact source that failed. Do not publish a partial batch as complete.
- Token or repository scope broader than the explicit allowlist: fail closed.
- Duplicate source snapshot: retain idempotent behavior; changed body creates a new immutable snapshot.
- Validation or publication failure: leave existing knowledge records unchanged; do not merge, deploy, or modify source repositories.

## Acceptance criteria before implementation is enabled

- Schema and deterministic validator cover the registry and each project/repository mapping.
- Tests prove source and destination tokens are never interchanged and that the source token cannot be used by Git push, PR creation or workflow dispatch.
- Tests cover private-repository denial, wrong repository identity, default-branch drift, pagination, per-source partial failure, duplicate snapshots and empty sweeps.
- The collector verifies the actual repository set against the intended App installation scope; no wildcard/all-repository token is used.
- The existing same-repository collector remains covered by its end-to-end test.
- A trusted CI run on the exact implementation SHA passes knowledge, migration, receipt, index, append-only, tests and both package builds.
- A real end-to-end test is run only after the App is installed and configured; evidence records the exact source repos and SHA values. No private key or installation token is recorded.
- A fresh-context EGM design review and human approval occur before source-code or workflow changes.

## Required external setup (not performed by this proposal)

A repository owner must create/register the GitHub App, grant the two read-only repository permissions, install it only on the approved source repositories, and configure the App Client ID as an Actions variable and the private key as an Actions secret. This proposal does not create credentials, install the App, change repository settings, or enable the feature.

## Review gate

The existing EGM policy requires a genuine fresh-context Goldfish review for T2 security/architecture work and a human decision at the permission boundary. The current execution environment exposes no native fresh-subagent spawn/wait tool, so that review is **not run** here. Same-context critique, successful CI, and this proposal are not substitutes for the required review. Implementation remains blocked until the fresh-context and human approval evidence is available.

## Official references

- [GitHub: GITHUB_TOKEN scope and cross-repository limitations](https://docs.github.com/en/actions/concepts/security/compromised-runners)
- [GitHub: List reviews for a pull request — Pull requests: read](https://docs.github.com/en/rest/pulls/reviews)
- [GitHub: Review comments — Pull requests: read](https://docs.github.com/en/rest/pulls/comments)
- [GitHub: Choosing permissions for a GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app)
- [actions/create-github-app-token v3.4.0](https://github.com/actions/create-github-app-token/releases/tag/v3.4.0)
