# PEOS — Platform Engineering Operating System

**Status:** Operating model proposal, implemented as a versioned evidence snapshot in this branch.  
**Scope:** Control plane for the existing platform repositories; not a new runtime service.  
**Relationship:** PEOS governs the platform engineering inventory and delivery state. EGM remains the context, knowledge, review, verification and learning engine.  
**Implementation constraint:** One canonical EGM knowledge store. PEOS registries reference EGM records and repository evidence; they do not create a parallel defect/evidence database.

## 1. System boundary

PEOS is the engineering control plane above the current backend, Android and admin repositories. It describes what exists, what is planned, what is verified, what is blocked, and which change can safely move the system forward.

The runtime architecture remains the existing Spring Boot modular monolith. PEOS does not introduce microservices, a second database, Kafka, OpenSearch, a vector store or a new always-on service. Initial inventories are Git-tracked JSON with deterministic validation.

## 2. Eight bounded responsibilities

1. **Truth and governance** — approved product intent, ADRs, authority boundaries, source pins and drift adjudication.
2. **Domain and module architecture** — domains, Maven modules, ownership, public interfaces, events and dependency constraints.
3. **Capability engineering** — capability contracts, business rules, provider dependencies, failure paths and proof obligations.
4. **Journey engineering** — customer, provider, operator and system journeys spanning backend, Android and admin surfaces.
5. **Work and change orchestration** — tasks, PRs, dependencies, review shards, migration ordering, merge gates and post-merge evidence.
6. **Quality, security and compliance** — architecture, unit, integration, concurrency, contract, client, security and privacy checks.
7. **Client and operations engineering** — Android and Admin experiences, releases, deployment evidence, observability, SLOs and recovery.
8. **EGM knowledge and learning** — contextual retrieval, Elephant design, genuinely independent Goldfish review where supported, Signals, Findings, Cases, Patterns, Rules, Controls and Verifications.

These are responsibilities inside one system, not eight services or eight databases.

## 3. Source-of-truth model: four evidence planes

Do not arrange every source in one linear precedence list. Different sources answer different questions:

| Plane | Question | Authority |
|---|---|---|
| Product intent | What should the platform do and why? | Owner-approved requirements and decisions |
| Implementation | What is present in the repository? | Main-branch code, migrations, API/GraphQL contracts, clients and configuration |
| Verification | What was actually tested? | CI/test evidence bound to exact commit SHA, workflow run and test scope |
| Operations | What is running and recoverable? | Deployment SHA, smoke evidence, telemetry, incident and recovery records |

A mismatch is a **drift record** with owner and resolution; it is not silently resolved by allowing newer code, older documentation or a green test to overwrite another plane.

Historical documents remain useful evidence, but their measurement baseline must be carried with them. A status from an October SHA is not a November main status.

## 4. Canonical records and relationships

PEOS maintains only platform inventory and workflow metadata. EGM remains the canonical knowledge store for Signals, Evidence, Findings, Cases, Patterns, Decisions, Rules, Controls, Actions, Risk Acceptances and Verifications.

PEOS inventory records reference source paths, source blob SHA, repository commit SHA, capture date and revalidation state. They do not duplicate Evidence bodies or defect narratives.

Required registries:
- Project/source registry.
- Domain and Maven module registry.
- Capability registry.
- Journey registry.
- PR/dependency registry.
- Release/deployment/evidence index referencing EGM Verification IDs.
- Technology/reference register with exact version, upstream source, license, decision and next review.

## 5. Capability and journey proof

A capability records its owner, use cases/personas, contracts, state transitions, dependencies, external providers, failure/retry semantics, clients and proof obligations.

A journey links capabilities into a user/operator outcome. The shared lifecycle (Need → Discover → Request → Response/Offers → Compare/Select → Agreement → Commitment → Execution → Completion → Aftercare) is an analysis scaffold only. It does not replace domain-specific state machines for payments, booking, orders, delivery or disputes.

Each proof is scoped separately:
- Backend unit and module tests.
- Database/integration and concurrency tests using real dependencies where needed.
- REST/OpenAPI and runtime GraphQL SDL contract tests.
- Android UI/navigation/device tests.
- Admin browser journeys.
- Security, authorization and privacy tests.
- Deployment smoke and operational recovery.

