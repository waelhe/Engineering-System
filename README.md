# EGM Engineering System

A single engineering knowledge and development system built on the Elephant–Goldfish Model (EGM).

This repository is the system's canonical source: EGM runtime assets, project-independent engineering governance, structured knowledge, evidence, retrieval, intake, verification, enforcement, and learning.

## Status

Repository bootstrap. Architecture and implementation are being established in reviewable stages.

## Upstream baseline

- Project: https://github.com/google/elephant-goldfish-model
- Baseline: EGM v0.1.1
- Tag commit: dea7761de06ce5b51c177ebb9bba0469f24af5a4
- License: Apache-2.0 (upstream license and notices must be preserved)

The upstream project is treated as a pinned foundation, not as an unmodified guarantee of production readiness. Local extensions are kept distinct from upstream-owned files and are verified independently.

## Intended scope

- Persistent, evidence-backed engineering knowledge.
- EGM orchestration for task context, design, independent review, implementation, and verification.
- Risk-tiered execution policies.
- GitHub, CI, review, test, and incident evidence intake.
- Traceable findings, cases, patterns, decisions, rules, controls, actions, risk acceptances, and verifications.
- Migration of useful historical knowledge without retaining a parallel legacy knowledge system.

## Non-goals

- No separate production database or always-on service in the initial version.
- No OpenSearch, Kafka, or vector database until measured retrieval requirements justify them.
- No automatic promotion of AI hypotheses into verified facts or binding rules.
- No autonomous production deployment or bypass of repository protections.

## Repository layout

The detailed architecture, data model, policies, phase gates, and implementation decisions will live under `docs/`. Machine-readable knowledge contracts and offline validators will live under `schemas/` and `tools/`.
