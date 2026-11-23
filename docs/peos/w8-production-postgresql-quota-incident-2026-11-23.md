# W8 — Production PostgreSQL Quota Incident — 2026-11-23

**Status:** Confirmed production outage; recovery is blocked by an external Neon quota refusal.  
**Evidence class:** Read-only operational observation, not a remediation or recovery receipt.  
**Scope:** Railway production service `app-java-v3`; no production configuration, credentials, database data, or deployment was changed.

## 1. Source pins and capture boundary

| Source | Observed value |
|---|---|
| Backend repository | `waelhe/app-java-v3` |
| Backend `main` SHA | `9b5e29afd0a5a344a8ac04a51a51da32fe134d10` |
| Backend deployment commit | `9b5e29afd0a5a344a8ac04a51a51da32fe134d10` |
| Railway project | `meticulous-consideration` / `c8985750-82a2-42eb-8431-ee0f49352818` |
| Railway environment | `production` / `c324c1a0-e4db-4a9a-8dc0-30ca1f3935d0` |
| Railway service | `app-java-v3` / `43b1b64b-9087-45d4-88ca-358a40c5a583` |
| Failed deployment | `b76e73fd-5ad7-469d-8aa5-e68f7b09ab3f` |
| Failed deployment time | `2026-11-22T07:57:55Z` |
| Capture date | `2026-11-23` |

The source repository's runbook identifies PostgreSQL as an external Neon service, not a Railway database. See the [provider migration runbook](https://github.com/waelhe/app-java-v3/blob/9b5e29afd0a5a344a8ac04a51a51da32fe134d10/docs/operating/trial-renewal-and-provider-migration-runbook.md).

## 2. Observed production state

Railway's read-only environment status reported:

- Service state: `crashed`; running replicas: `0/1`; crashed replicas: `1/1`.
- One critical issue and one recent failed deployment; no pending environment work.
- Latest deployment status: `CRASHED`, on the backend SHA above.
- HTTP totals in the queried 24-hour window: 77 requests, 0 responses in 2xx, 3 in 4xx, and 74 in 5xx.
- Resource samples: memory about `0.99946 GB` against a `0.999997 GB` limit. This is a capacity warning, but the observed application exception below identifies the immediate startup failure; these metrics alone do not prove an OOM kill.

## 3. Failure evidence and diagnosis

The container built and started the application process. The runtime log shows Tomcat initialized on port 8080 and the Spring WebApplicationContext initialized. Startup then failed while Spring Boot created `entityManagerFactory`, because Flyway could not obtain a PostgreSQL connection.

The PostgreSQL server returned the following message:

```text
ERROR: Your account or project has exceeded the quota. Upgrade your plan to increase limits.
SQL State: 53000
```

Spring cancelled application-context initialization, stopped Tomcat, and reported `Application run failed`.

**Confirmed immediate cause:** the configured external PostgreSQL provider rejected the connection because an account/project quota was exceeded. This is not evidence of a Docker build failure or a code regression in the Railway deployment repair.

**Not yet confirmed from the live Neon account:** which exact quota counter was exhausted, the current Neon plan, current compute usage, the next reset timestamp, and whether the account owner has already changed the plan. The Railway/GitHub connection cannot read those billing/account values.

## 4. Neon limits relevant to recovery

Neon's current pricing page lists the Free plan at 100 CU-hours per project per month. Its Launch plan is usage-based and currently lists compute at $0.106 per CU-hour and storage at $0.35 per GB-month; the page gives a typical spend estimate, not a quote for this database. See [Neon pricing](https://neon.com/pricing) and Neon's [2026-10-02 Free-plan update](https://neon.com/blog/neon-free-plan-1-gb-per-project).

The production project's actual plan and usage were not accessible in this read-only investigation. Therefore the Free-plan quota is relevant context, not a claim that the current account is definitely on Free.

The backend runbook contains an earlier quota incident with the same server response and documents historical Free-plan exhaustion. That is corroborating history, not a live usage read-back for this capture.

## 5. Connection-pool observation — hypothesis, not root-cause proof

At the captured backend SHA:

- `application-prod.yml` sets `spring.datasource.hikari.minimum-idle` to `${DB_POOL_MIN:5}` and `maximum-pool-size` to `${DB_POOL_SIZE:20}`.
- Base `application.yml` sets `minimum-idle: 5` and `idle-timeout: 300000` (five minutes).
- Whether production overrides `DB_POOL_MIN` or `DB_POOL_SIZE` was not inspected; environment variable values were not read.

Neon's current compute-lifecycle documentation says scale-to-zero occurs after five minutes with no active queries, and specifically treats `idle-in-transaction` sessions as active. Neon's guidance for long-running applications also explains that a compute can suspend even when clients are connected, subject to inactivity conditions. See [Compute lifecycle](https://neon.com/docs/introduction/compute-lifecycle) and [Using scale-to-zero with long-running applications](https://neon.com/blog/using-neons-auto-suspend-with-long-running-applications).

Consequently, the historical runbook statement that Hikari connections categorically prevent scale-to-zero is **not independently established by this capture**. The pool settings warrant a measured follow-up: inspect Neon compute activity and session state, then test idle-pool behavior against a non-production Neon branch before changing production defaults. Do not change pool sizing or connection lifecycle based only on this incident note.

## 6. Recovery gates

1. The account owner checks the affected Neon project in the Neon Console: current plan, the quota category, usage for the current billing period, and the next reset time.
2. The account owner chooses the financial/availability path: raise the project to a usage-based paid plan, or leave it suspended until the applicable quota reset. No plan change is made by this report.
3. After PostgreSQL accepts connections again, use the repository's current `Railway Deploy` workflow-dispatch procedure from `main`; do not replay historical Railway service/environment IDs or migration commands.
4. Verify a terminal Railway deployment `SUCCESS`, successful Flyway validation/application, readiness `200`, and the documented production smoke checks. A successful image build alone is insufficient.
5. Separately open a T2 follow-up to measure Neon idle-compute behavior and review Hikari configuration with a bounded non-production test. Any production pool/configuration change requires its own tested PR and normal review gates.

**Data safety:** do not point `DB_URL` at a new empty Neon project, rotate the five database/Flyway credentials, run migrations manually, or replace the live database as a quota workaround. The existing production data is outside Railway; a new project is not a data-preserving recovery.

## 7. Actions deliberately not performed

- No Neon plan/billing change or account mutation.
- No Railway variable, service, environment, deployment, or restart mutation.
- No database migration, reset, export/import, or schema change.
- No credential retrieval or disclosure.
- No change to the backend source repository.
- No claim of service recovery, readiness, or production availability.

This W8 note is incident evidence only. It does not close the production incident or authorize a financial change.
