# Knowledge Retrieval Policy

## Objective

Return the smallest relevant, source-linked knowledge set that materially improves the current task. Retrieval must not invent relevance or silently hide conflicting records.

## Progressive disclosure

1. **Project map:** project profile, repository/module map, active architecture decisions, core invariants and applicable policies.
2. **Relevant knowledge:** rules, controls, patterns, cases and findings matched to task domain, affected paths, APIs, tags and risk tier.
3. **Evidence detail:** exact source snippets/URLs, commits, PRs, tests, run IDs, logs and linked records needed to establish a claim.

The context builder returns record IDs, match reasons, status, freshness and source links. It does not flatten every record into a prompt.

## Retrieval constraints

- Filter by project and repository scope before ranking.
- Prefer approved/current records over proposed or superseded records.
- Never use a superseded decision or rule as current authority; expose it as history when useful.
- Include refuted and false-positive records only when they help avoid a known misclassification.
- Show conflicting applicable records together and mark the conflict.
- Prefer exact module/path/API/risk matches over generic text similarity.
- Include source citations for every retrieved claim.
- Deterministic lexical/metadata search is the baseline. Semantic/vector retrieval is not enabled until an evaluation set shows material improvement.
- Indexes are generated artifacts. Canonical records remain the source of truth.
