# W1 recheck — production recovery and remaining SLO gaps

**Snapshot:** 2026-11-15  
**Backend source pin:** `waelhe/app-java-v3/main` at `8b1d2a82bf5c870d88ffc7d5d05e36bb06175c26`  
**Railway deployed commit:** `1f46f8ae04008cb74436d99753478d1b5a828c9e` (the still-open PR #839 head)  
**Registry:** `registry/peos/app-java-v3.operations.json`, appended records OPS-RAILWAY-003, OPS-GRAFANA-005 and OPS-GITHUB-003.

## Result

The November 14 W1 OFFLINE / no-series snapshot remains historical and was not overwritten. This recheck proves a partial production recovery:

- Railway has a successful deployment on the new production service and one configured replica in `europe-west4-drams3a`.
- The last provider HTTP records after that deployment showed `/actuator/health/liveness=200` and `/actuator/health/readiness=200`, but `/actuator/health=503`.
- Grafana's default Prometheus datasource now reports healthy and returns application metrics. A sample at 2026-11-15 12:51:12 UTC reported `marketplace_eventbus_stale=3`.
- Grafana still has no managed alert rules, no contact points and an empty root receiver. OTLP metric-export warnings remain in Railway logs.
- Railway's one-hour metrics showed memory at 0.9769 GB of 1.0000 GB (about 97.7%; 61 samples). This is low headroom, not proof of an OOM event.
- PR #839 remains open and unreviewed, although its head is the SHA shown in the successful Railway deployment. GitHub `main` remains at `8b1d2a82...`.

**Status: deployed, partially recovered, not operationally healthy or release-reconciled.** This is not a production-readiness certification.

## 1. Railway deployment and health

Production project `meticulous-consideration` (ID `c8985750-82a2-42eb-8431-ee0f49352818`), environment `production` (ID `c324c1a0-e4db-4a9a-8dc0-30ca1f3935d0`), service `app-java-v3` (ID `43b1b64b-9087-45d4-88ca-358a40c5a583`).

Successful deployment:
- Deployment ID: `abed12b2-a8d4-4cf0-9ac2-48888ba88b32`
- Created: `2026-11-15T10:45:13.638Z`; updated: `2026-11-15T10:49:23.777Z`
- Commit: `1f46f8ae04008cb74436d99753478d1b5a828c9e`
- Region: `europe-west4-drams3a`

Last recorded post-deployment HTTP requests:
- liveness 200 at 10:50:54 UTC
- readiness 200 at 10:50:55 UTC
- aggregate `/actuator/health` 503 at 10:50:57 UTC

These are the latest returned HTTP log records, not a newly executed external probe at the snapshot time. Anonymous health requests expose status only; component details require an authenticated operator. Do not weaken the aggregate health contract to hide the 503.

## 2. Event publication backlog — investigate before replay

The measured `marketplace_eventbus_stale=3` is not a count of business events that can safely be replayed blindly. The pinned `ModulithEventBusHealthIndicator.java` query counts rows in `event_publication` where `completion_date IS NULL` and publication age exceeds 21,600 seconds. It marks its own health contributor DOWN when this count is positive.

The same source pin shows:
- `application-prod.yml`: Spring Modulith staleness thresholds are published=6h, processing=1h, resubmitted=1h and restart republishing is enabled.
- `EventPublicationResubmission.java`: a scheduled `FailedEventPublications.resubmit(ResubmissionOptions)` sweep runs every 15 minutes, with a 24-hour retry backoff.
- The recent scheduler logs report no stale PUBLISHED, PROCESSING or RESUBMITTED publications. The count of three therefore needs authenticated inspection of individual rows and states; the available evidence does not identify event types, listeners, exceptions, attempt counts or last retry times.

The supported recovery mechanism is documented by Spring Modulith, but the correct sequence is:
1. Inspect the authenticated health component tree and the three incomplete/failed publication records.
2. Identify event type, target listener, completion attempts, last resubmission time and original business aggregate.
3. Read the listener exception and confirm the underlying dependency has recovered.
4. Confirm idempotency/duplicate-effect safety for the specific listener, especially payment, booking, ledger and notification effects.
5. Only then use the pinned Spring Modulith API and the repository's bounded retry policy. Do not mutate `event_publication` rows with ad-hoc SQL or force retries without owner evidence.

Official references: [Spring Modulith events — lifecycle, staleness and failed-publication resubmission](https://docs.spring.io/spring-modulith/reference/events.html) and [EventPublicationRegistry 2.1.x API](https://docs.spring.io/spring-modulith/docs/2.1.x/api/org/springframework/modulith/events/core/EventPublicationRegistry.html).

## 3. Resource headroom

One-hour Railway sample (61 points):
- memory current 0.9769 GB; average 0.9537 GB; maximum 0.9856 GB; reported limit 1.0000 GB.
- CPU current 0.00132; average 0.00243; max 0.01171, with a reported 2-vCPU limit.

The observed memory ratio is approximately 97.7% currently and 98.6% at the sample maximum. No OOM event was found in the inspected deploy logs. The data does not yet distinguish Java heap, direct/native memory, metaspace, thread stacks, or filesystem cache. Do not increase limits or arbitrarily force `-Xmx` without inspecting heap/non-heap metrics and the Railway plan's actual resource configuration.

## 4. Grafana and OTLP

The default datasource `grafanacloud-prom` now returns datasource health OK and the metric discovery API returns application metrics including `marketplace_eventbus_stale` and `marketplace_health_aggregate`. A process-uptime range query returned 145 samples through 13:15 UTC.

However:
- Railway deploy logs show failed OTLP metric-export warnings at 11:54, 12:18 and 13:02 UTC.
- There are zero Grafana-managed alert rules, zero contact points and root notification receiver `empty`.
- Two additional Prometheus datasources have empty URLs. Their ownership/purpose is unknown and they were not deleted or repurposed.

The repository contract explicitly states that Prometheus rule files are source artifacts until an operator loads them and configures a notification path. Presence of `monitoring/prometheus-rules/marketplace-alerts.yml` is not proof of evaluated rules. The official [Grafana Cloud OTLP documentation](https://grafana.com/docs/grafana-cloud/send-data/otlp/send-data-otlp/) says to use the endpoint and authentication variables shown for the actual stack; do not infer or copy token values. A real notification destination must be selected before enabling alert delivery.

## 5. PR and release traceability

PR #839 `fix(railway): restore production deployment after service migration`:
- head `1f46f8ae...`, CI, Integration Test, CodeQL, Container Scan, OpenRewrite and Snyk passed;
- no review submissions or review threads were found;
- Railway's successful deployment uses this PR head;
- it remains open and is not the current `main` commit.

This deployment must be treated as a successful operational deployment of an unmerged PR head, not as proof of merge approval. The incident #682 and PR #839 received evidence comments on 2026-11-15. Incident #682 remains open.

## 6. Next closure evidence

| Priority | Required evidence | Closure condition |
|---|---|---|
| P0 | Authenticated health details and three event-publication records | Root cause and exact listener/event identified; no unexplained stale publications |
| P0 | Successful application-level aggregate health probe | `/actuator/health` returns 200 and the event-bus gauge returns 0 for a sustained observation window |
| P1 | JVM heap/non-heap and Railway memory configuration | Measured safe headroom; no unexplained near-limit condition |
| P1 | OTLP delivery diagnostics | No recurring exporter failures and fresh telemetry continues |
| P1 | Alert evaluation and notification destination | At least one real test alert reaches a verified human-owned contact point |
| P1 | PR #839 review and release reconciliation | Reviewed/merged under repository policy, or a documented decision explains the deployed SHA and follow-up |

## Capture boundary

This recheck used read-only GitHub, Railway and Grafana reads plus inspection of provider HTTP/deploy logs. It did not change Railway configuration, memory limits, variables/secrets, Grafana datasources, alert rules, contact points, notification policies, databases, event publications or deployment state. No merge was performed.

Credential values and authorization headers are intentionally excluded from the registry and this document.
