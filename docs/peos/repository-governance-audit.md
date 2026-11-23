# Main-branch repository governance audit

**Capture date:** 2026-11-23  
**Audit mode:** Read-only GitHub REST API. The audit never creates, modifies or deletes a ruleset.  
**Policy:** `registry/peos/repository-governance.json`.

## 1. Current observed state

| Repository | Visibility | Branch API `protected` | Rulesets API | Disposition |
|---|---|---:|---|---|
| `waelhe/app-java-v3` | Public | true | Readable; active ruleset #22305466 | Existing policy baseline verified |
| `waelhe/marketplace-admin` | Public | false | Readable; empty | Ruleset missing |
| `waelhe/Engineering-System` | Public | false | Readable; empty | Ruleset missing |
| `waelhe/mobile-marketplace` | Private | false | HTTP 403: plan feature unavailable | Plan-limited, not reported as an empty ruleset list |

The backend's existing active ruleset targets only `refs/heads/main` and requires: PR-only changes, resolved review threads, squash merge, linear history, no deletion, no non-fast-forward updates, and the exact required checks recorded in the policy registry. Its required approving-review count is zero; this does **not** satisfy EGM's separate independent-review requirement.

For Admin, the current successful GitHub Actions check-run name is `Materialize pinned Dashboard, apply overlay, type-check and build`. For Engineering-System, the validation workflow's job check is `validate`. The registry records these exact check names rather than inventing generic CI labels.

## 2. Private mobile repository limitation

GitHub's Rulesets REST API returned:

```text
HTTP 403
Upgrade to GitHub Pro or make this repository public to enable this feature.
```

The project is intentionally private. Do not make it public to work around the plan limit. If branch rulesets are required for this private repository, the supported path is a GitHub plan that provides private-repository rulesets. The audit treats the repository as **plan-limited**, not as verified and not as an empty ruleset list.

## 3. Desired policy for the remaining public repositories

The registry follows the backend's existing baseline to avoid introducing arbitrary new merge semantics:

- PR required for every change to `main`.
- No branch deletion or non-fast-forward update.
- Linear history.
- Review conversation resolution required.
- Squash merge only.
- Required CI checks must be selected from observed workflow check-run names.
- Bypass actors: none.
- No invented approval count: EGM independent Goldfish/human review remains a separate gate that must be evidenced before a PR is declared accepted.

The Admin and Engineering-System rulesets are currently absent. Their policy gaps are visible to the scheduled audit; this report does not claim they are configured.

## 4. Audit implementation

The scheduled workflow uses two separate read credentials:

- `GITHUB_TOKEN` reads only the Engineering-System sink repository.
- The same short-lived source GitHub App token used by cross-repository review intake reads the three source repositories. The token is repository-scoped and requests only Pull requests: read and Issues: read; GitHub's default Metadata read permission is used for branch metadata and repository ruleset GET endpoints. No Administration write permission is requested.

The audit code selects the sink token only for `waelhe/Engineering-System` and the source token for the three source repositories. The source token is never used for a write request. The private mobile repository is therefore accessed through the App installation, not through the sink repository's `GITHUB_TOKEN`.


`tools/audit_repository_governance.py` reads branch metadata, the repository rulesets collection and each active matching ruleset. It compares the effective rules to the checked-in PEOS expectation and writes a GitHub Actions job summary. It does not require Administration write permission and does not attempt a mutation.

The workflow `Repository Governance Audit` runs daily and manually. Accessible missing policies make the workflow report failure; a plan-limited private repository is reported as a distinct warning state. API permission failures other than the known plan limitation are not converted into success.

## 5. Official references

- GitHub rulesets creation/availability and private repository plan limits: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository
- Required status checks: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- Rulesets REST API and the Administration write permission required to create one: https://docs.github.com/en/rest/repos/rules
- About rulesets and rule layering: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets

**Disposition:** governance is not complete. The backend has a verified active ruleset; Admin and Engineering-System still need an administrator-authorized ruleset; mobile remains blocked by the current plan. The audit is implemented, but only repository administrators can apply the missing rulesets.
