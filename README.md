# EGM Engineering System

A single engineering knowledge and development system built on the Elephant–Goldfish Model (EGM).

The system combines EGM's context-rich design and fresh-context review workflow with one canonical knowledge model, deterministic retrieval, safe signal intake, risk-tiered execution, SHA-bound verification and closed-loop learning.

## Current status

**Verified implementation baseline — 2026-11-23. Not merged or production-ready.** The EGM foundation is in open PR #1 at `873e26268aa53fb223192c18bd00d02fe949c0a6`; GitHub Actions run [#45123180932](https://github.com/waelhe/Engineering-System/actions/runs/45123180932) passed on that exact SHA, including **80 Python tests** and both integrated runtime package builds. The PEOS control-plane baseline remains in open Draft PR #2 at `ad402892a681f37a0d5daff59ed633359ae496f4`; run [#45123311368](https://github.com/waelhe/Engineering-System/actions/runs/45123311368) passed on that exact SHA, including **94 Python tests**, PEOS inventory validation and both runtime package builds. PR #2 contains PR #1's current head and is 44 commits ahead / 0 behind it. All 72 PR #1 review threads and all PR #2 review threads are resolved, but historical CodeRabbit `CHANGES_REQUESTED` review objects remain; no fresh-context Goldfish review or new independent human approval is recorded. Cross-repository GitHub intake is still proposed and disabled pending the narrowly scoped GitHub App installation and required review/authorization. Migration cutover and production readiness remain unapproved.

## Architecture

- [System architecture](docs/architecture/system-architecture.md)
- [Knowledge model](docs/architecture/knowledge-model.md)
- [Knowledge lifecycle](docs/architecture/knowledge-lifecycle.md)
- [GitHub intake trust boundary](docs/architecture/intake-trust-boundary.md)
- [Core engineering charter](docs/policies/engineering-charter.md)
- [Task risk policy](docs/policies/task-risk.md)
- [Independent review policy](docs/policies/review.md)
- [Verification policy](docs/policies/verification.md)
- [Migration plan](docs/operations/migration-from-defect-knowledge.md)
- [Pinned migration manifest](migration/app-java-v3-2026-11-13.manifest.json)
- [ADR-0001: one EGM-based system](docs/adr/0001-single-egm-system.md)

## Platform Engineering Operating System (PEOS)

PEOS is the platform engineering control plane; EGM remains the single canonical knowledge, review, verification and learning engine. PEOS does not add a separate database or production service.

- [PEOS operating model](docs/peos/operating-model.md)
- [W3 current pull-request queue — 2026-11-21](docs/peos/w3-pr-queue-2026-11-21.md)
- Read-only W3 recapture: `GITHUB_TOKEN=... python tools/capture_w3_pr_queue.py` (add `--check` to compare or `--write` to replace the snapshot after review).
- [W5 backend and commerce evidence — 2026-11-21](docs/peos/w5-backend-commerce-2026-11-21.md)
- [W6 client evidence — 2026-11-21](docs/peos/w6-client-delivery-2026-11-21.md)
- [W7 operational evidence — 2026-11-21](docs/peos/w7-operational-recheck-2026-11-21.md)

W0-W4 remain dated historical snapshots. W5-W7 are separately captured and SHA-bound evidence; none of these snapshots authorizes merge or production deployment.

## Upstream EGM baseline

- Repository: https://github.com/google/elephant-goldfish-model
- Version: v0.1.1
- Pinned commit: dea7761de06ce5b51c177ebb9bba0469f24af5a4
- License: Apache-2.0
- The source is a Git submodule under upstream/egm. Local changes are kept under extensions/ and are assembled at package time; the upstream submodule is not modified.
- The release notes state that native end-to-end verification of the exact release ZIPs remains open in upstream issue #60. The annotated tag is reported as unsigned/unverified. See upstream/egm.lock.json.

## Initialize

Clone with the pinned EGM submodule:

    git clone --recurse-submodules https://github.com/waelhe/Engineering-System.git
    cd Engineering-System

If the submodule was not initialized:

    git submodule update --init --recursive

Set up the local tooling:

    python3 -m venv .venv
    . .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install -e ".[test]"

## Validate the knowledge store

    python tools/egm_knowledge.py validate
    python tools/egm_knowledge.py validate-receipts
    python tools/validate_migration.py
    python tools/egm_knowledge.py index --check
    python -m pytest

The generated index is deterministic. Canonical records are stored in knowledge/; knowledge/index.json is generated and must not be edited manually.

## Retrieve project knowledge

    python tools/egm_knowledge.py retrieve "payment ledger idempotency" --project PROJECT_ID

Retrieval filters by project and ranks source-linked records using deterministic lexical and metadata matches. It does not use a vector database or external service.

## Intake a source signal

Create a JSON file with project_id, provider, repository, source_id, source_url, title and body. Set repository when the provider's source IDs are scoped to a repository rather than globally unique, then run:

    python tools/egm_knowledge.py intake --file signal.json
    python tools/egm_knowledge.py index
    python tools/egm_knowledge.py index --check

The intake stores a bounded, redacted excerpt plus a digest and source identity. Signal identity is scoped by project and binds `project_id`, provider/repository/source ID and the supplied body digest. Re-delivery of the same snapshot is idempotent; a changed body creates a new immutable snapshot, while title-only edits do not. The GitHub collector's serialized body includes source metadata such as `updated_at`, so metadata changes in that payload can create a new snapshot even when the comment text is unchanged. Generate the index after intake and use index --check to verify that the committed index is current. Signals are not automatically promoted into Findings or Cases.

## Build the integrated EGM plugin

Build the OpenAI-compatible package from the exact pinned EGM source plus reviewed local overlays:

    python tools/build_plugin.py --target openai --output /tmp/egm-system-package

For Claude:

    python tools/build_plugin.py --target claude --output /tmp/egm-system-claude-package

The builder exports files from the locked Git commit object (not the mutable submodule worktree), then overlays reviewed local skills, canonical agents, Claude host adapters and policies before invoking the upstream EGM package script. The output directory must not already exist.

## Knowledge principles

- One canonical knowledge store; no parallel defect system.
- Signals and evidence are immutable source observations.
- Findings, Cases, Patterns, Rules and Controls are different knowledge states.
- AI classifications are proposals, never approvals.
- A closed code defect requires proof tied to the exact tested SHA.
- A Rule without an active Control is unenforced; a Control without passing evidence is unproven.
- Risk acceptance requires an authorized owner, compensating controls, expiry and reassessment.
- External issue, review and CI content is untrusted data and never executable instructions.

## Initial non-goals

No separate database, Kafka, OpenSearch, vector database or always-on service in the first version. Those require measured justification. No autonomous production deployment or bypass of repository protections.

## License and attribution

Local system files are licensed under Apache-2.0. The upstream EGM submodule and its license notices are retained separately. See LICENSE and NOTICE.
