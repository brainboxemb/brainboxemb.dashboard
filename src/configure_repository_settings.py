#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import urllib.error
import urllib.request
from typing import Any

import yaml

API = "https://api.github.com"


def load_config(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def configured_repositories(config: dict[str, Any]) -> list[tuple[str, str]]:
    owner = config.get("dashboard", {}).get("owner")
    if not owner:
        raise ValueError("dashboard.owner is required")

    repositories: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for group in config.get("groups", []):
        for raw in group.get("repositories", []):
            if isinstance(raw, str):
                item_owner, name = owner, raw
            else:
                item_owner = raw.get("owner", owner)
                name = raw.get("name")
            if not name:
                continue
            key = (item_owner, name)
            if key not in seen:
                seen.add(key)
                repositories.append(key)

    return repositories


def patch_repository(owner: str, repo: str, token: str, enabled: bool) -> None:
    payload = json.dumps({"delete_branch_on_merge": enabled}).encode("utf-8")
    request = urllib.request.Request(
        f"{API}/repos/{owner}/{repo}",
        data=payload,
        method="PATCH",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "brainboxemb-dashboard-settings",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{owner}/{repo}: GitHub API {exc.code}: {body[:400]}") from exc

    actual = bool(result.get("delete_branch_on_merge", False))
    if actual != enabled:
        raise RuntimeError(
            f"{owner}/{repo}: requested delete_branch_on_merge={enabled}, "
            f"but GitHub returned {actual}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure repository settings for dashboard-managed repositories"
    )
    parser.add_argument("--config", type=pathlib.Path, default=pathlib.Path("dashboard.yml"))
    parser.add_argument(
        "--repository",
        default="all",
        help="Repository name to change, owner/name, or 'all'",
    )
    parser.add_argument(
        "--delete-branch-on-merge",
        required=True,
        choices=["true", "false"],
    )
    args = parser.parse_args()

    token = os.environ.get("DASHBOARD_ADMIN_TOKEN")
    if not token:
        raise RuntimeError(
            "DASHBOARD_ADMIN_TOKEN is required. Use a fine-grained token with "
            "Administration: write for the selected repositories."
        )

    config = load_config(args.config)
    repositories = configured_repositories(config)
    enabled = args.delete_branch_on_merge == "true"

    if args.repository != "all":
        requested = args.repository
        if "/" in requested:
            owner, name = requested.split("/", 1)
            selected = [(o, r) for o, r in repositories if o == owner and r == name]
        else:
            selected = [(o, r) for o, r in repositories if r == requested]
        if not selected:
            raise ValueError(f"Repository is not configured in dashboard.yml: {requested}")
    else:
        selected = repositories

    action = "enable" if enabled else "disable"
    print(f"Will {action} automatic merged-branch deletion for {len(selected)} repository/repositories.")

    failures: list[str] = []
    for owner, name in selected:
        print(f"Updating {owner}/{name} ...")
        try:
            patch_repository(owner, name, token, enabled)
        except Exception as exc:
            failures.append(str(exc))
            print(f"ERROR: {exc}")
        else:
            print(f"OK: {owner}/{name}")

    if failures:
        raise RuntimeError(
            f"{len(failures)} repository update(s) failed:\n- " + "\n- ".join(failures)
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
