import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

import yaml

from src.github import GitHubError, GitHubRelease
from src.github_collector import (
    collect_github_pr_metadata,
    collect_github_releases,
    load_config,
    main,
    release_to_metadata,
    repository_from_url,
    write_yaml,
)


REPOSITORY = "Neves-P/software-layer"
REPO_URL = "https://github.com/Neves-P/software-layer"


class TestRepositoryFromUrl(unittest.TestCase):

    def test_extracts_owner_and_repository(self):
        self.assertEqual(
            repository_from_url(
                "https://github.com/Neves-P/software-layer"
            ),
            "Neves-P/software-layer",
        )

    def test_accepts_trailing_slash(self):
        self.assertEqual(
            repository_from_url(
                "https://github.com/Neves-P/software-layer/"
            ),
            "Neves-P/software-layer",
        )

    def test_strips_dot_git(self):
        self.assertEqual(
            repository_from_url(
                "https://github.com/Neves-P/software-layer.git"
            ),
            "Neves-P/software-layer",
        )

    def test_rejects_invalid_url(self):
        with self.assertRaises(ValueError):
            repository_from_url(
                "software-layer"
            )


class TestLoadConfig(unittest.TestCase):

    def test_loads_github_repositories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.yaml"

            path.write_text(
                """
github_repos:
  - https://github.com/Neves-P/software-layer
  - https://github.com/EESSI/filesystem-layer
""",
                encoding="utf-8",
            )

            config = load_config(path)

            self.assertEqual(
                config["github_repos"],
                [
                    (
                        "https://github.com/"
                        "Neves-P/software-layer"
                    ),
                    (
                        "https://github.com/"
                        "EESSI/filesystem-layer"
                    ),
                ],
            )

    def test_rejects_non_mapping_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.yaml"

            path.write_text(
                "- foo\n- bar\n",
                encoding="utf-8",
            )

            with self.assertRaises(TypeError):
                load_config(path)

    def test_rejects_missing_github_repos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.yaml"

            path.write_text(
                "something_else: true\n",
                encoding="utf-8",
            )

            with self.assertRaises(TypeError):
                load_config(path)


class TestCollectGithubPrMetadata(unittest.TestCase):

    @patch(
        "src.github_collector.run_gh_json"
    )
    def test_collects_pull_requests(self, mock_gh):
        mock_gh.return_value = [
            {
                "number": 42,
                "title": "Add foo",
                "labels": [
                    {
                        "name": "enhancement",
                    }
                ],
                "author": {
                    "login": "alice",
                },
                "mergedAt": (
                    "2026-09-01T12:00:00Z"
                ),
                "mergedBy": {
                    "login": "bob",
                },
                "url": (
                    "https://github.com/"
                    "Neves-P/software-layer/"
                    "pull/42"
                ),
            }
        ]

        result = collect_github_pr_metadata(
            REPO_URL
        )

        self.assertEqual(
            result,
            [
                {
                    "number": 42,
                    "title": "Add foo",
                    "labels": [
                        {
                            "name": "enhancement",
                        }
                    ],
                    "author": {
                        "login": "alice",
                    },
                    "merged_at": (
                        "2026-09-01T12:00:00Z"
                    ),
                    "merged_by": {
                        "login": "bob",
                    },
                    "url": (
                        "https://github.com/"
                        "Neves-P/software-layer/"
                        "pull/42"
                    ),
                }
            ],
        )

        mock_gh.assert_called_once_with(
            "pr",
            "list",
            "--repo",
            REPOSITORY,
            "--state",
            "merged",
            "--json",
            (
                "number,title,labels,author,"
                "mergedAt,mergedBy,url"
            ),
            "--limit",
            "2000",
        )

    @patch(
        "src.github_collector.run_gh_json"
    )
    def test_rejects_unexpected_pr_response(
        self,
        mock_gh,
    ):
        mock_gh.return_value = {
            "unexpected": "object"
        }

        with self.assertRaises(GitHubError):
            collect_github_pr_metadata(
                REPO_URL
            )


