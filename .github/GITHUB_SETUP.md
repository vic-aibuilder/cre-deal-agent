# GitHub Repository Configuration

Manual settings applied by the repo owner (@vic-aibuilder) in the GitHub UI after creating the repo. Apply all of these before anyone opens a PR.

---

## Branch Protection — `main`

**Settings → Rules → Rulesets → New branch ruleset**

- [x] Require a pull request before merging
  - [x] Required approvals: **1**
  - [x] Dismiss stale pull request approvals when new commits are pushed
- [x] Require status checks to pass before merging
  - [x] Require branches to be up to date before merging
  - [x] Required status checks (job names from `.github/workflows/ci.yml`):
    - `Branch Guard`
    - `Quality Checks`
    - `Security Checks`
    - `Build App`
- [x] Require review from Code Owners (enforces `.github/CODEOWNERS`)
- [x] Block force pushes
- [x] Ruleset name: `protect-main` · Enforcement status: `Active` · targeting `main`

---

## Repository Settings

**Settings → General**

- [x] Default branch: `main`
- [x] Merge button options:
  - [x] Allow squash merging — enabled
  - [x] Allow merge commits — enabled
  - [x] Allow rebase merging — enabled
- [x] Automatically delete head branches after merge — enabled

---

## Code Owners

The `.github/CODEOWNERS` file is committed. It takes effect once "Require review from Code Owners" is enabled above.

---

## Verification Checklist

Run through this after applying all settings:

- [ ] Open a test PR from a branch named `feat/cre-0-test-branch` — confirm all four status checks appear as pending
- [ ] Open a test PR from a branch named `bad-branch-name` — confirm `Branch Guard` fails with a clear error
- [ ] Attempt a direct push to `main` — confirm it is rejected
- [ ] Confirm the merge button is greyed out until all checks pass and 1 approval is given
