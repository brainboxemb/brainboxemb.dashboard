# brainboxemb.dashboard

Central GitHub Actions status dashboard for brainboxemb repositories.

The dashboard is generated as a static site and published with GitHub Pages. It has no server, database, Azure dependency, or JavaScript framework.

## What it shows

- repositories grouped by purpose;
- active GitHub Actions workflows discovered automatically;
- status of the most recent run on each repository's default branch;
- direct links to repositories and workflow runs;
- latest Git tag per repository, linked to the tagged tree;
- last activity per repository;
- summary counts for passing, failing, and running workflows;
- search and **Problems only** filtering;
- responsive light/dark styling.

Repositories with no active workflows are hidden by default. The **Latest tag** column can be disabled with `dashboard.show_latest_tag: false`.

## Configuration

Edit [`dashboard.yml`](dashboard.yml). A repository can be listed by name:

```yaml
- docker.scad-toolchain
```

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

`include_workflows` and `exclude_workflows` accept a workflow path, filename, normalized filename stem, or GitHub workflow name.

## GitHub Pages setup

After the initial commit:

1. Open **Settings → Pages**.
2. Set **Source** to **GitHub Actions**.
3. Open **Actions → Update Actions dashboard** and run it once with **Run workflow**.

The scheduled workflow refreshes the dashboard once per hour.

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
