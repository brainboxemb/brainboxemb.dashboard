#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

import yaml

API = "https://api.github.com"

@dataclass
class WorkflowStatus:
    name: str
    path: str
    state: str
    conclusion: str | None
    run_url: str | None
    updated_at: str | None
    workflow_url: str

    @property
    def display_state(self) -> str:
        if self.state in {"queued", "in_progress", "waiting", "requested", "pending"}:
            return "running"
        if self.conclusion == "success":
            return "passing"
        if self.conclusion in {"failure", "timed_out", "startup_failure"}:
            return "failing"
        if self.conclusion == "cancelled":
            return "cancelled"
        if self.conclusion in {"neutral", "skipped", "action_required", "stale"}:
            return "neutral"
        return "no-status"

def load_config(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "dashboard" not in data or "groups" not in data:
        raise ValueError("dashboard.yml must contain 'dashboard' and 'groups'")
    return data

def request_json(url: str, token: str | None) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "brainboxemb-actions-dashboard",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {exc.code} for {url}: {body[:300]}") from exc

def normalize_repo_entry(entry: str | dict[str, Any], owner: str) -> dict[str, Any]:
    if isinstance(entry, str):
        return {"name": entry, "owner": owner}
    result = dict(entry)
    result.setdefault("owner", owner)
    if not result.get("name"):
        raise ValueError(f"Repository entry is missing a name: {entry!r}")
    return result

def workflow_key(path: str, name: str) -> str:
    stem = pathlib.PurePosixPath(path).stem.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    return cleaned or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

def friendly_workflow_name(path: str, name: str, labels: dict[str, str]) -> str:
    stem = pathlib.PurePosixPath(path).stem
    for candidate in [stem, stem.lower(), workflow_key(path, name), name, name.lower()]:
        if candidate in labels:
            return labels[candidate]
    return name

def fetch_repository(owner: str, repo: str, token: str | None) -> dict[str, Any]:
    return request_json(f"{API}/repos/{owner}/{repo}", token)

def fetch_latest_tag(owner: str, repo: str, token: str | None) -> dict[str, str] | None:
    tags = request_json(f"{API}/repos/{owner}/{repo}/tags?per_page=1", token)
    if not tags:
        return None
    tag = tags[0]
    name = tag.get("name")
    if not name:
        return None
    return {
        "name": name,
        "sha": (tag.get("commit") or {}).get("sha", ""),
        "url": f"https://github.com/{owner}/{repo}/tree/{urllib.parse.quote(name, safe='')}",
    }

def fetch_open_pull_requests(owner: str, repo: str, token: str | None) -> list[dict[str, Any]]:
    pulls: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = request_json(
            f"{API}/repos/{owner}/{repo}/pulls?state=open&per_page=100&page={page}",
            token,
        )
        pulls.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return pulls

def fetch_workflow_source(owner: str, repo: str, path: str, branch: str, token: str | None) -> str:
    quoted_path = urllib.parse.quote(path, safe="/")
    query = urllib.parse.urlencode({"ref": branch})
    data = request_json(f"{API}/repos/{owner}/{repo}/contents/{quoted_path}?{query}", token)
    content = data.get("content")
    if not content:
        return ""
    import base64
    return base64.b64decode(content).decode("utf-8")

def reusable_only_workflow(source: str) -> bool:
    """Return True when the workflow can only be invoked through workflow_call."""
    lines = source.splitlines()
    on_index = None
    inline_value = ""

    for index, line in enumerate(lines):
        match = re.match(r"^(?:on|['\"]on['\"])\s*:\s*(.*?)\s*$", line)
        if match:
            on_index = index
            inline_value = match.group(1).strip()
            break

    if on_index is None:
        return False

    if inline_value:
        normalized = inline_value.strip("[] ").replace('"', "").replace("'", "")
        triggers = {item.strip() for item in normalized.split(",") if item.strip()}
        return triggers == {"workflow_call"}

    triggers: set[str] = set()
    for line in lines[on_index + 1:]:
        if line and not line[0].isspace() and not line.lstrip().startswith("#"):
            break
        match = re.match(r"^\s{2}([A-Za-z_][A-Za-z0-9_-]*)\s*:", line)
        if match:
            triggers.add(match.group(1))

    return triggers == {"workflow_call"}

def fetch_workflows(owner: str, repo: str, token: str | None) -> list[dict[str, Any]]:
    return request_json(f"{API}/repos/{owner}/{repo}/actions/workflows?per_page=100", token).get("workflows", [])

def fetch_latest_run(owner: str, repo: str, workflow_id: int, branch: str, token: str | None) -> dict[str, Any] | None:
    query = urllib.parse.urlencode({"branch": branch, "per_page": 1})
    runs = request_json(f"{API}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs?{query}", token).get("workflow_runs", [])
    return runs[0] if runs else None

def collect_repository(entry: dict[str, Any], config: dict[str, Any], token: str | None) -> dict[str, Any]:
    owner, repo = entry["owner"], entry["name"]
    meta = fetch_repository(owner, repo, token)
    branch = entry.get("branch") or meta.get("default_branch") or "main"
    latest_tag = fetch_latest_tag(owner, repo, token)
    open_pull_requests = fetch_open_pull_requests(owner, repo, token)
    workflows = fetch_workflows(owner, repo, token)
    show_disabled = bool(config["dashboard"].get("show_disabled_workflows", False))
    hide_reusable = bool(entry.get(
        "hide_reusable_only_workflows",
        config["dashboard"].get("hide_reusable_only_workflows", True),
    ))
    include = set(entry.get("include_workflows", []))
    exclude = set(entry.get("exclude_workflows", []))
    labels = {**config.get("workflow_labels", {}), **entry.get("workflow_labels", {})}
    results: list[WorkflowStatus] = []

    for wf in workflows:
        path = wf.get("path", "")
        name = wf.get("name") or pathlib.PurePosixPath(path).stem
        state = wf.get("state") or "unknown"
        file_name = pathlib.PurePosixPath(path).name
        key = workflow_key(path, name)
        if not show_disabled and state != "active":
            continue
        if include and not ({path, file_name, key, name} & include):
            continue
        if {path, file_name, key, name} & exclude:
            continue
        if hide_reusable:
            try:
                source = fetch_workflow_source(owner, repo, path, branch, token)
                if reusable_only_workflow(source):
                    continue
            except Exception as exc:
                print(
                    f"WARNING: could not inspect workflow triggers for {owner}/{repo}:{path}: {exc}",
                    file=sys.stderr,
                )
        if not wf.get("id"):
            continue
        run = fetch_latest_run(owner, repo, int(wf["id"]), branch, token)
        results.append(WorkflowStatus(
            name=friendly_workflow_name(path, name, labels),
            path=path,
            state=(run or {}).get("status") or ("disabled" if state != "active" else "unknown"),
            conclusion=(run or {}).get("conclusion"),
            run_url=(run or {}).get("html_url"),
            updated_at=(run or {}).get("updated_at"),
            workflow_url=wf.get("html_url") or f"https://github.com/{owner}/{repo}/actions",
        ))

    results.sort(key=lambda item: item.name.lower())
    latest = max((w.updated_at for w in results if w.updated_at), default=None)
    return {
        "name": repo,
        "url": meta.get("html_url") or f"https://github.com/{owner}/{repo}",
        "branch": branch,
        "latest_tag": latest_tag,
        "open_pull_requests": open_pull_requests,
        "pulls_url": f"https://github.com/{owner}/{repo}/pulls",
        "workflows": results,
        "latest": latest,
    }

def status_counts(groups: list[dict[str, Any]]) -> dict[str, int]:
    counts = {k: 0 for k in ["passing", "failing", "running", "cancelled", "neutral", "no-status"]}
    for group in groups:
        for repo in group["repositories"]:
            for wf in repo["workflows"]:
                counts[wf.display_state] += 1
    return counts

def relative_time(value: str | None, now: dt.datetime | None = None) -> str:
    if not value:
        return "—"
    now = now or dt.datetime.now(dt.timezone.utc)
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    seconds = max(0, int((now - parsed).total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago" if days < 30 else parsed.strftime("%Y-%m-%d")

def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)

def render_workflow(wf: WorkflowStatus) -> str:
    state = wf.display_state
    label = {"passing":"passing","failing":"failing","running":"running","cancelled":"cancelled","neutral":"neutral","no-status":"no status"}[state]
    target = wf.run_url or wf.workflow_url
    return (
        f'<a class="workflow workflow--{state}" href="{esc(target)}" title="{esc(wf.name)} — {label}" target="_blank" rel="noopener">'
        f'<span class="workflow__icon" aria-hidden="true">◆</span>'
        f'<span class="workflow__name">{esc(wf.name)}</span>'
        f'<span class="workflow__state">{label}</span></a>'
    )

def render_dashboard(config: dict[str, Any], groups: list[dict[str, Any]], generated_at: dt.datetime) -> str:
    dcfg = config["dashboard"]
    counts = status_counts(groups)
    repo_count = sum(len(g["repositories"]) for g in groups)
    workflow_count = sum(len(r["workflows"]) for g in groups for r in g["repositories"])
    open_pr_count = sum(len(r.get("open_pull_requests", [])) for g in groups for r in g["repositories"])
    unhealthy = counts["failing"] + counts["cancelled"]
    summary = [
        ("Repositories", repo_count, "summary--neutral"),
        ("Workflows", workflow_count, "summary--neutral"),
        ("Passing", counts["passing"], "summary--passing"),
        ("Failing", counts["failing"], "summary--failing" if counts["failing"] else "summary--neutral"),
        ("Running", counts["running"], "summary--running" if counts["running"] else "summary--neutral"),
        ("Open PRs", open_pr_count, "summary--prs" if open_pr_count else "summary--neutral"),
    ]
    summary_html = "".join(f'<div class="summary {klass}"><strong>{value}</strong><span>{esc(label)}</span></div>' for label,value,klass in summary)

    show_latest_tag = bool(dcfg.get("show_latest_tag", True))
    show_open_pull_requests = bool(dcfg.get("show_open_pull_requests", True))
    sections = []
    for group in groups:
        rows = []
        for repo in group["repositories"]:
            workflow_html = "".join(render_workflow(w) for w in repo["workflows"]) or '<span class="empty">No workflows</span>'
            problem = any(w.display_state in {"failing","cancelled"} for w in repo["workflows"])
            tag = repo.get("latest_tag")
            tag_html = (
                f'<a class="tag" href="{esc(tag["url"])}" title="{esc(tag.get("sha", ""))}" target="_blank" rel="noopener">{esc(tag["name"])}</a>'
                if tag else '<span class="empty">No tags</span>'
            )
            pulls = repo.get("open_pull_requests", [])
            pull_count = len(pulls)
            pull_titles = " | ".join(
                f'#{pull.get("number")}: {pull.get("title", "")}' for pull in pulls[:8]
            )
            pr_html = (
                f'<a class="pr-badge" href="{esc(repo.get("pulls_url", repo["url"] + "/pulls"))}" '
                f'title="{esc(pull_titles or "Open pull requests")}" target="_blank" rel="noopener">'
                f'{pull_count} open</a>'
                if pull_count else '<span class="empty">—</span>'
            )
            search_parts = [repo["name"], *(w.name for w in repo["workflows"])]
            if tag:
                search_parts.append(tag["name"])
            search_parts.extend(
                f'pr {pull.get("number")} {pull.get("title", "")}' for pull in pulls
            )
            search_text = " ".join(search_parts).lower()
            rows.append(
                f'<tr class="repo-row{" repo--problem" if problem else ""}" data-problem="{str(problem).lower()}" data-search="{esc(search_text)}">'
                f'<td class="repo-cell"><a href="{esc(repo["url"])}" target="_blank" rel="noopener">{esc(repo["name"])}</a><div class="repo-meta">{esc(repo["branch"])}</div></td>'
                + (f'<td class="tag-cell">{tag_html}</td>' if show_latest_tag else '')
                + (f'<td class="pr-cell">{pr_html}</td>' if show_open_pull_requests else '')
                + f'<td class="actions-cell">{workflow_html}</td>'
                f'<td class="activity-cell" title="{esc(repo["latest"] or "")}">{esc(relative_time(repo["latest"], generated_at))}</td></tr>'
            )
        sections.append(
            f'<section class="group"><h2>{esc(group["name"])}</h2><div class="table-wrap"><table>'
            '<thead><tr><th>Repo</th>'
            + ('<th>Latest tag</th>' if show_latest_tag else '')
            + ('<th>Open PRs</th>' if show_open_pull_requests else '')
            + '<th>Actions</th><th>Last activity</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></section>'
        )

    generated_iso = generated_at.replace(microsecond=0).isoformat().replace("+00:00","Z")
    dashboard_repo = dcfg.get("repository")
    refresh_workflow = dcfg.get("refresh_workflow", "deploy-dashboard.yml")
    refresh_url = (
        f"https://github.com/{dcfg.get('owner')}/{dashboard_repo}/actions/workflows/{refresh_workflow}"
        if dcfg.get("owner") and dashboard_repo else None
    )
    health = "Problems detected" if unhealthy else "All monitored workflows healthy"
    health_class = "health--problem" if unhealthy else "health--ok"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>{esc(dcfg.get("title","GitHub Actions Dashboard"))}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
<main class="page">
  <header class="hero">
    <div class="hero-copy">
      <h1>{esc(dcfg.get("title","GitHub Actions Dashboard"))}</h1>
      <p>{esc(dcfg.get("subtitle",""))}</p>
      <div class="refresh-meta">Last refreshed <time class="local-time" data-local-time datetime="{generated_iso}">{generated_iso}</time></div>
    </div>
    <div class="hero-actions">
      <div class="health {health_class}">{health}</div>
      {f'<a class="refresh-button" href="{esc(refresh_url)}" target="_blank" rel="noopener" title="Open the GitHub Actions workflow and choose Run workflow">Refresh dashboard ↗</a>' if refresh_url else ''}
    </div>
  </header>
  <section class="summary-grid">{summary_html}</section>
  <section class="toolbar" aria-label="Dashboard filters">
    <label class="search"><span>Search</span><input id="search" type="search" placeholder="Repository or workflow…"></label>
    <label class="toggle"><input id="problems-only" type="checkbox"><span>Problems only</span></label>
  </section>
  <div id="groups">{"".join(sections)}</div>
  <footer>Generated <time class="local-time" data-local-time datetime="{generated_iso}">{generated_iso}</time> · Static GitHub Pages dashboard</footer>
</main>
<script src="app.js"></script>
</body>
</html>
"""

def collect(config: dict[str, Any], token: str | None) -> list[dict[str, Any]]:
    owner = config["dashboard"].get("owner")
    if not owner:
        raise ValueError("dashboard.owner is required")

    dcfg = config["dashboard"]
    hide_empty = bool(dcfg.get("hide_repositories_without_workflows", False))
    separate_empty = bool(dcfg.get("separate_repositories_without_workflows", True))
    empty_group_name = dcfg.get("repositories_without_workflows_group", "Repositories without Actions")

    groups = []
    repositories_without_workflows = []

    for group_cfg in config["groups"]:
        repositories = []
        for raw in group_cfg.get("repositories", []):
            entry = normalize_repo_entry(raw, owner)
            print(f"Collecting {entry['owner']}/{entry['name']}…", file=sys.stderr)
            try:
                repo = collect_repository(entry, config, token)
            except Exception as exc:
                print(f"WARNING: {entry['owner']}/{entry['name']}: {exc}", file=sys.stderr)
                continue

            if not repo["workflows"]:
                if hide_empty:
                    continue
                if separate_empty:
                    repositories_without_workflows.append(repo)
                    continue

            repositories.append(repo)

        if repositories:
            groups.append({"name": group_cfg.get("name","Repositories"), "repositories": repositories})

    if repositories_without_workflows:
        groups.append({
            "name": empty_group_name,
            "repositories": repositories_without_workflows,
        })

    return groups

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a static GitHub Actions status dashboard")
    parser.add_argument("--config", default="dashboard.yml", type=pathlib.Path)
    parser.add_argument("--output", default="site/index.html", type=pathlib.Path)
    args = parser.parse_args()
    config = load_config(args.config)
    token = os.environ.get("DASHBOARD_TOKEN") or os.environ.get("GITHUB_TOKEN")
    groups = collect(config, token)
    generated_at = dt.datetime.now(dt.timezone.utc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_dashboard(config, groups, generated_at), encoding="utf-8")
    print(f"Wrote {args.output} with {sum(len(g['repositories']) for g in groups)} repositories", file=sys.stderr)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
