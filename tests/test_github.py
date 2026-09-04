import json
import subprocess
import unittest
from unittest.mock import Mock, patch

from src.github import (
    GitHubError,
    GitHubRelease,
    run_gh,
    run_gh_json,
)


class TestGitHubRelease(unittest.TestCase):

    def test_release_is_immutable(self):
        release = GitHubRelease(
            repository="Neves-P/software-layer",
            tag="eessi-2026.09-poc.1",
            name="EESSI PoC",
            published_at="2026-09-04T12:40:00Z",
            url=(
                "https://github.com/Neves-P/software-layer/"
                "releases/tag/eessi-2026.09-poc.1"
            ),
        )

        with self.assertRaises(AttributeError):
            release.tag = "something-else"


class TestRunGh(unittest.TestCase):

    @patch("src.github.subprocess.run")
    def test_runs_gh_and_returns_stdout(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "version"],
            returncode=0,
            stdout="gh version 2.80.0\n",
            stderr="",
        )

        result = run_gh("version")

        self.assertEqual(
            result,
            "gh version 2.80.0\n",
        )

        mock_run.assert_called_once_with(
            ["gh", "version"],
            capture_output=True,
            text=True,
        )

    @patch("src.github.subprocess.run")
    def test_passes_all_arguments_to_gh(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="[]",
            stderr="",
        )

        run_gh(
            "release",
            "list",
            "--repo",
            "Neves-P/software-layer",
        )

        mock_run.assert_called_once_with(
            [
                "gh",
                "release",
                "list",
                "--repo",
                "Neves-P/software-layer",
            ],
            capture_output=True,
            text=True,
        )

    @patch("src.github.subprocess.run")
    def test_raises_on_nonzero_exit(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[
                "gh",
                "release",
                "view",
                "missing",
            ],
            returncode=1,
            stdout="",
            stderr="release not found",
        )

        with self.assertRaises(GitHubError) as context:
            run_gh(
                "release",
                "view",
                "missing",
            )

        self.assertIn(
            "release not found",
            str(context.exception),
        )

    @patch("src.github.subprocess.run")
    def test_error_contains_command(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[
                "gh",
                "api",
                "repos/example/repo",
            ],
            returncode=1,
            stdout="",
            stderr="boom",
        )

        with self.assertRaises(GitHubError) as context:
            run_gh(
                "api",
                "repos/example/repo",
            )

        self.assertIn(
            "gh api repos/example/repo",
            str(context.exception),
        )


class TestRunGhJson(unittest.TestCase):

    @patch("src.github.run_gh")
    def test_parses_json_object(self, mock_run_gh):
        mock_run_gh.return_value = json.dumps(
            {
                "tagName": "v1.0.0",
            }
        )

        result = run_gh_json(
            "release",
            "view",
            "v1.0.0",
        )

        self.assertEqual(
            result,
            {
                "tagName": "v1.0.0",
            },
        )

    @patch("src.github.run_gh")
    def test_parses_json_list(self, mock_run_gh):
        mock_run_gh.return_value = json.dumps(
            [
                {
                    "tagName": "v1.0.0",
                },
                {
                    "tagName": "v2.0.0",
                },
            ]
        )

        result = run_gh_json(
            "release",
            "list",
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(
            result[1]["tagName"],
            "v2.0.0",
        )

    @patch("src.github.run_gh")
    def test_raises_on_invalid_json(self, mock_run_gh):
        mock_run_gh.return_value = "this is not json"

        with self.assertRaises(GitHubError):
            run_gh_json(
                "release",
                "list",
            )


if __name__ == "__main__":
    unittest.main()