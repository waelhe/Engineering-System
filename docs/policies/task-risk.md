# Task Classification and Risk Policy

## Classification model

Every task receives a workflow tier based on its highest credible impact, not estimated effort or agent preference. The task may be escalated at any time. A higher-risk signal overrides a lower initial classification.

| Tier | Typical scope | Required workflow |
|---|---|---|
| T0 — Inquiry | Explanation, research, read-only status, tiny typo/docs question | Minimal context; cite sources; no design pipeline unless requested |
| T1 — Local change | Small isolated code/doc/test fix with no contract, data, security or cross-module effect | Targeted investigation, write boundary, appropriate tests, self-review |
| T2 — Feature/change | New behavior, multiple files/modules, API or integration behavior | Project context, design/spec, fresh Goldfish review, readiness plan, implementation, regression/integration tests, knowledge review |
| T3 — Critical change | AuthZ/security, money/ledger, concurrency, destructive data/migrations, external side effects, production, major architecture or broad contract change | Full EGM lifecycle, independent design and code review, explicit human authorization at required gates, adversarial failure analysis, environment-accurate verification, rollback/recovery proof |

## Mandatory escalation triggers

Escalate to T3 when a change affects:
- authentication, authorization, identity, tenant/data boundaries or secrets;
- money movement, ledger invariants, pricing distribution, refunds or settlement;
- concurrency, idempotency, retries, event delivery or distributed state;
- applied database migration history, destructive data operations or irreversible backfills;
- public API/GraphQL contracts, compatibility guarantees or high-blast-radius integrations;
- production deployment, infrastructure, access policy or security-sensitive workflows.

A task can be T2/T3 even if its code diff is small. A large documentation-only edit may remain T1 if it has no binding policy impact.

## Classification record

For T1–T3, record task ID, project, repository and target ref; tier and triggering risk dimensions; affected modules, data and external systems; required source/policy profiles; reviewer requirements; test/evidence requirements; write allowlist and prohibited side effects.

Do not lower a tier solely because a reviewer or tool is unavailable. Record blocked/review_unavailable and explain.

## Approval gates

User approval is not required at every mechanical step. It is required when crossing a real authority boundary: unresolved product choice, architectural decision not already delegated, new paid/operational dependency, security-sensitive permission, irreversible data change, production deployment, or risk acceptance. Routine steps inside an approved plan can proceed without repetitive confirmation.
