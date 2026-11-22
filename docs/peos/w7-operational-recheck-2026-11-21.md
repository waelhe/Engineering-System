# W7 — Operational maturity recheck

**Snapshot:** 2026-11-21  
**Machine registry:** `registry/peos/operations.w7-current.json`  
**Scope:** read-only Railway and Grafana Cloud source checks. No deployment, service configuration, secrets, database, alert-rule or notification-routing changes were made.

## Railway production

The production environment contains one live service, `app-java-v3`, with one running replica. `environment-status` reports the service **Online** and the currently active successful deployment is `abed12b2-a8d4-4cf0-9ac2-48888ba88b32`, running commit `1f46f8ae04008cb74436d99753478d1b5a828c9e` from 2026-11-15.

The newest deployment attempt is not successful. Deployment `b725182f-91d9-4dcc-a811-7922ac6a7eaa` attempted current `app-java-v3/main@8ab2c667aef190b58d88cb116d8ce004bf948cf9` on 2026-11-20 and failed at `BUILD_IMAGE`. Railway's build log says the Dockerfile cache mount ID at line 26 is missing the required cacheKey prefix. A second attempt on 2026-11-20 also failed. There are no staged changes or pending Railway operations.

PR #839 is the candidate repair. Its integration, canonical-plan, OpenRewrite, CodeQL and container workflows passed on the inspected head, but its main CI run was queued at capture. No deployment success for the repaired head is claimed.

## Resource observation

Railway returned 1,441 samples over 24 hours. Memory was 0.998631424 GB at the current sample, averaged 0.997748524 GB and peaked at 0.999952384 GB. CPU current was 0 and the 24-hour average was approximately 0.00151. The service-config response did not include a memory limit, so this report deliberately does not convert the memory value into a percentage or claim a confirmed limit breach. The absolute memory samples warrant capacity review and correlation with application telemetry.

## Grafana Cloud

The Grafana datasource inventory returned 17 data sources, including a default Prometheus datasource. The contact-point list returned an empty array. The notification policy tree returned root receiver `empty` and no child routes. The alert-rule read returned `null`, not a structured rules inventory; it is therefore not interpreted as a verified zero count. Prometheus query calls could not resolve the UID that appeared in the datasource list.

These observations establish an alert-delivery routing gap: a contact point and a non-empty receiver are not configured in the returned state. They do not establish the complete alert-rule inventory or that no alert rules exist.

## W7 exit criteria still open

1. Merge the Railway cache-ID repair only after exact-head review and all required CI succeeds; observe a new production deployment reach SUCCESS and pass liveness, readiness and aggregate health checks.
2. Confirm the actual Railway memory limit and assess sustained peak usage against the service's configured limit.
3. Reconcile the Grafana datasource UID discrepancy; run bounded Prometheus queries against the correct datasource.
4. Obtain a structured alert-rule inventory, provision an owner-approved contact point and notification route, and test end-to-end delivery with a controlled test alert.
5. Verify SLO queries consume live metrics and exercise a rollback/recovery runbook.
6. Record all operational evidence against exact deployment IDs, commit SHAs, query windows and capture dates.

**Disposition:** W7 is partially observed, not operationally mature. The service is online on a previous successful deployment, but its latest build attempt failed; memory usage is high in absolute terms; and alert routing is incomplete. No production changes were applied during this inspection.
