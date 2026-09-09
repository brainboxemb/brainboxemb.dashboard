# Changelog

## Unreleased

- Read PR branch auto-delete settings through GitHub GraphQL and show `Unknown` instead of incorrectly reporting `Off` when the setting cannot be read.
- Keep Actions cells as normal table cells so row separators align across all columns, and label the synthetic GitHub Pages workflow simply as `Pages`.
- Skip GitHub Pages deployment when the dashboard fingerprint is unchanged; scheduled data checks still run every 15 minutes.
- Clarify that the browser freshness check only checks for a newer deployed page, not live repository data.
- Rebuild the dashboard every 15 minutes and show a live Last checked timestamp in the browser.
- Auto-check every minute for a newly deployed dashboard and cache-bust static assets.
- Update relative activity timestamps live in the browser on the static dashboard.
- Show and manage the automatic deletion of merged pull-request branches per repository.
- Show branch cleanup candidates when closed pull request branches still exist.
- Hide reusable-only workflows that are invoked exclusively through `workflow_call`.
- Show open pull request counts per repository with links to the PR list.
- Show the dashboard refresh timestamp at the top in browser-local time.
- Add a shortcut to manually run the dashboard workflow.
- Refresh the dashboard automatically every four hours.
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
