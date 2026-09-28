import unittest
from typing import Optional
from unittest.mock import patch

from eessi_revisions.component_release import (
    ComponentRelease,
    ComponentReleaseMismatch,
    ComponentReleaseMissingConceptDOI,
    ComponentReleaseMissingDOI,
    combine_component_release,
    get_component_release,
    wait_for_component_release,
)
from eessi_revisions.github import GitHubRelease
from eessi_revisions.github_release import (
    GitHubReleaseError,
    GitHubReleaseSnapshot,
)
from eessi_revisions.zenodo_lookup import (
    ZenodoAmbiguousMatch,
    ZenodoRecord,
)

REPOSITORY = "Neves-P/software-layer"
TAG = "eessi-2026.09-poc.1"
COMMIT = (
    "0123456789abcdef"
    "0123456789abcdef"
    "01234567"
)
GITHUB_RELEASE_URL = (
    "https://github.com/Neves-P/software-layer/"
    "releases/tag/eessi-2026.09-poc.1"
)
ZENODO_RELATED_IDENTIFIER = (
    "https://github.com/Neves-P/software-layer/"
    "tree/eessi-2026.09-poc.1"
)
DOI = "10.5072/zenodo.598123"
CONCEPT_DOI = "10.5072/zenodo.598122"


def make_github_snapshot(
    *,
    is_immutable: bool = True,
) -> GitHubReleaseSnapshot:
    return GitHubReleaseSnapshot(
        release=GitHubRelease(
            repository=REPOSITORY,
            tag=TAG,
            name="EESSI PoC release",
            published_at="2026-09-04T12:40:00Z",
            url=GITHUB_RELEASE_URL,
        ),
        commit=COMMIT,
        is_immutable=is_immutable,
    )


def make_zenodo_record(
    *,
    doi: str = DOI,
    concept_doi: Optional[str] = CONCEPT_DOI,
    version: Optional[str] = TAG,
    related_identifier: str = ZENODO_RELATED_IDENTIFIER,
) -> ZenodoRecord:
    return ZenodoRecord(
        record_id=598123,
        doi=doi,
        concept_doi=concept_doi,
        version=version,
        github_release_url=related_identifier,
    )


class TestCombineComponentRelease(unittest.TestCase):

    def test_combines_matching_provenance(self):
        result = combine_component_release(
            make_github_snapshot(),
            make_zenodo_record(),
        )

        self.assertEqual(
            result,
            ComponentRelease(
                repository=REPOSITORY,
                tag=TAG,
                commit=COMMIT,
                github_release_url=GITHUB_RELEASE_URL,
                is_immutable=True,
                doi=DOI,
                concept_doi=CONCEPT_DOI,
            ),
        )

    def test_component_release_is_frozen(self):
        release = combine_component_release(
            make_github_snapshot(),
            make_zenodo_record(),
        )

        with self.assertRaises(AttributeError):
            release.commit = (  # pyright: ignore[reportAttributeAccessIssue]
                "something-else"
            )

    def test_preserves_mutable_release_status(self):
        result = combine_component_release(
            make_github_snapshot(is_immutable=False),
            make_zenodo_record(),
        )

        self.assertFalse(result.is_immutable)

    def test_rejects_mismatched_related_identifier(self):
        invalid_identifiers = (
            (
                "https://github.com/Neves-P/software-layer/"
                "tree/something-else"
            ),
            (
                "https://github.com/EESSI/software-layer/"
                "tree/eessi-2026.09-poc.1"
            ),
            GITHUB_RELEASE_URL,
        )

        for identifier in invalid_identifiers:
            with self.subTest(identifier=identifier), self.assertRaises(
                ComponentReleaseMismatch
            ):
                combine_component_release(
                    make_github_snapshot(),
                    make_zenodo_record(
                        related_identifier=identifier
                    ),
                )

    def test_rejects_missing_version_doi(self):
        for doi in ("", "   "):
            with self.subTest(doi=doi), self.assertRaises(
                ComponentReleaseMissingDOI
            ):
                combine_component_release(
                    make_github_snapshot(),
                    make_zenodo_record(doi=doi),
                )

    def test_rejects_missing_concept_doi(self):
        for concept_doi in (None, "", "   "):
            with self.subTest(
                concept_doi=concept_doi
            ), self.assertRaises(
                ComponentReleaseMissingConceptDOI
            ):
                combine_component_release(
                    make_github_snapshot(),
                    make_zenodo_record(
                        concept_doi=concept_doi
                    ),
                )

    def test_does_not_use_zenodo_version_as_identity(self):
        result = combine_component_release(
            make_github_snapshot(),
            make_zenodo_record(version="different-version-text"),
        )

        self.assertEqual(result.tag, TAG)


