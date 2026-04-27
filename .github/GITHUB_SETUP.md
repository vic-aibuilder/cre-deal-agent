# GitHub Repository Configuration

Manual settings applied by the repo owner (@vic-aibuilder) in the GitHub UI after creating the repo. Apply all of these before anyone opens a PR.

---

## Branch Protection — `main`

**Settings → Branches → Add ruleset (or classic protection rule) for `main`**

- [ ] Require a pull request before merging
  - [ ] Required approvals: **1**
  - [ ] Dismiss stale pull request approvals when new commits are pushed
- [ ] Require status checks to pass before merging
  - [ ] Require branches to be up to date before merging
  - [ ] Required status checks (job names from `.github/workflows/ci.yml`):
    - `Branch Guard`
    - `Quality Checks`
    - `Security Checks`
    - `Build App`
- [ ] Require review from Code Owners (enforces `.github/CODEOWNERS`)
- [ ] Do not allow bypassing the above settings
- [ ] Restrict who can push to matching branches — no direct pushes to `main`

---

## Repository Settings

**Settings → General**

- [ ] Default branch: `main`
- [ ] Merge button options:
  - [ ] Allow squash merging — enabled (recommended for clean history)
  - [ ] Allow merge commits — enabled
  - [ ] Allow rebase merging — your preference
- [ ] Automatically delete head branches after merge — enabled

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