A green backend test does not prove Android or Admin completion. A merged PR does not prove a deployed journey.

## 6. PR and release state are separate

PR lifecycle:
Draft → Ready for Review → Changes Requested → Ready to Merge → Merged.

Release lifecycle:
Assembled → Checks Passed → Authorized → Deployed → Smoke Verified → Operationally Observed → Evidence Synchronized.

A release may contain several PRs. Therefore Merged, Deployed and Smoke Verified must not be statuses in one shared PR state machine.

Every PR snapshot binds its base SHA, head SHA, changed files, CI, reviews, migration/API impact, dependencies and merge policy. A PR is not mergeable merely because its checks are green. It must be based on a current compatible target and pass required reviews and protections.

Special rules for this platform:
- #787 remains the single full-commerce candidate according to the campaign contract; do not decompose it into six mergeable shards.
- #806–#811 are permanent review-coverage shards and are tracking-only / DO_NOT_MERGE.
- #837 is stacked on the commerce branch, not on main.
- Owner authorization and repository protection remain required; this system does not auto-merge.

## 7. Maturity model

The model has **seven levels, M0–M6**:

| Level | Meaning | Exit evidence |
|---|---|---|
| M0 — Unmapped | Scope/owner/dependencies are not yet established | Audited inventory |
| M1 — Designed | Requirements, decisions, contracts and state transitions are defined | Approved design and contracts |
| M2 — Implemented | Code, schema/migrations and unit tests exist | SHA-bound build and unit tests |
| M3 — Backend proven | Cross-module and real-dependency journeys pass | Integration/contract evidence |
| M4 — Product proven | Applicable client/provider/admin journeys work | Android/Admin E2E evidence |
| M5 — Release ready | Security, config, external dependencies, deployment and smoke are verified | Authorized deployment and smoke evidence |
| M6 — Operationally mature | SLOs, telemetry, recovery and learning are demonstrated under real operation | Operational history and incident/recovery evidence |

Do not average dimensions in a way that hides security, integration or client gaps. Track Domain, Backend, Integration, Android, Provider/Admin, Security and Operations independently. Use unknown, not_applicable, blocked_external and not_revalidated explicitly; never convert missing evidence into success.

## 8. Technology and reference policy

Before adopting a tool: define the gap, inspect existing Spring/Android/GitHub capabilities, consult official documentation for the pinned version, inspect the upstream repository/release/license, compare alternatives, run a scoped PoC only when necessary, and record an ADR with measured results.

Keep the current Modular Monolith, PostgreSQL/PostGIS, Redis, Maven, Spring Modulith, DGS, Kotlin/Compose and existing delivery stack. Use Testcontainers, Spring Modulith verification/scenarios, contract gates and Playwright where they match existing risks. Do not add Kafka, OpenSearch, Temporal, OpenFGA/Cedar, another database or a new agent runtime without measured evidence and an approved decision.

## 9. W0–W7 implementation sequence

- **W0 — Evidence baseline:** pin repository heads, enumerate modules/journeys/PRs, capture dependency and check states, flag stale or malformed sources.
- **W1 — Operational truth:** validate deployment identity, liveness/readiness, config, observability consumers, alerts, runbooks and recovery evidence.
- **W2 — Capability and journey linking:** map each capability/journey to domains, modules, contracts, clients, tests and known gaps.
- **W3 — PR queue control:** classify all open PRs, refresh bases, settle dependencies and review policy without opening duplicate work.
- **W4 — Critical-risk closure:** sequence money, identity, privacy, API and concurrency risks from evidence.
- **W5 — Commerce and backend outcomes:** complete the governed commerce candidate and remaining cross-domain backend journeys.
- **W6 — Android and PAOS/Admin:** close client/provider/operator journeys against exact contracts.
- **W7 — Operational maturity:** deployment/smoke, SLO consumption, alert routing, resilience and recovery.

## 10. Adoption and safety gates

- PEOS additions remain stacked on EGM foundation PR #1 until that PR is reviewed and accepted.
- The current W0 snapshot is descriptive; it does not certify every PR or journey.
- No merge, deployment, production mutation, migration cutover or knowledge-authority transfer is performed by the baseline job.
- A snapshot is refreshed only by a new source capture with exact SHAs and new evidence; old snapshots remain historical.
