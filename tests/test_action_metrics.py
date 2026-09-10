import datetime as dt
import importlib.util
import pathlib
import sys
import unittest

MODULE = pathlib.Path(__file__).parents[1] / "src" / "collect_action_metrics.py"
spec = importlib.util.spec_from_file_location("action_metrics", MODULE)
action_metrics = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = action_metrics
spec.loader.exec_module(action_metrics)


class ActionMetricsTests(unittest.TestCase):
    def test_summarize_runs(self):
        runs = [
            {
                "status": "completed",
                "conclusion": "success",
                "created_at": "2026-09-10T10:00:00Z",
                "run_started_at": "2026-09-10T10:02:00Z",
                "updated_at": "2026-09-10T10:12:00Z",
            },
            {
                "status": "completed",
                "conclusion": "failure",
                "created_at": "2026-09-10T11:00:00Z",
                "run_started_at": "2026-09-10T11:01:00Z",
                "updated_at": "2026-09-10T11:06:00Z",
            },
        ]

        metrics = action_metrics.summarize_runs(runs)
        self.assertEqual(metrics["runs"], 2)
        self.assertEqual(metrics["success"], 1)
        self.assertEqual(metrics["failed"], 1)
        self.assertEqual(metrics["cancelled"], 0)
        self.assertEqual(metrics["success_rate"], 50.0)
        self.assertEqual(metrics["runtime_seconds"], 900)
        self.assertEqual(metrics["avg_runtime_seconds"], 450.0)
        self.assertEqual(metrics["avg_queue_seconds"], 90.0)

    def test_snapshot_state_ignores_collection_timestamp(self):
        base = {
            "generated_at": "2026-09-09T12:00:00Z",
            "period_start": "2026-08-10",
            "period_end": "2026-09-09",
            "window_days": 30,
            "summary": {"runs": 1},
            "repositories": [{"name": "repo", "runs": 1}],
            "workflows": [{"name": "Build", "runs": 1}],
        }
        newer = dict(base)
        newer["generated_at"] = "2026-09-10T12:00:00Z"
        newer["period_start"] = "2026-08-11"
        newer["period_end"] = "2026-09-10"
        self.assertEqual(
            action_metrics.snapshot_state(base),
            action_metrics.snapshot_state(newer),
        )

    def test_configured_repositories_are_deduplicated(self):
        config = {
            "dashboard": {"owner": "brainboxemb"},
            "groups": [
                {"repositories": ["one", "two"]},
                {"repositories": ["one"]},
            ],
        }
        repositories = action_metrics.configured_repositories(config)
        self.assertEqual(
            [(item["owner"], item["name"]) for item in repositories],
            [("brainboxemb", "one"), ("brainboxemb", "two")],
        )


if __name__ == "__main__":
    unittest.main()
