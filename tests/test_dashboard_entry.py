import importlib.util
import os
import pathlib
import sys
import unittest

SRC = pathlib.Path(__file__).parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MODULE = SRC / "dashboard_entry.py"
spec = importlib.util.spec_from_file_location("dashboard_entry", MODULE)
policy = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = policy
spec.loader.exec_module(policy)


class DashboardEntryTests(unittest.TestCase):
    def test_branch_cleanup_ignores_rel_prefix_but_keeps_temporary_branches(self):
        branches = [
            {"name": "main"},
            {"name": "rel/v0.0.2/build"},
            {"name": "rel/v0.0.2/verification"},
            {"name": "chore/orphan"},
            {"name": "temp-release-v0.0.2"},
        ]
        candidates = policy.branch_cleanup_candidates(
            "brainboxemb",
            "repo",
            "main",
            branches,
            [],
            [],
            {"rel/*"},
        )
        self.assertEqual(
            [item["branch"] for item in candidates],
            ["chore/orphan", "temp-release-v0.0.2"],
        )

    def test_active_branch_rules_count_as_protected(self):
        original_request = policy.dashboard.request_json
        original_base = policy._base_fetch_default_branch_protection
        policy.dashboard.request_json = lambda url, token: (
            [{"type": "pull_request"}] if "/rules/branches/" in url else {}
        )
        policy._base_fetch_default_branch_protection = lambda *args: self.fail(
            "active rules should resolve protection without fallback"
        )
        try:
            result = policy.fetch_default_branch_protection(
                "brainboxemb", "repo", "main", "token"
            )
        finally:
            policy.dashboard.request_json = original_request
            policy._base_fetch_default_branch_protection = original_base

        self.assertTrue(result)

    def test_classic_branch_protection_uses_admin_token(self):
        original_request = policy.dashboard.request_json
        original_base = policy._base_fetch_default_branch_protection
        original_admin = os.environ.get("DASHBOARD_ADMIN_TOKEN")
        seen_tokens = []

        def request(url, token):
            seen_tokens.append((url, token))
            if "/rules/branches/" in url:
                return []
            if url.endswith("/protection"):
                return {"url": url}
            raise AssertionError(f"unexpected URL {url}")

        policy.dashboard.request_json = request
        policy._base_fetch_default_branch_protection = lambda *args: self.fail(
            "classic protection should resolve before fallback"
        )
        os.environ["DASHBOARD_ADMIN_TOKEN"] = "admin-token"
        try:
            result = policy.fetch_default_branch_protection(
                "brainboxemb", "repo", "main", "read-token"
            )
        finally:
            policy.dashboard.request_json = original_request
            policy._base_fetch_default_branch_protection = original_base
            if original_admin is None:
                os.environ.pop("DASHBOARD_ADMIN_TOKEN", None)
            else:
                os.environ["DASHBOARD_ADMIN_TOKEN"] = original_admin

        self.assertTrue(result)
        self.assertTrue(
            any(url.endswith("/protection") and token == "admin-token" for url, token in seen_tokens)
        )

    def test_no_active_rules_and_no_classic_protection_is_unprotected(self):
        original_request = policy.dashboard.request_json
        original_base = policy._base_fetch_default_branch_protection
        original_admin = os.environ.get("DASHBOARD_ADMIN_TOKEN")

        def request(url, token):
            if "/rules/branches/" in url:
                return []
            if url.endswith("/protection"):
                raise RuntimeError("GitHub API 404 for protection: not found")
            raise AssertionError(f"unexpected URL {url}")

        policy.dashboard.request_json = request
        policy._base_fetch_default_branch_protection = lambda *args: False
        os.environ["DASHBOARD_ADMIN_TOKEN"] = "admin-token"
        try:
            result = policy.fetch_default_branch_protection(
                "brainboxemb", "repo", "main", "read-token"
            )
        finally:
            policy.dashboard.request_json = original_request
            policy._base_fetch_default_branch_protection = original_base
            if original_admin is None:
                os.environ.pop("DASHBOARD_ADMIN_TOKEN", None)
            else:
                os.environ["DASHBOARD_ADMIN_TOKEN"] = original_admin

        self.assertFalse(result)

    def test_release_uses_latest_run_across_short_lived_request_branch(self):
        original_base = policy._base_fetch_latest_run
        original_request = policy.dashboard.request_json
        policy._base_fetch_latest_run = lambda *args: {
            "name": "Release",
            "path": ".github/workflows/release.yml",
            "head_branch": "main",
            "status": "completed",
            "conclusion": "failure",
        }
        policy.dashboard.request_json = lambda url, token: {
            "workflow_runs": [{
                "name": "Release",
                "path": ".github/workflows/release.yml",
                "head_branch": "release-request/v0.0.2/abc",
                "status": "completed",
                "conclusion": "success",
            }]
        }
        try:
            run = policy.fetch_latest_run("brainboxemb", "repo", 1, "main", None)
        finally:
            policy._base_fetch_latest_run = original_base
            policy.dashboard.request_json = original_request

        self.assertEqual(run["conclusion"], "success")
        self.assertTrue(run["head_branch"].startswith("release-request/"))

    def test_non_release_workflow_stays_on_default_branch(self):
        original_base = policy._base_fetch_latest_run
        original_request = policy.dashboard.request_json
        branch_run = {
            "name": "Build",
            "path": ".github/workflows/build.yml",
            "head_branch": "main",
            "status": "completed",
            "conclusion": "failure",
        }
        policy._base_fetch_latest_run = lambda *args: branch_run
        policy.dashboard.request_json = lambda url, token: self.fail(
            "non-release workflow should not query latest run across all branches"
        )
        try:
            run = policy.fetch_latest_run("brainboxemb", "repo", 1, "main", None)
        finally:
            policy._base_fetch_latest_run = original_base
            policy.dashboard.request_json = original_request

        self.assertIs(run, branch_run)


if __name__ == "__main__":
    unittest.main()
