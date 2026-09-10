# brainboxemb.dashboard

Central GitHub Actions status dashboard for brainboxemb repositories.

The dashboard is generated as a static site and published with GitHub Pages. It has no server, database, Azure dependency, or JavaScript framework.

## What it shows

- repositories grouped by purpose;
- active GitHub Actions workflows discovered automatically;
- reusable-only workflows (`workflow_call` without a normal trigger) hidden automatically;
- status of the most recent run on each repository's default branch;
- direct links to repositories and workflow runs;
- latest Git tag per repository, linked to the tagged tree;
- open pull request count per repository, linked to the repository's PR list;
- branch cleanup candidates for closed pull requests whose source branch still exists;
- branch auto-delete setting (`delete_branch_on_merge`) per repository;
- last activity per repository; relative activity timestamps update in the browser without rebuilding the static page;
- summary counts for passing, failing, and running workflows;
- search and **Problems only** filtering;
- responsive light/dark styling;
- data-generation timestamp shown at the top in the viewer's local time;
- visible **Page version checked** timestamp updated when the browser checks whether a newer deployed dashboard page exists;
- checks every minute for a newly deployed dashboard and reloads automatically when one is available;
- manual refresh shortcut to the GitHub Actions workflow.

Repositories without active workflows remain visible, but are collected in a separate **Repositories without Actions** section at the bottom. This keeps the main groups focused on repositories with workflow status while still giving a complete overview. The **Latest tag** column can be disabled with `dashboard.show_latest_tag: false`, the **Open PRs** column with `dashboard.show_open_pull_requests: false`, branch cleanup scanning with `dashboard.show_branch_cleanup: false`, and the **PR branch auto-delete** column with `dashboard.show_branch_auto_delete: false`.

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

## GitHub Pages setup

After the initial commit:

1. Open **Settings → Pages**.
2. Set **Source** to **GitHub Actions**.
3. Open **Actions → Update Actions dashboard** and run it once with **Run workflow**.

The scheduled workflow checks GitHub once per hour, scheduled for 11 minutes past the hour. GitHub may still delay scheduled runs. After collecting the data it computes a content fingerprint over the dashboard-visible repository state, configuration, generator, and static assets. GitHub Pages is uploaded and deployed only when that fingerprint differs from the currently deployed page. The browser checks every minute for a newer deployed copy, updates the visible **Page version checked** value, and reloads automatically when a newer copy appears. **Check for update** performs that page-version check immediately; it does not query the monitored repositories. **Rebuild dashboard** opens the workflow page; when signed in to GitHub, choose **Run workflow** there for an immediate data rebuild. A static GitHub Pages page cannot securely dispatch a workflow directly without exposing credentials or adding a backend.

## Repository access

The initial configuration monitors the public repositories currently present under `brainboxemb`.

For private repositories, add a repository secret named `DASHBOARD_TOKEN`. Prefer a fine-grained personal access token restricted to only the repositories to monitor, with read-only access to Actions and repository metadata. Never put a token in `dashboard.yml`.

## Local development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GITHUB_TOKEN = "..."   # optional, but useful for API rate limits
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
├── src/generate_dashboard.py
├── site/
│   ├── app.js
│   └── style.css
└── tests/test_dashboard.py
```


## Branch cleanup

The dashboard scans non-default branches and closed pull requests. A branch is listed in **Branch cleanup** when:

- the branch still exists in the same repository;
- its pull request is closed;
- the branch is not the default branch.

Merged PR branches are marked **merged** and are strong cleanup candidates. Branches from closed-but-unmerged PRs are marked **closed, not merged** and should be reviewed before deletion. The dashboard never deletes branches automatically; the PR link takes you to GitHub, where the branch can be removed after review.

For future merged PRs, GitHub's repository setting **Automatically delete head branches** can also reduce this cleanup work.


## Repository settings

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

1. collect repository/workflow/PR/branch settings data;
2. calculate a SHA-256 fingerprint of dashboard-visible state and relevant renderer/static files;
3. read the fingerprint embedded in the currently deployed page;
4. skip `configure-pages`, artifact upload, and `deploy-pages` when both fingerprints are equal;
5. deploy a new Pages version only when dashboard-visible content changed.

The generation timestamp is deliberately excluded from the fingerprint, so time passing alone never causes a deployment.