class TestGetComponentRelease(unittest.TestCase):

    @patch(
        "eessi_revisions.component_release.find_github_release"
    )
    @patch(
        "eessi_revisions.component_release.get_github_release"
    )
    def test_resolves_one_shot_release(
        self,
        mock_get_github,
        mock_find_zenodo,
    ):
        mock_get_github.return_value = make_github_snapshot()
        mock_find_zenodo.return_value = make_zenodo_record()

        result = get_component_release(
            REPOSITORY,
            TAG,
            sandbox=False,
        )

        self.assertEqual(result.doi, DOI)
        mock_get_github.assert_called_once_with(REPOSITORY, TAG)
        mock_find_zenodo.assert_called_once_with(
            REPOSITORY,
            TAG,
            sandbox=False,
        )

    @patch(
        "eessi_revisions.component_release.get_github_release"
    )
    def test_propagates_github_errors(self, mock_get_github):
        error = GitHubReleaseError("GitHub failed")
        mock_get_github.side_effect = error

        with self.assertRaises(GitHubReleaseError) as context:
            get_component_release(REPOSITORY, TAG)

        self.assertIs(context.exception, error)

    @patch(
        "eessi_revisions.component_release.find_github_release"
    )
    @patch(
        "eessi_revisions.component_release.get_github_release"
    )
    def test_propagates_zenodo_errors(
        self,
        mock_get_github,
        mock_find_zenodo,
    ):
        error = ZenodoAmbiguousMatch("multiple records")
        mock_get_github.return_value = make_github_snapshot()
        mock_find_zenodo.side_effect = error

        with self.assertRaises(ZenodoAmbiguousMatch) as context:
            get_component_release(REPOSITORY, TAG)

        self.assertIs(context.exception, error)


class TestWaitForComponentRelease(unittest.TestCase):

    @patch(
        "eessi_revisions.component_release.wait_for_github_release"
    )
    @patch(
        "eessi_revisions.component_release.get_github_release"
    )
    def test_waits_for_zenodo_release(
        self,
        mock_get_github,
        mock_wait_zenodo,
    ):
        mock_get_github.return_value = make_github_snapshot()
        mock_wait_zenodo.return_value = make_zenodo_record()

        result = wait_for_component_release(
            REPOSITORY,
            TAG,
            sandbox=False,
            timeout=120,
            poll_interval=5,
        )

        self.assertEqual(result.concept_doi, CONCEPT_DOI)
        mock_get_github.assert_called_once_with(REPOSITORY, TAG)
        mock_wait_zenodo.assert_called_once_with(
            REPOSITORY,
            TAG,
            sandbox=False,
            timeout=120,
            poll_interval=5,
        )

    @patch(
        "eessi_revisions.component_release.wait_for_github_release"
    )
    @patch(
        "eessi_revisions.component_release.get_github_release"
    )
    def test_propagates_github_errors(
        self,
        mock_get_github,
        mock_wait_zenodo,
    ):
        error = GitHubReleaseError("GitHub failed")
        mock_get_github.side_effect = error

        with self.assertRaises(GitHubReleaseError) as context:
            wait_for_component_release(REPOSITORY, TAG)

        self.assertIs(context.exception, error)
        mock_wait_zenodo.assert_not_called()

    @patch(
        "eessi_revisions.component_release.wait_for_github_release"
    )
    @patch(
        "eessi_revisions.component_release.get_github_release"
    )
    def test_propagates_zenodo_errors(
        self,
        mock_get_github,
        mock_wait_zenodo,
    ):
        error = ZenodoAmbiguousMatch("multiple records")
        mock_get_github.return_value = make_github_snapshot()
        mock_wait_zenodo.side_effect = error

        with self.assertRaises(ZenodoAmbiguousMatch) as context:
            wait_for_component_release(REPOSITORY, TAG)

        self.assertIs(context.exception, error)


if __name__ == "__main__":
    unittest.main()
