# Repository agent guidance

Persistent guidance for automated coding agents working in `brainboxemb.dashboard`.

## Repository purpose

`brainboxemb.dashboard` is the central static GitHub Actions/status dashboard for the configured `brainboxemb` repositories.

The normal data flow is:

```text
dashboard.yml
    -> GitHub REST/GraphQL APIs
    -> Python collectors/generator
    -> site/index.html + static assets
    -> GitHub Pages
```

Keep this repository intentionally small: no application server, database, Azure service, or frontend framework unless the project direction is explicitly changed.

## Sources of truth

Use the owning systems as the authoritative source instead of duplicating changing operational state here:

```text
dashboard.yml                    monitored repositories and dashboard policy
GitHub repository metadata       repository/default-branch/settings state
GitHub active branch rules       enabled rulesets affecting a branch
GitHub classic branch protection classic protected-branch state
GitHub Actions API               workflow/run state and historical metrics
GitHub pull requests/branches    PR and cleanup state
src/generate_dashboard.py        rendering and generic current-status collection logic
src/dashboard_entry.py           brainboxemb-specific collection/status policy
src/collect_action_metrics.py    historical Actions metrics collection
site/app.js                      browser-side freshness/relative-time behaviour
.github/workflows/               dashboard scheduling/deployment/settings/release automation
CHANGELOG.md                     release history
```

Do not hard-code current workflow results, release versions, branch lists, branch protection state, or repository settings into documentation or source when they can be read from GitHub.

## Workflow status semantics

For normal workflows, the dashboard status represents the most recent run on the repository's configured/default branch. Do not switch normal Build/Verify/etc. status to "latest run on any branch" because feature or PR activity must not replace the main-line health signal.

`Release` is deliberately different. The release procedure runs on temporary `release-request/**` branches, so Release status must use the latest run regardless of branch. This prevents a successful current release from being hidden by an older run on `main`.

Reusable-only workflows (`workflow_call` without a normal trigger) are hidden by default. GitHub's synthetic Pages workflow is displayed as `Pages`.

## Branch cleanup semantics

**Branch cleanup** is observational only. The dashboard must never delete branches automatically.

A non-default branch is a cleanup candidate when:

- its same-repository pull request is closed and the branch still exists; or
- the branch still exists and no same-repository pull request has ever used it.

Branches with an open PR are not cleanup candidates.

Long-lived generated/release branches are excluded by configuration. The current conventions include:

```text
build
verification
dev/build
dev/verification
prod/build
prod/verification
rel/*
gh-pages
```

Treat `rel/*` as a pattern, not as a version-specific literal. Future release-output branches such as `rel/v0.0.3/build` must remain out of the cleanup list automatically.

Branches such as `chore/*`, `temp-release-*`, `release-request/*`, and other unrecognised orphan branches should remain visible when they otherwise qualify; they are intentionally useful cleanup signals.

## Repository settings

The `PR auto-delete` status comes from GitHub's `delete_branch_on_merge` repository setting.

The `Branch protected` status is the effective protection state of the configured/default branch. Resolve it in this order:

1. GitHub's branch-rules endpoint (`/rules/branches/{branch}`), which returns only active rulesets and needs only Metadata read permission;
2. classic branch protection (`/branches/{branch}/protection`) using `DASHBOARD_ADMIN_TOKEN` when available because that endpoint needs Administration read permission;
3. the normal branch resource as a compatibility fallback.

A ruleset with `disabled` or `evaluate` enforcement is not active protection. The dashboard is observational only: it must never create, modify, enable, disable, or remove branch protection/rulesets.

For both repository settings, do not interpret an unreadable/missing value as an explicit negative state. Preserve the three-state distinction:

```text
true    -> enabled/protected
false   -> disabled/not protected
unknown -> Unknown
```

`DASHBOARD_ADMIN_TOKEN` is used only where repository Administration access is required. Never print, expose, persist, or place secret values in generated pages, logs, fixtures, configuration, or documentation.

## Actions metrics

Historical Actions metrics use a rolling window configured by `dashboard.action_metrics_days` and are intentionally refreshed more slowly than current status.

The expected behaviour is:

- collect at most once per UTC day;
- cache the daily snapshot with GitHub Actions cache;
- reuse the snapshot on later runs that day;
- do not force a Pages deployment merely because a new collection attempt occurred;
- deploy when metric values or other dashboard-visible state actually changed.

Metrics are derived runtime/performance values, not billing data.

## Scheduling and freshness

The scheduled workflow is best-effort GitHub scheduling, currently requested hourly at minute 11. Do not describe that schedule as a guaranteed polling interval.

Manual **Rebuild dashboard** is an intentional fallback.

The static page does not query all monitored repositories from the browser. Browser-side freshness checks only test whether a newer deployed dashboard page exists and reload it when available.

## Change-aware Pages deployment

Keep data collection separate from Pages publication.

The generator computes a SHA-256 fingerprint over dashboard-visible state and relevant renderer/static inputs. The generation timestamp is deliberately excluded. If the candidate fingerprint matches the deployed fingerprint and daily metrics did not change, skip Pages configuration, artifact upload, and deployment.

Preserve the safe failure mode: if the deployed fingerprint cannot be read, allow deployment rather than assuming the page is current.

## Release workflow

Use the permanent `.github/workflows/release.yml` workflow. A release tags an exact, already-verified commit and requires a matching `CHANGELOG.md` release heading.

Where the connected GitHub interface cannot invoke workflow dispatch directly, use the self-cleaning release-request mechanism rather than one-shot workflow files or permanent helper branches:

```text
release-request/vX.Y.Z/<40-character-release-sha>
```

Create that branch from the exact release commit. The workflow validates the request, creates an annotated immutable tag, and removes the request branch. Never overwrite an existing release tag.

## Development and tests

When changing status semantics, cleanup rules, fingerprinting, settings handling, or rendering, add/update focused unit tests in `tests/`.

Run:

```text
python -m unittest discover -s tests -v
```

before treating a change as complete.

Keep `src/` standard-library-first where practical; PyYAML is the intentionally small external dependency.

Do not commit generated `site/action-metrics.json` or other transient cache/output files.

## Documentation discipline

`README.md` explains user-facing behaviour and setup. `AGENTS.md` stores persistent implementation/maintenance guidance for agents.

When behaviour changes materially, update both the tests and the relevant README/CHANGELOG text so the repository does not drift from the actual dashboard semantics.
