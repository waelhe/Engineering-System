# Independent Review Policy

## Roles

- **Elephant / author:** owns context, draft, implementation proposal and responses.
- **Goldfish comprehension reviewer:** receives the target artifact only and tests whether it is self-contained.
- **Goldfish design critic:** receives the design plus an approved, bounded source reading set; tests technical and architectural assumptions.
- **Codebase/readiness reviewer:** checks paths, symbols, contracts and tests against the actual target code revision.
- **Executor:** implements the approved plan; does not approve its own work.
- **Verifier:** independently checks required proof and exact SHAs.
- **Human DRI/approver:** owns consequential trade-offs and approval.

## Independence evidence

A review counts as independent only when:
1. a fresh child context is actually created by the active harness;
2. the reviewer reads its persona, target artifact and every assigned source;
3. the parent transcript and author conclusions are not supplied as context;
4. the reviewer returns an actual completed result;
5. tool output or native execution evidence confirms completion and the reading set.

Fresh conversation context alone does not prove isolation from project instruction files, filesystem, memory services or ambient tools. Host-specific limits are recorded. If fresh context cannot be established, mark review not_run or blocked; same-context self-critique is not a Goldfish review.

## Findings adjudication

Each review item is a Signal until adjudicated. Classify it as valid, incorrect, needs_human_decision, duplicate, or not_actionable. Do not downgrade severity without evidence. Do not create one durable defect for every repeated comment. Preserve original observations and link them to the adjudicated Finding.

## Coverage

For T2/T3 changes, choose review lenses according to risk: simplicity/YAGNI, comprehension, architecture/failure modes, security, data/concurrency, code structure, and implementation readiness. Not every persona is needed for every task.

## Tool reviews

CodeRabbit, Copilot, linters and scanners are evidence sources, not authority. Record whether the tool ran, its SHA, status and findings. An absent or rate-limited bot is not a clean review. A successful gate is not equivalent to an independent human or Goldfish review unless the gate implements that review.
