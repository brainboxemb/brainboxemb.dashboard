# brainboxemb.dashboard

Central GitHub Actions status dashboard for brainboxemb repositories.

The dashboard is generated as a static site and published with GitHub Pages. It has no server, database, Azure dependency, or JavaScript framework.

## What it shows

- repositories grouped by purpose;
- active GitHub Actions workflows discovered automatically;
- reusable-only workflows (`workflow_call` without a normal trigger) hidden automatically;
- status of the most recent run on each repository's default branch;
- whether the default branch is protected;
- direct links to repositories and workflow runs;
- latest Git tag per repository, linked to the tagged tree;
- open pull request count per repository, linked to the repository's PR list;
- branch cleanup candidates for closed pull requests whose source branch still exists, plus branches that have never had a pull request;
- branch auto-delete setting (`delete_branch_on_merge`) per repository;
- daily GitHub Actions performance metrics over a configurable rolling window;
- last activity per repository; relative activity timestamps update in the browser without rebuilding the static page;
- summary counts for passing, failing, and running workflows;
- search and **Problems only** filtering;
- responsive light/dark styling;
- data-generation timestamp shown at the top in the viewer's local time;
- visible **Page version checked** timestamp updated when the browser checks whether a newer deployed dashboard page exists;
- checks every minute for a newly deployed dashboard and reloads automatically when one is available;
- manual refresh shortcut to the GitHub Actions workflow.

Repositories without active workflows remain visible, but are collected in a separate **Repositories without Actions** section at the bottom. This keeps the main groups focused on repositories with workflow status while still giving a complete overview. The **Latest tag** column can be disabled with `dashboard.show_latest_tag: false`, the **Open PRs** column with `dashboard.show_open_pull_requests: false`, the **Default branch protected** column with `dashboard.show_default_branch_protection: false`, branch cleanup scanning with `dashboard.show_branch_cleanup: false`, and the **PR branch auto-delete** column with `dashboard.show_branch_auto_delete: false`.

## Configuration

Edit [`dashboard.yml`](dashboard.yml). A repository can be listed by name:

```yaml
- docker.scad-toolchain
```

The bottom section for repositories without workflows can be controlled with `dashboard.separate_repositories_without_workflows` and `dashboard.repositories_without_workflows_group`.

Or with overrides:

```yaml
- name: docker.scad-toolchain
  branch: main
  include_workflows:
    - build.yml
    - tests.yml
  workflow_labels:
    build: Docker build
    tests: Tests
```

`include_workflows` and `exclude_workflows` accept a workflow path, filename, normalized filename stem, or GitHub workflow name. Reusable-only workflows are hidden by default with `dashboard.hide_reusable_only_workflows: true`; this can also be overridden per repository when a reusable workflow should intentionally be shown.

Long-lived generated or publication branches can be excluded from **Branch cleanup** with `dashboard.branch_cleanup_ignore_branches`. The current configuration ignores `build`, `verification`, `dev/build`, `dev/verification`, and `gh-pages`. A repository entry can also add its own `branch_cleanup_ignore_branches` list.

The Actions metrics rolling window is controlled by `dashboard.action_metrics_days`; the current value is 30 days.

## Actions metrics

The dashboard derives performance metrics from GitHub workflow run history for all configured repositories. The overview shows run count, success rate, failures, cancellations, total wall-clock runtime, average runtime, and average workflow queue time. Expandable tables break the same data down by repository and by the workflows using the most runtime.

These values are performance/runtime measurements, not billable Actions minutes. This avoids depending on GitHub's legacy workflow timing REST endpoint and is also more meaningful for the public repositories monitored here, where standard GitHub-hosted Actions are not billed by minute.

Metrics intentionally have a slower refresh path than current workflow status. The first successful dashboard run in a UTC day restores the previous snapshot, collects a new 30-day snapshot, and stores it under a date-specific Actions cache key. Later dashboard runs on the same day reuse that snapshot and do not query workflow history again. If the newly collected metric values are identical to the previous snapshot, metrics alone do not force a Pages deployment.

There is no second daily cron for metrics. They piggyback on whichever dashboard run happens first that day: scheduled, manual, or triggered by a dashboard code/configuration change. This is deliberate because the GitHub schedule is best-effort. If no scheduled run occurs, **Rebuild dashboard** also refreshes the daily metrics when that day's snapshot has not yet been collected.

## GitHub Pages setup

After the initial commit:

1. Open **Settings → Pages**.
2. Set **Source** to **GitHub Actions**.
3. Open **Actions → Update Actions dashboard** and run it once with **Run workflow**.

