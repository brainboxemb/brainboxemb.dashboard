# Changelog

## Unreleased

- Add 30-day Actions performance metrics from workflow run history, refreshed at most once per UTC day through a date-keyed cache; unchanged metrics do not force a Pages deployment.
- Include non-default branches that have never had a pull request in **Branch cleanup**, while ignoring configured long-lived publication/output branches.
- Keep `Last activity` relative through 99 days, show `>99d ago` beyond that, and show the exact date on hover without a time.
- Read PR branch auto-delete settings through GitHub GraphQL and show `Unknown` instead of incorrectly reporting `Off` when the setting cannot be read.
- Keep Actions cells as normal table cells so row separators align across all columns, and label the synthetic GitHub Pages workflow simply as `Pages`.
- Skip GitHub Pages deployment when the dashboard fingerprint is unchanged; scheduled data checks now run once per hour at minute 11.
- Clarify that the browser freshness check only checks for a newer deployed page, not live repository data.
- Auto-check every minute for a newly deployed dashboard and cache-bust static assets.
- Update relative activity timestamps live in the browser on the static dashboard.
- Show and manage the automatic deletion of merged pull-request branches per repository.
- Show branch cleanup candidates when closed pull request branches still exist.
- Hide reusable-only workflows that are invoked exclusively through `workflow_call`.
- Show open pull request counts per repository with links to the PR list.
- Show the dashboard refresh timestamp at the top in browser-local time.
- Add a shortcut to manually run the dashboard workflow.
- Group repositories without active Actions in a separate section at the bottom.
- Show configured repositories even when they have no active workflows.
- Show the latest Git tag for each monitored repository.

## v0.1.0 - 2026-09-09

- Initial static GitHub Actions dashboard.
- Repository grouping through `dashboard.yml`.
- Automatic workflow discovery.
- Default-branch run status.
- GitHub Pages deployment.
- Search and problems-only filter.
- Responsive light/dark styling.
- Unit tests for status mapping and rendering.
