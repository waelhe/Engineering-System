# EGM Engineering System

A single engineering knowledge and development system built on the Elephant–Goldfish Model (EGM).

The system combines EGM's context-rich design and fresh-context review workflow with one canonical knowledge model, deterministic retrieval, safe signal intake, risk-tiered execution, SHA-bound verification and closed-loop learning.

## Current status

**Early implementation baseline. Not production-ready.** The repository has a pinned EGM submodule, initial architecture and governance policies, JSON Schemas, a knowledge CLI, local skills, and a CI workflow. Native harness and remote CI verification are still required before operational adoption.

## Architecture

- [System architecture](docs/architecture/system-architecture.md)
- [Knowledge model](docs/architecture/knowledge-model.md)
- [Knowledge lifecycle](docs/architecture/knowledge-lifecycle.md)
- [Core engineering charter](docs/policies/engineering-charter.md)
- [Task risk policy](docs/policies/task-risk.md)
- [Independent review policy](docs/policies/review.md)
- [Verification policy](docs/policies/verification.md)
- [Migration plan](docs/operations/migration-from-defect-knowledge.md)
- [ADR-0001: one EGM-based system](docs/adr/0001-single-egm-system.md)

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
    python tools/egm_knowledge.py index --check
    python -m pytest

The generated index is deterministic. Canonical records are stored in knowledge/; knowledge/index.json is generated and must not be edited manually.

## Retrieve project knowledge

    python tools/egm_knowledge.py retrieve "payment ledger idempotency" --project PROJECT_ID

Retrieval filters by project and ranks source-linked records using deterministic lexical and metadata matches. It does not use a vector database or external service.

## Intake a source signal

Create a JSON file with project_id, provider, source_id, source_url, title and body, then run:

    python tools/egm_knowledge.py intake --file signal.json

The intake stores a bounded, redacted excerpt plus a digest and source identity. Repeated delivery of the same payload is idempotent. Edited source content becomes a new immutable snapshot. Signals are not automatically promoted into Findings or Cases.

## Build the integrated EGM plugin

Build the OpenAI-compatible package from the exact pinned EGM source plus reviewed local overlays:

    python tools/build_plugin.py --target openai --output /tmp/egm-system-package

For Claude:

    python tools/build_plugin.py --target claude --output /tmp/egm-system-claude-package

The builder refuses an unpinned upstream checkout and uses the upstream EGM package script after overlaying local skills, agents and policies. The output directory must not already exist.

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