The workflow is scheduled once per hour for 11 minutes past the hour, but GitHub scheduled runs are treated as best-effort rather than as a guaranteed polling interval. After collecting current status it computes a content fingerprint over the dashboard-visible repository state, configuration, generator, and static assets. GitHub Pages is uploaded and deployed only when that fingerprint differs from the currently deployed page, or when the daily Actions metric values changed. The browser checks every minute for a newer deployed copy, updates the visible **Page version checked** value, and reloads automatically when a newer copy appears. **Check for update** performs that page-version check immediately; it does not query the monitored repositories. **Rebuild dashboard** opens the workflow page; when signed in to GitHub, choose **Run workflow** there for an immediate data rebuild. A static GitHub Pages page cannot securely dispatch a workflow directly without exposing credentials or adding a backend.

## Repository access

The initial configuration monitors the public repositories currently present under `brainboxemb`.

For private repositories, add a repository secret named `DASHBOARD_TOKEN`. Prefer a fine-grained personal access token restricted to only the repositories to monitor, with read-only access to Actions and repository metadata. Never put a token in `dashboard.yml`.

## Local development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GITHUB_TOKEN = "..."   # optional, but useful for API rate limits
python src/collect_action_metrics.py --config dashboard.yml --output site/action-metrics.json
python src/generate_dashboard.py
python -m unittest discover -s tests -v
```

Open `site/index.html` in a browser after generation.

## Repository structure

```text
.
├── .github/workflows/deploy-dashboard.yml
├── dashboard.yml
├── requirements.txt
├── src/
│   ├── collect_action_metrics.py
│   └── generate_dashboard.py
├── site/
│   ├── action-metrics.json   # generated/cached, not committed
│   ├── app.js
│   └── style.css
└── tests/
```

## Branch cleanup

The dashboard scans non-default branches and pull requests. A branch is listed in **Branch cleanup** when either:

- the branch still exists after its pull request was closed; or
- the branch still exists and no pull request has ever used that branch in the same repository.

Branches with an open pull request are not cleanup candidates. The default branch and configured long-lived branches in `branch_cleanup_ignore_branches` are also excluded.

Merged PR branches are marked **merged** and are strong cleanup candidates. Branches from closed-but-unmerged PRs are marked **closed, not merged**. Branches with no PR are marked **no pull request**. The latter two categories should be reviewed before deletion. The dashboard never deletes branches automatically.

For future merged PRs, GitHub's repository setting **Automatically delete head branches** can also reduce this cleanup work.

## Repository settings

The **Default branch protected** column reads the `protected` state of each repository's configured/default branch:

- **Protected** — the default branch is covered by GitHub branch protection or a ruleset that GitHub exposes as protected.
- **Not protected** — GitHub reports the default branch as unprotected.
- **Unknown** — the protection state could not be read reliably.

The badge links to the repository's branch settings page. The protection state is observational; this dashboard does not change branch protection rules.

The **PR branch auto-delete** column shows GitHub's `delete_branch_on_merge` repository setting:

- **On** — GitHub automatically deletes the PR head branch after a successful merge.
- **Off** — merged PR branches remain until they are deleted manually.

The badge links to the repository's Settings page.

The dashboard also includes a **Repository settings** shortcut to the `Configure repository settings` workflow. This workflow can enable or disable automatic merged-branch deletion for one configured repository or for all configured repositories.

To use the settings workflow, add a repository secret named `DASHBOARD_ADMIN_TOKEN`. Use a separate fine-grained personal access token restricted to the repositories you want the dashboard to manage, with **Administration: Read and write** repository permission. Keep the existing read-only `DASHBOARD_TOKEN` separate.

Example workflow inputs:

```text
repository: all
delete_branch_on_merge: true
```

or:

```text
repository: tool.scad-project
delete_branch_on_merge: true
```

The settings workflow changes only the `delete_branch_on_merge` property.

## Change-aware Pages deployment

Scheduled checks intentionally separate **data collection** from **Pages deployment**:

1. collect current repository/workflow/PR/branch settings data;
2. restore or, at most once per UTC day, refresh the Actions metrics snapshot;
3. calculate a SHA-256 fingerprint of normal dashboard-visible state and relevant renderer/static files;
4. read the fingerprint embedded in the currently deployed page;
5. skip `configure-pages`, artifact upload, and `deploy-pages` when both fingerprints are equal and the daily metric values are unchanged;
6. deploy a new Pages version only when current dashboard-visible content or the daily metric values changed.

The normal dashboard generation timestamp is deliberately excluded from the fingerprint, so time passing alone never causes a deployment.
