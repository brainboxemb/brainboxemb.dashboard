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

    def test_relative_time(self):
        now = dt.datetime(2026, 9, 9, 12, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(dashboard.relative_time("2026-09-09T10:00:00Z", now), "2h ago")

    def test_render_contains_repository_and_status(self):
        config = {"dashboard": {"title": "Test", "subtitle": "Status"}}
        wf = dashboard.WorkflowStatus("Build", "build.yml", "completed", "failure", "https://run", "2026-09-09T10:00:00Z", "https://wf")
        groups = [{"name": "Tools", "repositories": [{"name": "repo", "url": "https://repo", "branch": "main", "latest_tag": {"name": "v1.2.3", "url": "https://tag", "sha": "abc123"}, "latest": "2026-09-09T10:00:00Z", "workflows": [wf]}]}]
        generated = dt.datetime(2026, 9, 9, 12, 0, tzinfo=dt.timezone.utc)
        out = dashboard.render_dashboard(config, groups, generated)
        self.assertIn("repo", out)
        self.assertIn("failing", out)
        self.assertIn("Problems detected", out)
        self.assertIn("Latest tag", out)
        self.assertIn("v1.2.3", out)

if __name__ == "__main__":
    unittest.main()
