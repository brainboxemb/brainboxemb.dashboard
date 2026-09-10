#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.parse
from collections import defaultdict
from typing import Any

SRC_DIR = pathlib.Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import generate_dashboard as dashboard

FAIL_CONCLUSIONS = {"failure", "timed_out", "startup_failure"}


def parse_timestamp(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    success = 0
    failed = 0
    cancelled = 0
    other = 0
    runtime_seconds: list[float] = []
    queue_seconds: list[float] = []

    for run in runs:
        conclusion = run.get("conclusion")
        if conclusion == "success":
            success += 1
        elif conclusion in FAIL_CONCLUSIONS:
            failed += 1
        elif conclusion == "cancelled":
            cancelled += 1
        else:
            other += 1

        created = parse_timestamp(run.get("created_at"))
        started = parse_timestamp(run.get("run_started_at"))
        updated = parse_timestamp(run.get("updated_at"))

        if created and started:
            queue_seconds.append(max(0.0, (started - created).total_seconds()))
        if run.get("status") == "completed" and started and updated:
            runtime_seconds.append(max(0.0, (updated - started).total_seconds()))

    decided = success + failed
    return {
        "runs": len(runs),
        "success": success,
        "failed": failed,
        "cancelled": cancelled,
        "other": other,
        "success_rate": round(success * 100.0 / decided, 1) if decided else None,
        "runtime_seconds": round(sum(runtime_seconds)),
        "avg_runtime_seconds": round(sum(runtime_seconds) / len(runtime_seconds), 1) if runtime_seconds else None,
        "avg_queue_seconds": round(sum(queue_seconds) / len(queue_seconds), 1) if queue_seconds else None,
    }


def request_json_with_retry(url: str, token: str | None) -> Any:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return dashboard.request_json(url, token)
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
    assert last_error is not None
    raise last_error


def fetch_recent_runs(
    owner: str,
    repo: str,
    token: str | None,
    cutoff: dt.datetime,
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    page = 1

    while True:
        query = urllib.parse.urlencode({"per_page": 100, "page": page})
        data = request_json_with_retry(
            f"{dashboard.API}/repos/{owner}/{repo}/actions/runs?{query}", token
        )
        batch = data.get("workflow_runs", [])
        if not batch:
            break

        reached_cutoff = False
        for run in batch:
            created = parse_timestamp(run.get("created_at"))
            if created and created < cutoff:
                reached_cutoff = True
                break
            runs.append(run)

        if reached_cutoff or len(batch) < 100:
            break
        page += 1

    return runs


def configured_repositories(config: dict[str, Any]) -> list[dict[str, Any]]:
    owner = config["dashboard"].get("owner")
    if not owner:
        raise ValueError("dashboard.owner is required")

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in config.get("groups", []):
        for raw in group.get("repositories", []):
            entry = dashboard.normalize_repo_entry(raw, owner)
            key = f"{entry['owner']}/{entry['name']}"
            if key not in seen:
                seen.add(key)
                result.append(entry)
    return result


def snapshot_state(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return only metric values that should trigger a Pages update."""
    if not snapshot:
        return None
    return {
        "window_days": snapshot.get("window_days"),
        "summary": snapshot.get("summary"),
        "repositories": snapshot.get("repositories"),
        "workflows": snapshot.get("workflows"),
    }


def build_snapshot(
    config: dict[str, Any],
    token: str | None,
    now: dt.datetime | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    now = now or dt.datetime.now(dt.timezone.utc)
    window_days = int(config["dashboard"].get("action_metrics_days", 30))
    cutoff = now - dt.timedelta(days=window_days)
    all_runs: list[dict[str, Any]] = []
    repositories: list[dict[str, Any]] = []
    workflow_runs: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    workflow_info: dict[tuple[str, str], dict[str, Any]] = {}
    errors: list[str] = []

    for entry in configured_repositories(config):
        owner = str(entry["owner"])
        repo = str(entry["name"])
        print(f"Collecting Actions metrics for {owner}/{repo}…", file=sys.stderr)
        try:
            runs = fetch_recent_runs(owner, repo, token, cutoff)
        except Exception as exc:
            errors.append(f"{owner}/{repo}: {exc}")
            continue

        all_runs.extend(runs)
        repo_stats = summarize_runs(runs)
        repositories.append({
            "name": repo,
            "url": f"https://github.com/{owner}/{repo}/actions",
            **repo_stats,
        })

        for run in runs:
            workflow_id = run.get("workflow_id")
            path = run.get("path") or ""
            name = run.get("name") or pathlib.PurePosixPath(path).stem or "Workflow"
            identity = str(workflow_id or path or name)
            key = (repo, identity)
            workflow_runs[key].append(run)
            workflow_info[key] = {
                "repository": repo,
                "name": name,
                "path": path,
                "url": (
                    f"https://github.com/{owner}/{repo}/actions/workflows/{workflow_id}"
                    if workflow_id
                    else f"https://github.com/{owner}/{repo}/actions"
                ),
            }

    if errors:
        return None, errors

    workflows = []
    for key, runs in workflow_runs.items():
        workflows.append({**workflow_info[key], **summarize_runs(runs)})

    repositories.sort(key=lambda item: (-item["runtime_seconds"], item["name"].lower()))
    workflows.sort(
        key=lambda item: (
            -item["runtime_seconds"],
            item["repository"].lower(),
            item["name"].lower(),
        )
    )

    return {
        "generated_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "window_days": window_days,
        "period_start": cutoff.date().isoformat(),
        "period_end": now.date().isoformat(),
        "source": "workflow-runs",
        "summary": summarize_runs(all_runs),
        "repositories": repositories,
        "workflows": workflows,
    }, []


def write_flag(path: pathlib.Path | None, value: bool) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(("true" if value else "false") + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect daily GitHub Actions performance metrics from workflow run history"
    )
    parser.add_argument("--config", default="dashboard.yml", type=pathlib.Path)
    parser.add_argument("--output", default="site/action-metrics.json", type=pathlib.Path)
    parser.add_argument("--changed-output", type=pathlib.Path)
    parser.add_argument("--valid-output", type=pathlib.Path)
    args = parser.parse_args()

    config = dashboard.load_config(args.config)
    token = os.environ.get("DASHBOARD_TOKEN") or os.environ.get("GITHUB_TOKEN")

    previous: dict[str, Any] | None = None
    if args.output.exists():
        try:
            previous = json.loads(args.output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = None

    snapshot, errors = build_snapshot(config, token)
    if errors or snapshot is None:
        for error in errors:
            print(f"WARNING: Actions metrics: {error}", file=sys.stderr)
        print(
            "Actions metrics snapshot not replaced; a later dashboard run can retry.",
            file=sys.stderr,
        )
        write_flag(args.changed_output, False)
        write_flag(args.valid_output, False)
        return 0

    changed = snapshot_state(previous) != snapshot_state(snapshot)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_flag(args.changed_output, changed)
    write_flag(args.valid_output, True)

    print(
        f"Wrote {args.output}: {snapshot['summary']['runs']} runs across "
        f"{len(snapshot['repositories'])} repositories; changed={str(changed).lower()}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
