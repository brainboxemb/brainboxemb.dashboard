#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import urllib.parse
from typing import Any

import generate_dashboard as dashboard

# Keep policy that depends on brainboxemb's repository conventions out of the
# generic dashboard collector itself. The entry point installs these policies
# before calling generate_dashboard.main().
_base_branch_cleanup_candidates = dashboard.branch_cleanup_candidates
_base_fetch_latest_run = dashboard.fetch_latest_run


def branch_cleanup_candidates(
    owner: str,
    repo: str,
    default_branch: str,
    branches: list[dict[str, Any]],
    closed_pulls: list[dict[str, Any]],
    open_pulls: list[dict[str, Any]] | None = None,
    ignored_branches: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Apply exact and prefix-style cleanup exclusions.

    Existing dashboard configuration remains exact-match by default. Entries
    ending in ``*`` are treated as prefixes, so ``rel/*`` excludes all release
    output branches while temporary branches such as ``release-request/...``
    remain visible as cleanup candidates.
    """
    ignored = set(ignored_branches or set())
    prefixes = tuple(value[:-1] for value in ignored if value.endswith("*"))
    exact = {value for value in ignored if not value.endswith("*")}

    candidates = _base_branch_cleanup_candidates(
        owner,
        repo,
        default_branch,
        branches,
        closed_pulls,
        open_pulls,
        exact,
    )
    if not prefixes:
        return candidates
    return [
        candidate
        for candidate in candidates
        if not str(candidate.get("branch") or "").startswith(prefixes)
    ]


def _is_release_run(run: dict[str, Any] | None) -> bool:
    if not run:
        return False
    path = str(run.get("path") or "")
    name = str(run.get("name") or "")
    return pathlib.PurePosixPath(path).name.lower() == "release.yml" or name.lower() == "release"


def fetch_latest_run(
    owner: str,
    repo: str,
    workflow_id: int,
    branch: str,
    token: str | None,
) -> dict[str, Any] | None:
    """Use default-branch status normally, but latest run overall for Release.

    Release requests run on short-lived ``release-request/...`` branches. A
    default-branch filter therefore reports an older Release run and can leave
    the dashboard red even after a newer successful release. Other workflows
    keep their default-branch status so pull-request/feature runs do not affect
    repository health.
    """
    branch_run = _base_fetch_latest_run(owner, repo, workflow_id, branch, token)
    if branch_run is not None and not _is_release_run(branch_run):
        return branch_run

    query = urllib.parse.urlencode({"per_page": 1})
    runs = dashboard.request_json(
        f"{dashboard.API}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs?{query}",
        token,
    ).get("workflow_runs", [])
    latest = runs[0] if runs else None

    if _is_release_run(latest):
        return latest
    return branch_run


def install_policy() -> None:
    dashboard.branch_cleanup_candidates = branch_cleanup_candidates
    dashboard.fetch_latest_run = fetch_latest_run


def main() -> int:
    install_policy()
    return dashboard.main()


if __name__ == "__main__":
    raise SystemExit(main())
