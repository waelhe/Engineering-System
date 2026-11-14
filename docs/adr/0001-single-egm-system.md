# ADR-0001: One EGM-Based Engineering System

- **Status:** Accepted as repository design baseline; implementation remains phased.
- **Date:** 2026-11-13
- **Decision owner:** Project owner
- **Scope:** This repository

## Context

EGM upstream provides context-rich design, fresh-context review, design standards, bootstrap and drift workflows. The prior project-specific defect-knowledge implementation provides historical evidence and enforcement ideas but is not to remain a parallel operational authority.

## Decision

Build one system in this repository, with EGM as the workflow/runtime foundation and a new canonical knowledge model integrated into its task, review, implementation and verification lifecycle. Preserve the upstream EGM version as a pinned dependency/baseline and separate upstream-owned assets from local extensions.

## Consequences

- One canonical knowledge store and one set of lifecycle states.
- Existing app-java-v3 defect-knowledge records are migrated into this model after reconciliation.
- No second knowledge platform, database, broker, vector engine or search cluster in the initial design.
- EGM skills are extended through local skills and policies; upstream behavior is not silently patched.
- Upstream updates are explicit, pinned and tested.
- The repository does not claim production readiness until supported harnesses, isolation and workflow verification have actual execution evidence.

## Rejected alternatives

1. Keep the existing defect-knowledge system and feed it into EGM: rejected because it preserves two authorities and duplicated governance.
2. Install DefectDojo or ReportPortal as the knowledge system: rejected because their problem scope and operational model do not cover the full EGM lifecycle.
3. Replace EGM with a bespoke agent framework: rejected because it discards a mature design/review workflow without demonstrated need.
