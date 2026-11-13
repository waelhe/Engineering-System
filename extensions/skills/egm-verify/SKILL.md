---
name: egm-verify
description: Verify implementation, regression protection, reviews, CI evidence and target-branch inclusion against exact commit SHAs.
---

# EGM Verification

Verification is an evidence task, not a narrative assertion.

## Required identity

Record repository, PR, branch, candidate HEAD SHA, tested SHA, target branch and target SHA. Never substitute a newer or older SHA without stating the relationship.

## Verification procedure

1. Re-read the approved plan and acceptance criteria.
2. Check the diff against the declared write allowlist.
3. Run the reproducer or focused failing scenario where feasible.
4. Run the regression test and appropriate unit, integration, contract, property, fuzz and end-to-end suites according to the risk tier.
5. Verify module boundaries, security, data/concurrency and API compatibility where affected.
6. Capture actual workflow/run IDs, conclusions, tested SHA and canonical URLs.
7. Confirm required independent review completed, including actual fresh-context and source-read evidence for Goldfish.
8. For a merge claim, prove the tested fix commit is an ancestor of the target branch.
9. For a deployment claim, require deployment evidence; a merge is not a deployment.
10. Record residual risks and any unavailable proof.

## Closure rules

- A reproducible code defect requires a regression test when technically feasible.
- A green workflow on another SHA is not proof for the current candidate.
- queued, in_progress, cancelled, skipped, missing or mismatched checks are not successful evidence.
- A review tool that did not run, was rate-limited or returned no final result is not a clean review.
- Non-reproducible or organizational cases require an explicit alternate proof contract and owner.

Do not close a Finding until its required proof is linked and the knowledge validator accepts the resulting relations.