class TestCollectGithubReleases(unittest.TestCase):

    @patch(
        "src.github_collector.run_gh_json"
    )
    def test_collects_releases(self, mock_gh):
        mock_gh.return_value = [
            {
                "tagName": "v1.0.0",
                "name": "Version 1",
                "publishedAt": (
                    "2026-08-01T12:00:00Z"
                ),
                "url": (
                    "https://github.com/"
                    "Neves-P/software-layer/"
                    "releases/tag/v1.0.0"
                ),
            },
            {
                "tagName": "v2.0.0",
                "name": "",
                "publishedAt": (
                    "2026-09-01T12:00:00Z"
                ),
                "url": (
                    "https://github.com/"
                    "Neves-P/software-layer/"
                    "releases/tag/v2.0.0"
                ),
            },
        ]

        result = collect_github_releases(
            REPO_URL
        )

        self.assertEqual(len(result), 2)

        self.assertEqual(
            result[0],
            GitHubRelease(
                repository=REPOSITORY,
                tag="v1.0.0",
                name="Version 1",
                published_at=(
                    "2026-08-01T12:00:00Z"
                ),
                url=(
                    "https://github.com/"
                    "Neves-P/software-layer/"
                    "releases/tag/v1.0.0"
                ),
            ),
        )

        # Empty GitHub release names fall back
        # to the tag.
        self.assertEqual(
            result[1].name,
            "v2.0.0",
        )

    @patch(
        "src.github_collector.run_gh_json"
    )
    def test_rejects_unexpected_release_response(
        self,
        mock_gh,
    ):
        mock_gh.return_value = {
            "not": "a list"
        }

        with self.assertRaises(GitHubError):
            collect_github_releases(
                REPO_URL
            )


class TestReleaseToMetadata(unittest.TestCase):

    def test_preserves_existing_metadata_schema(self):
        release = GitHubRelease(
            repository=REPOSITORY,
            tag="v1.0.0",
            name="Version 1",
            published_at="2026-09-01T12:00:00Z",
            url=(
                "https://github.com/"
                "Neves-P/software-layer/"
                "releases/tag/v1.0.0"
            ),
        )

        self.assertEqual(
            release_to_metadata(release),
            {
                "tag": "v1.0.0",
                "name": "Version 1",
                "published_at": (
                    "2026-09-01T12:00:00Z"
                ),
            },
        )


class TestWriteYaml(unittest.TestCase):

    def test_creates_parent_directories_and_writes_yaml(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = (
                Path(tmpdir)
                / "nested"
                / "metadata.yaml"
            )

            data = [
                {
                    "tag": "v1.0.0",
                    "name": "Version 1",
                }
            ]

            write_yaml(
                path,
                data,
            )

            self.assertTrue(path.exists())

            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                loaded = yaml.safe_load(file)

            self.assertEqual(
                loaded,
                data,
            )

class TestMain(unittest.TestCase):

    @patch("src.github_collector.write_yaml")
    @patch("src.github_collector.collect_github_releases")
    @patch("src.github_collector.collect_github_pr_metadata")
    @patch("src.github_collector.load_config")
    def test_collects_and_writes_both_metadata_types(
        self,
        mock_load_config,
        mock_collect_prs,
        mock_collect_releases,
        mock_write_yaml,
    ):
        mock_load_config.return_value = {
            "github_repos": [
                REPO_URL,
            ]
        }

        mock_collect_prs.return_value = [
            {
                "number": 42,
                "title": "Add foo",
            }
        ]

        mock_collect_releases.return_value = [
            GitHubRelease(
                repository=REPOSITORY,
                tag="v1.0.0",
                name="Version 1",
                published_at="2026-09-01T12:00:00Z",
                url=(
                    "https://github.com/"
                    "Neves-P/software-layer/"
                    "releases/tag/v1.0.0"
                ),
            )
        ]

        main()

        mock_collect_prs.assert_called_once_with(
            REPO_URL
        )

        mock_collect_releases.assert_called_once_with(
            REPO_URL
        )

        self.assertEqual(
            mock_write_yaml.call_count,
            2,
        )

        first_write = mock_write_yaml.call_args_list[0]
        second_write = mock_write_yaml.call_args_list[1]

        pr_data = first_write.args[1]
        release_data = second_write.args[1]

        self.assertEqual(
            pr_data,
            [
                {
                    "number": 42,
                    "title": "Add foo",
                }
            ],
        )

        self.assertEqual(
            release_data,
            [
                {
                    "tag": "v1.0.0",
                    "name": "Version 1",
                    "published_at": "2026-09-01T12:00:00Z",
                }
            ],
        )



if __name__ == "__main__":
    unittest.main()
