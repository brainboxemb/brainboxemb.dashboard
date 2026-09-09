import datetime as dt
import importlib.util
import pathlib
import sys
import unittest

MODULE = pathlib.Path(__file__).parents[1] / "src" / "generate_dashboard.py"
spec = importlib.util.spec_from_file_location("dashboard", MODULE)
dashboard = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = dashboard
spec.loader.exec_module(dashboard)

class DashboardTests(unittest.TestCase):
    def test_display_state_success(self):
        wf = dashboard.WorkflowStatus("Build", "build.yml", "completed", "success", None, None, "https://example")
        self.assertEqual(wf.display_state, "passing")

    def test_display_state_running(self):
        wf = dashboard.WorkflowStatus("Build", "build.yml", "in_progress", None, None, None, "https://example")
        self.assertEqual(wf.display_state, "running")

    def test_reusable_only_workflow(self):
        source = """name: Reusable\non:\n  workflow_call:\n    inputs:\n      value:\n        type: string\n"""
        self.assertTrue(dashboard.reusable_only_workflow(source))

    def test_reusable_plus_dispatch_is_not_hidden(self):
        source = """name: Mixed\non:\n  workflow_call:\n  workflow_dispatch:\n"""
        self.assertFalse(dashboard.reusable_only_workflow(source))

    def test_pages_workflow_label(self):
        labels = {"pages-build-deployment": "Pages"}
        self.assertEqual(
            dashboard.friendly_workflow_name(
                "dynamic/pages/pages-build-deployment",
                "pages-build-deployment",
                labels,
            ),
            "Pages",
        )

    def test_regular_workflow_is_not_hidden(self):
        source = """name: Build\non:\n  push:\n    branches: [main]\n"""
        self.assertFalse(dashboard.reusable_only_workflow(source))

    def test_branch_auto_delete_graphql_mapping(self):
        original = dashboard.request_graphql
        dashboard.request_graphql = lambda query, token: {
            "r0": {"deleteBranchOnMerge": True},
            "r1": {"deleteBranchOnMerge": False},
        }
        try:
            result = dashboard.fetch_branch_auto_delete_settings(
                [
                    {"owner": "brainboxemb", "name": "one"},
                    {"owner": "brainboxemb", "name": "two"},
                ],
                "token",
            )
        finally:
            dashboard.request_graphql = original

        self.assertEqual(result["brainboxemb/one"], True)
        self.assertEqual(result["brainboxemb/two"], False)

    def test_branch_cleanup_candidates(self):
        branches = [{"name": "main"}, {"name": "feature/merged"}, {"name": "feature/closed"}]
        pulls = [
            {
                "number": 10,
                "title": "Merged work",
                "html_url": "https://example/pr/10",
                "closed_at": "2026-09-08T10:00:00Z",
                "merged_at": "2026-09-08T09:55:00Z",
                "head": {"ref": "feature/merged", "repo": {"full_name": "brainboxemb/repo"}},
            },
            {
                "number": 11,
                "title": "Closed work",
                "html_url": "https://example/pr/11",
                "closed_at": "2026-09-08T11:00:00Z",
                "merged_at": None,
                "head": {"ref": "feature/closed", "repo": {"full_name": "brainboxemb/repo"}},
            },
        ]
        candidates = dashboard.branch_cleanup_candidates(
            "brainboxemb", "repo", "main", branches, pulls
        )
        self.assertEqual([item["branch"] for item in candidates], ["feature/closed", "feature/merged"])
        states = {item["branch"]: item["state"] for item in candidates}
        self.assertEqual(states["feature/merged"], "merged")
        self.assertEqual(states["feature/closed"], "closed")

    def test_branch_cleanup_ignores_deleted_and_fork_branches(self):
        branches = [{"name": "main"}, {"name": "local"}]
        pulls = [
            {
                "number": 12,
                "title": "Fork",
                "closed_at": "2026-09-08T12:00:00Z",
                "merged_at": "2026-09-08T11:00:00Z",
                "head": {"ref": "local", "repo": {"full_name": "someone/fork"}},
            },
            {
                "number": 13,
                "title": "Already deleted",
                "closed_at": "2026-09-08T13:00:00Z",
                "merged_at": "2026-09-08T12:00:00Z",
                "head": {"ref": "gone", "repo": {"full_name": "brainboxemb/repo"}},
            },
        ]
        self.assertEqual(
            dashboard.branch_cleanup_candidates("brainboxemb", "repo", "main", branches, pulls),
            [],
        )

    def test_relative_time(self):
        now = dt.datetime(2026, 9, 9, 12, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(dashboard.relative_time("2026-09-09T10:00:00Z", now), "2h ago")

    def test_relative_time_caps_at_99_days(self):
        now = dt.datetime(2026, 9, 9, 12, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(dashboard.relative_time("2026-07-17T12:00:00Z", now), "54d ago")
        self.assertEqual(dashboard.relative_time("2026-05-01T12:00:00Z", now), ">99d ago")

    def test_dashboard_content_hash_is_stable_and_tracks_visible_state(self):
        config = {"dashboard": {"title": "Test"}, "groups": []}
        wf = dashboard.WorkflowStatus(
            "Build", "build.yml", "completed", "success",
            "https://run", "2026-09-09T10:00:00Z", "https://wf"
        )
        groups = [{
            "name": "Tools",
            "repositories": [{
                "name": "repo",
                "url": "https://repo",
                "branch": "main",
                "latest_tag": None,
                "open_pull_requests": [],
                "pulls_url": "https://repo/pulls",
                "branch_cleanup": [],
                "delete_branch_on_merge": True,
                "settings_url": "https://repo/settings",
                "workflows": [wf],
                "latest": "2026-09-09T10:00:00Z",
            }],
        }]

        first = dashboard.dashboard_content_hash(config, groups)
        second = dashboard.dashboard_content_hash(config, groups)
        self.assertEqual(first, second)

        wf.conclusion = "failure"
        changed = dashboard.dashboard_content_hash(config, groups)
        self.assertNotEqual(first, changed)

    def test_unknown_branch_auto_delete_is_not_counted_as_off(self):
        config = {
            "dashboard": {
                "title": "Test",
                "subtitle": "Status",
                "owner": "brainboxemb",
            }
        }
        groups = [{
            "name": "Tools",
            "repositories": [{
                "name": "repo",
                "url": "https://repo",
                "branch": "main",
                "latest_tag": None,
                "open_pull_requests": [],
                "pulls_url": "https://repo/pulls",
                "delete_branch_on_merge": None,
                "settings_url": "https://repo/settings",
                "branch_cleanup": [],
                "latest": None,
                "workflows": [],
            }],
        }]
        out = dashboard.render_dashboard(
            config,
            groups,
            dt.datetime(2026, 9, 9, 12, 0, tzinfo=dt.timezone.utc),
            "abc",
        )
        self.assertIn(">Unknown</a>", out)
        self.assertIn("<strong>0</strong><span>Auto-delete off</span>", out)

    def test_render_contains_repository_and_status(self):
        config = {"dashboard": {"title": "Test", "subtitle": "Status", "owner": "brainboxemb", "repository": "brainboxemb.dashboard", "refresh_workflow": "deploy-dashboard.yml"}}
        wf = dashboard.WorkflowStatus("Build", "build.yml", "completed", "failure", "https://run", "2026-09-09T10:00:00Z", "https://wf")
        groups = [{"name": "Tools", "repositories": [{"name": "repo", "url": "https://repo", "branch": "main", "latest_tag": {"name": "v1.2.3", "url": "https://tag", "sha": "abc123"}, "open_pull_requests": [{"number": 42, "title": "Improve dashboard"}], "pulls_url": "https://repo/pulls", "delete_branch_on_merge": False, "settings_url": "https://repo/settings", "branch_cleanup": [{"branch": "feature/test", "branch_url": "https://repo/tree/feature/test", "pr_number": 41, "pr_title": "Old branch", "pr_url": "https://repo/pull/41", "state": "merged", "closed_at": "2026-09-08T10:00:00Z", "merged_at": "2026-09-08T09:50:00Z"}], "latest": "2026-09-09T10:00:00Z", "workflows": [wf]}]}]
        generated = dt.datetime(2026, 9, 9, 12, 0, tzinfo=dt.timezone.utc)
        out = dashboard.render_dashboard(config, groups, generated, "abc123")
        self.assertIn("repo", out)
        self.assertIn("failing", out)
        self.assertIn("Problems detected", out)
        self.assertIn("Latest tag", out)
        self.assertIn("v1.2.3", out)
        self.assertIn("Dashboard updated", out)
        self.assertIn("Page version checked", out)
        self.assertIn("Repository check", out)
        self.assertIn("every 15 min", out)
        self.assertIn("refresh-meta__item", out)
        self.assertIn("Rebuild dashboard", out)
        self.assertIn("actions/workflows/deploy-dashboard.yml", out)
        self.assertIn("Open PRs", out)
        self.assertIn("1 open", out)
        self.assertIn("#42: Improve dashboard", out)
        self.assertIn("Branch cleanup", out)
        self.assertIn("feature/test", out)
        self.assertIn("merged", out)
        self.assertIn("PR branch auto-delete", out)
        self.assertIn("Auto-delete off", out)
        self.assertIn(">Off</a>", out)
        self.assertIn("Repository settings", out)
        self.assertIn("data-relative-time", out)
        self.assertIn('datetime="2026-09-09T10:00:00Z"', out)
        self.assertIn("data-dashboard-generated", out)
        self.assertIn('id="last-checked"', out)
        self.assertIn("Check for update", out)
        self.assertIn("Rebuild dashboard", out)
        self.assertIn("app.js?v=", out)
        self.assertIn("style.css?v=", out)
        self.assertIn('class="actions-list"', out)
        self.assertIn('name="dashboard-content-hash" content="abc123"', out)

if __name__ == "__main__":
    unittest.main()
