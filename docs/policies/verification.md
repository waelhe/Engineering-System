# Verification and Enforcement Policy

## Proof hierarchy

Use the most direct proof suitable for the claim:
1. reproducible failing scenario and regression test;
2. passing focused test against the candidate SHA;
3. relevant unit/integration/contract/property/fuzz/E2E suites;
4. CI workflow and job evidence for the exact SHA and PR;
5. proof the tested commit is included in the target branch;
6. operational/production evidence where the claim concerns runtime behavior.

A build passing is not proof a feature is complete. A PR being merged is not proof production is deployed.

## Verification record

Capture exact repository, PR, branch and tested SHA; workflow name, run ID, job/check name and conclusion; test command or scenario identity; environment and relevant runtime/dependency versions; artifact/log/source URL and digest where available; whether tested SHA is an ancestor of final candidate and target branch; verifier and timestamp.

A workflow must be complete and successful. queued, in_progress, cancelled, skipped, missing, or mismatched runs do not satisfy a successful-proof claim. A general Verification may document a control or operational check without target-branch inclusion; that proof is required specifically when closing a reproducible code-defect Finding.

A `verified` Execution Receipt must have `tested_sha` equal to its `head_sha`: the claim is that the declared candidate itself was tested. A `merged` or `deployed` receipt may retain an earlier `tested_sha` only when it also records the target SHA and a verifiable ancestry/inclusion proof. A passing run on an unrelated revision is not proof for the candidate.

## Code-defect closure

For reproducible defects, require a reproducer and regression test when feasible. The test should fail on pre-fix code and pass on the fix. Record candidate SHA, successful workflow evidence and target-branch inclusion. A fix commit by itself does not close a Finding.

For non-reproducible or non-code cases, set the Finding's `closure_mode` to `alternate_proof` and record `alternate_closure_proof`. The validator requires an approved same-project Decision or Control with an approver, at least one source-linked Evidence record, a test limitation, and a resolved Action whose owner matches the accountable proof owner and has measurable acceptance. When residual risk remains, a reassessment date is mandatory. Do not attach a CI target-inclusion claim to an organizational proof merely to satisfy a code-defect gate.

For reproducible code defects, set `closure_mode` to `code_defect`; the linked Verification must bind the successful workflow's tested SHA to the target-inclusion proof and its source record.

## Enforcement mapping

Each approved Rule links to one or more Controls. A Control records enforcement type, scope and trigger, exact command/workflow or owner, failure behavior, evidence required to consider the control active, and known blind spots/bypass paths.

A documented rule without a working Control is reported as unenforced. A Control without passing evidence is not counted as proven.

## Security-sensitive CI

Untrusted PR content must not execute in a privileged workflow. Capture untrusted events with read-only/no-token workflows where possible; privileged receivers execute trusted default-branch code and re-fetch authoritative current state through the provider API. Never trust artifacts or event body data as proof of permissions or status.
