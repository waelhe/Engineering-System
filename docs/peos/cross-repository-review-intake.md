# Cross-repository EGM review-signal intake

**Implementation:** Code and workflow are committed on the PEOS branch.  
**Activation:** Disabled until a narrowly scoped GitHub App is installed and its credentials are configured in this repository.  
**Write boundary:** `waelhe/Engineering-System` only.  
**Source repositories:** `waelhe/app-java-v3`, `waelhe/marketplace-admin`, `waelhe/mobile-marketplace`.

## 1. What the collector does

The scheduled/manual workflow reads open PR metadata, submitted reviews, PR review comments and issue-level PR comments from the three registered source repositories. It only selects PRs whose base is the configured default branch.

Each item is converted into a source-linked EGM **Signal** under the source project's knowledge scope. The original body is redacted before storage and is explicitly tagged as untrusted source data. Repeated source IDs are deduplicated by the canonical EGM intake.

The collector does not:
- fetch, check out, merge, build, test or execute any source PR branch;
- download or execute source artifacts;
- change, approve, dismiss, close or merge source PRs;
- promote a Signal to a Finding, Pattern, Rule, Control or Verification;
- change repository settings or deploy any application.

After collecting Signals, the trusted code from the canonical default branch validates the EGM knowledge store, migration manifest, receipts, PEOS registry and tests. Only generated knowledge/index data is pushed to a fresh branch in Engineering-System and offered as a **Draft** PR. The normal review and merge process remains mandatory.

## 2. Token and repository permissions

Two different credentials have deliberately separate roles.

### Source token — GitHub App installation token

Create or reuse a dedicated GitHub App installed only on these three source repositories:

- `waelhe/app-java-v3`
- `waelhe/marketplace-admin`
- `waelhe/mobile-marketplace`

Grant only:
- Repository metadata: read (GitHub's required baseline).
- Pull requests: read.
- Issues: read.

Do **not** grant source Contents, Actions, Administration, Checks, Commit statuses, Deployments, or write permissions. GitHub's required/default repository Metadata permission remains read-only; the ruleset audit uses that metadata read surface for GET-only branch/ruleset inspection. The collector reads PR objects and review/comment APIs; it does not read source files or run source code.

The workflow uses the official `actions/create-github-app-token` action pinned to the verified v3.4.0 commit `f418cff399f7aef4c2f0ad47e25ca7a6abbdd6fc`. It creates a repository-scoped installation token for only the three named source repositories and explicitly narrows it to `pull-requests:read` and `issues:read`. The token is short-lived and revoked by the action's post step. The governance audit also uses this token for read-only metadata requests on the same three registered source repositories; the Engineering-System sink continues to use only its own workflow token.

### Sink token — workflow GITHUB_TOKEN

The workflow's `GITHUB_TOKEN` is scoped to Engineering-System and the current job grants only:
- Contents: write — push the generated, data-only branch.
- Pull requests: write — open the draft intake PR.
- Actions: write — dispatch the trusted validation workflow for that intake PR.

It is never used to read the source repositories. Neither credential is passed to validators, tests or child Git processes. The shared subprocess environment removes GitHub and EGM token variables before executing unprivileged child code.

## 3. One-time activation

In GitHub:

1. Register the dedicated GitHub App and set the repository permissions exactly as described above.
2. Install it on **only** the three source repositories listed in `registry/peos/review-sources.json`. Do not install it on all repositories or grant repository write permissions.
3. In `waelhe/Engineering-System`, add repository variable `EGM_REVIEW_APP_CLIENT_ID` with the App's Client ID.
4. Add repository secret `EGM_REVIEW_APP_PRIVATE_KEY` with the App's private key.
5. Run **Actions → Cross-Repository Review Signal Intake → Run workflow**. The workflow reports a clear disabled message and performs no source query or write when either credential is absent.

The App's private key is held only by the canonical sink repository. Installation permissions must be approved for all three sources. The private mobile repository must be included in the App installation's selected-repository list; otherwise the token is not authorized to read it.

## 4. Schedule and bounds

The workflow runs daily at 05:43 UTC and can also be started manually. The checked-in registry caps the scan at 50 recently updated backend PRs and 25 for each client repository, with a seven-day update window. These bounds can be revised through a reviewed change to the registry.

A source PR targeting another base branch is skipped. The source repository's actual default branch is checked against the registry before collection; branch drift fails closed and requires a reviewed registry update.

## 5. Verification and failure behavior

The implementation has unit tests for:
- registry schema and duplicate-source rejection;
- source/sink separation;
- source default-branch drift;
- PR base-branch filtering;
- read-only source token routing;
- removal of both tokens from child-process environments.

The PR workflow must additionally pass the canonical EGM validation, PEOS validation, receipt validation, index check, full pytest suite, and both integrated runtime-package builds. A token, API permission, pagination, source repository or validation failure stops publication. Signals already written to the isolated runner are not uploaded and are collected again on the next run.

## 6. Official references

- GitHub App permission selection: https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app
- GitHub App installation and selected repositories: https://docs.github.com/en/apps/using-github-apps/installing-a-github-app-from-a-third-party
- Official create-github-app-token action: https://github.com/actions/create-github-app-token
- GitHub Actions token least privilege: https://docs.github.com/en/actions/reference/security/secure-use

**Current state:** the code and source registry are implemented, but live cross-repository intake is not active until the owner completes the App installation and stores the two credentials. No token or key is committed to this repository.
