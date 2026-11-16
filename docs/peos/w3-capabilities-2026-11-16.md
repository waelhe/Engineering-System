# W3 — Journey-outcome capability candidates

**Snapshot:** 2026-11-16  
**Upstream project source:** `waelhe/app-java-v3/main` at `5809a8c3e2b351b3b807b9ed26cf211a2fd3f1b6`  
**Journey source snapshot:** `2026-11-14`  
**Registry:** `registry/peos/app-java-v3.capabilities.json`

## Purpose

This is a conservative first capability index derived from the 35 canonical journey records. It creates one **candidate journey outcome** per source journey so PEOS can link user-visible outcomes to later capability decomposition, module ownership, contracts, clients and verification.

It does **not** assert that one journey equals one final domain capability. A journey may require several capabilities, and a capability may serve several journeys. The one-to-one candidate link is only an indexing seed.

## Trust and verification boundaries

All 35 records remain `candidate_not_adjudicated`. The source journey inventory marks its implementation labels as historical and `not_revalidated_at_2026-11-14-main`. Accordingly:

- Backend, Android, Admin, Provider and production verification remain `not_revalidated`.
- `tested_head_sha` is null and no current workflow run is claimed.
- Module names are preserved exactly as documented by the journey source. They are not promoted to module ownership; mapping remains `not_adjudicated`.
- Current APIs, GraphQL fields, events, Android screens, Admin screens, provider workflows and production effects must be re-derived from source code and current tests.
- Candidate decomposition must be reviewed against accepted ADRs, current module boundaries, contracts and product requirements before acceptance.

## Acceptance process

A candidate can be promoted only after:

1. Revalidating the source journey against a pinned current `app-java-v3/main` SHA.
2. Decomposing or merging candidate outcomes into reviewed product capabilities.
3. Adjudicating the responsible domain/module using source code and governing decisions.
4. Linking current REST/GraphQL/event contracts and applicable Android/Admin/Provider surfaces.
5. Attaching successful tests and review evidence bound to exact SHAs.
6. Recording remaining gaps and an accountable owner.

The validator enforces the candidate state, source-journey relationship, module-name provenance, and absence of current verification claims. It does not independently establish semantic correctness or approve capabilities.
