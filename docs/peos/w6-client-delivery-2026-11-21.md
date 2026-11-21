# W6 — Android and Admin current evidence

**Snapshot:** 2026-11-21  
**Machine registry:** `registry/peos/clients.w6-current.json`  
**Purpose:** replace stale client-stack assumptions with current repository evidence and identify missing client acceptance proofs.

## Current source heads

| Surface | Repository / main SHA | Latest observed commit | Open PRs | Current evidence |
|---|---|---|---:|---|
| Admin | `waelhe/marketplace-admin@982ecf3667d2242cab941737cb6a0bceaee7ffcb` | 2026-10-20 | 0 | Downstream Saleor Dashboard 3.23.39 with platform integration documentation and scheduled contract-drift workflow |
| Mobile | `waelhe/mobile-marketplace@3e2357ac3f5ed00cfffc51b2909c60f9f214f1f4` | 2026-10-03 | 0 | Expo / React Native project with EAS OTA channels and expo-updates configured |

## Verified facts

### Admin

The package manifest identifies the downstream UI as `saleor-dashboard` version `3.23.39`. The README points to `PLATFORM_INTEGRATION.md` for platform GraphQL contracts, OAuth/BFF boundaries and test behavior. The workflow adds a weekly scheduled dashboard build and a contract-drift issue on scheduled failure, with auto-close after a successful scheduled run. No current workflow runs were returned for the queried main commit SHA; presence of the workflow is not proof that the most recent scheduled run succeeded.

### Mobile

The current package manifest identifies Expo SDK `~57.0.26`, React Native `0.86.3`, package version `1.0.0`, and npm. `expo-updates` is configured, `runtimeVersion.policy` is `appVersion`, and EAS channels are `development`, `preview`, and `production`. The README is still the default Expo starter guide. The repo is therefore correctly described as an Expo/React Native project; earlier Kotlin/Jetpack Compose descriptions are not current evidence for this repository.

No GitHub Actions runs were returned for the queried mobile main commit. This snapshot does not prove complete mobile screens, native authentication, checkout, inbox, push notifications or release readiness.

## Completion rule

A client surface is not complete because the repository exists, a package builds, or OTA is wired. W6 exits only when each applicable journey is traced to the exact backend REST/GraphQL contract SHA, the responsible screen/navigation path, meaningful UI/component/E2E tests, authorization and error handling, and a release artifact on the same client source revision.

## Required work

1. Revalidate the Admin schema-generation workflow against the accepted backend GraphQL contract and execute representative operator journeys.
2. Replace starter-only mobile project guidance with the actual application architecture and supported journeys, based on source files rather than assumptions.
3. Map login/identity, catalog/search, product detail, cart/checkout, orders/delivery, notifications/inbox and profile journeys to implemented screens and tests.
4. Add or refresh exact-SHA CI and client E2E evidence; do not promote historical journey labels.
5. Keep Android and Admin as separate acceptance dimensions. Backend success cannot stand in for client proof.

This snapshot is read-only. It does not modify either client repository or publish an app build.
