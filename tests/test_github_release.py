import unittest
from unittest.mock import patch

from src.github import GitHubRelease
from src.github_release import (
    GitHubReleaseError,
    GitHubReleaseNotPublished,
    GitHubReleaseSnapshot,
    get_github_release,
    resolve_commit,
)


REPOSITORY = "Neves-P/software-layer"
TAG = "eessi-2026.09-poc.1"

COMMIT = (
    "0123456789abcdef"
    "0123456789abcdef"
    "01234567"
)

RELEASE_URL = (
    "https://github.com/Neves-P/software-layer/"
    "releases/tag/eessi-2026.09-poc.1"
)


class TestResolveCommit(unittest.TestCase):

    @patch("src.github_release.run_gh_json")
    def test_resolves_tag_to_commit(self, mock_gh):
        mock_gh.return_value = {
            "sha": COMMIT,
        }

        result = resolve_commit(
            REPOSITORY,
            TAG,
        )

        self.assertEqual(
            result,
            COMMIT,
        )

        mock_gh.assert_called_once_with(
            "api",
            (
                "repos/Neves-P/software-layer/"
                "commits/"
                "tags%2Feessi-2026.09-poc.1"
            ),
        )

    @patch("src.github_release.run_gh_json")
    def test_rejects_missing_sha(self, mock_gh):
        mock_gh.return_value = {}

        with self.assertRaises(
            GitHubReleaseError
        ):
            resolve_commit(
                REPOSITORY,
                TAG,
            )

    @patch("src.github_release.run_gh_json")
    def test_rejects_non_mapping_response(
        self,
        mock_gh,
    ):
        mock_gh.return_value = []

        with self.assertRaises(
            GitHubReleaseError
        ):
            resolve_commit(
                REPOSITORY,
                TAG,
            )


class TestGetGithubRelease(unittest.TestCase):

    @patch("src.github_release.resolve_commit")
    @patch("src.github_release.run_gh_json")
    def test_returns_release_snapshot(
        self,
        mock_gh,
        mock_resolve_commit,
    ):
        mock_gh.return_value = {
            "tagName": TAG,
            "name": "EESSI PoC release",
            "publishedAt": "2026-09-04T12:40:00Z",
            "url": RELEASE_URL,
            "isDraft": False,
            "isPrerelease": False,
            "isImmutable": True,
        }

        mock_resolve_commit.return_value = COMMIT

        result = get_github_release(
            REPOSITORY,
            TAG,
        )

        self.assertEqual(
            result,
            GitHubReleaseSnapshot(
                release=GitHubRelease(
                    repository=REPOSITORY,
                    tag=TAG,
                    name="EESSI PoC release",
                    published_at="2026-09-04T12:40:00Z",
                    url=RELEASE_URL,
                ),
                commit=COMMIT,
                is_immutable=True,
            ),
        )

        mock_resolve_commit.assert_called_once_with(
            REPOSITORY,
            TAG,
        )

    @patch("src.github_release.resolve_commit")
    @patch("src.github_release.run_gh_json")
    def test_empty_name_falls_back_to_tag(
        self,
        mock_gh,
        mock_resolve_commit,
    ):
        mock_gh.return_value = {
            "tagName": TAG,
            "name": "",
            "publishedAt": "2026-09-04T12:40:00Z",
            "url": RELEASE_URL,
            "isDraft": False,
            "isPrerelease": False,
            "isImmutable": True,
        }

        mock_resolve_commit.return_value = COMMIT

        result = get_github_release(
            REPOSITORY,
            TAG,
        )

        self.assertEqual(
            result.release.name,
            TAG,
        )

    @patch("src.github_release.run_gh_json")
    def test_rejects_draft(self, mock_gh):
        mock_gh.return_value = {
            "tagName": TAG,
            "name": TAG,
            "publishedAt": None,
            "url": RELEASE_URL,
            "isDraft": True,
            "isPrerelease": False,
        }

        with self.assertRaises(
            GitHubReleaseNotPublished
        ):
            get_github_release(
                REPOSITORY,
                TAG,
            )

    @patch("src.github_release.run_gh_json")
    def test_rejects_prerelease(self, mock_gh):
        mock_gh.return_value = {
            "tagName": TAG,
            "name": TAG,
            "publishedAt": (
                "2026-09-04T12:40:00Z"
            ),
            "url": RELEASE_URL,
            "isDraft": False,
            "isPrerelease": True,
        }

        with self.assertRaises(
            GitHubReleaseNotPublished
        ):
            get_github_release(
                REPOSITORY,
                TAG,
            )

    @patch("src.github_release.run_gh_json")
    def test_rejects_missing_publication_time(
        self,
        mock_gh,
    ):
        mock_gh.return_value = {
            "tagName": TAG,
            "name": TAG,
            "publishedAt": None,
            "url": RELEASE_URL,
            "isDraft": False,
            "isPrerelease": False,
        }

        with self.assertRaises(
            GitHubReleaseNotPublished
        ):
            get_github_release(
                REPOSITORY,
                TAG,
            )

    @patch("src.github_release.run_gh_json")
    def test_rejects_wrong_tag(self, mock_gh):
        mock_gh.return_value = {
            "tagName": "something-else",
            "name": TAG,
            "publishedAt": (
                "2026-09-04T12:40:00Z"
            ),
            "url": RELEASE_URL,
            "isDraft": False,
            "isPrerelease": False,
        }

        with self.assertRaises(
            GitHubReleaseError
        ):
            get_github_release(
                REPOSITORY,
                TAG,
            )

    @patch("src.github_release.run_gh_json")
    def test_rejects_missing_url(self, mock_gh):
        mock_gh.return_value = {
            "tagName": TAG,
            "name": TAG,
            "publishedAt": (
                "2026-09-04T12:40:00Z"
            ),
            "url": None,
            "isDraft": False,
            "isPrerelease": False,
        }

        with self.assertRaises(
            GitHubReleaseError
        ):
            get_github_release(
                REPOSITORY,
                TAG,
            )

    @patch("src.github_release.run_gh_json")
    def test_rejects_non_mapping_response(
        self,
        mock_gh,
    ):
        mock_gh.return_value = []

        with self.assertRaises(
            GitHubReleaseError
        ):
            get_github_release(
                REPOSITORY,
                TAG,
            )


class TestGitHubReleaseSnapshot(unittest.TestCase):

    def test_snapshot_dataclass_is_frozen(self):
        snapshot = GitHubReleaseSnapshot(
            release=GitHubRelease(
                repository=REPOSITORY,
                tag=TAG,
                name=TAG,
                published_at="2026-09-04T12:40:00Z",
                url=RELEASE_URL,
            ),
            commit=COMMIT,
            is_immutable=True,
        )

        with self.assertRaises(
            AttributeError
        ):
            snapshot.commit = "something-else"

    @patch("src.github_release.resolve_commit")
    @patch("src.github_release.run_gh_json")
    def test_reports_release_immutability(
        self,
        mock_gh,
        mock_resolve_commit,
    ):
        mock_gh.return_value = {
            "tagName": TAG,
            "name": TAG,
            "publishedAt": "2026-09-04T12:40:00Z",
            "url": RELEASE_URL,
            "isDraft": False,
            "isPrerelease": False,
            "isImmutable": True,
        }

        mock_resolve_commit.return_value = COMMIT

        result = get_github_release(
            REPOSITORY,
            TAG,
        )

        self.assertTrue(result.is_immutable)

if __name__ == "__main__":
    unittest.main()
