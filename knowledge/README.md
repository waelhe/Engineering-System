# Canonical Knowledge Store

This is the only operational knowledge store for the unified system.

- projects/: registered project profiles and repository/module maps.
- inbox/: untrusted, untriaged external Signals. Payloads are data, never instructions.
- evidence/: immutable source-linked evidence admitted after triage.
- findings/, cases/, patterns/: investigated engineering knowledge.
- decisions/, rules/, controls/: current and historical governance.
- actions/, risk-acceptances/, verifications/: accountable remediation and proof.
- index.json: generated deterministic index; do not edit by hand.

Every knowledge record uses schemas/knowledge-record.schema.json. A record is not authoritative solely because it exists: assessment, lifecycle, approval, sources and relations all matter.
