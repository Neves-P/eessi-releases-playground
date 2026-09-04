import unittest
from unittest.mock import Mock, patch

from src.zenodo_lookup import (
    ZenodoAmbiguousMatch,
    ZenodoLookupError,
    ZenodoLookupTimeout,
    ZenodoRecord,
    ZenodoRecordNotFound,
    find_github_release,
    github_release_url,
    wait_for_github_release,
)


REPOSITORY = "Neves-P/software-layer"
TAG = "eessi-2026.09-poc.1"
RELEASE_URL = (
    "https://github.com/Neves-P/software-layer/"
    "tree/eessi-2026.09-poc.1"
)


def make_record(
    record_id=598123,
    doi="10.5072/zenodo.598123",
    concept_doi="10.5072/zenodo.598122",
    version=TAG,
    related_identifier=RELEASE_URL,
):
    return {
        "id": record_id,
        "doi": doi,
        "conceptdoi": concept_doi,
        "metadata": {
            "version": version,
            "related_identifiers": [
                {
                    "identifier": related_identifier,
                    "relation": "issupplementto",
                }
            ],
        },
    }


def make_response(records):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "hits": {
            "hits": records,
        }
    }
    return response


class TestGithubReleaseUrl(unittest.TestCase):

    def test_builds_expected_url(self):
        self.assertEqual(
            github_release_url(REPOSITORY, TAG),
            RELEASE_URL,
        )


class TestFindGithubRelease(unittest.TestCase):

    @patch("src.zenodo_lookup.requests.get")
    def test_finds_matching_record(self, mock_get):
        mock_get.return_value = make_response(
            [make_record()]
        )

        record = find_github_release(
            REPOSITORY,
            TAG,
        )

        self.assertEqual(record.record_id, 598123)
        self.assertEqual(
            record.doi,
            "10.5072/zenodo.598123",
        )
        self.assertEqual(
            record.concept_doi,
            "10.5072/zenodo.598122",
        )
        self.assertEqual(
            record.version,
            TAG,
        )
        self.assertEqual(
            record.github_release_url,
            RELEASE_URL,
        )

    @patch("src.zenodo_lookup.requests.get")
    def test_uses_exact_related_identifier(self, mock_get):
        other_record = make_record(
            record_id=123,
            doi="10.5072/zenodo.123",
            related_identifier=(
                "https://github.com/Neves-P/software-layer/"
                "tree/eessi-2026.08-poc.1"
            ),
        )

        matching_record = make_record()

        mock_get.return_value = make_response(
            [
                other_record,
                matching_record,
            ]
        )

        record = find_github_release(
            REPOSITORY,
            TAG,
        )

        self.assertEqual(record.record_id, 598123)

    @patch("src.zenodo_lookup.requests.get")
    def test_raises_if_no_record_exists(self, mock_get):
        mock_get.return_value = make_response([])

        with self.assertRaises(ZenodoRecordNotFound):
            find_github_release(
                REPOSITORY,
                TAG,
            )

    @patch("src.zenodo_lookup.requests.get")
    def test_raises_if_search_result_does_not_match_exact_url(
        self,
        mock_get,
    ):
        mock_get.return_value = make_response(
            [
                make_record(
                    related_identifier=(
                        "https://github.com/Neves-P/"
                        "software-layer/tree/something-else"
                    )
                )
            ]
        )

        with self.assertRaises(ZenodoRecordNotFound):
            find_github_release(
                REPOSITORY,
                TAG,
            )

    @patch("src.zenodo_lookup.requests.get")
    def test_raises_on_ambiguous_match(self, mock_get):
        mock_get.return_value = make_response(
            [
                make_record(record_id=1),
                make_record(
                    record_id=2,
                    doi="10.5072/zenodo.2",
                ),
            ]
        )

        with self.assertRaises(ZenodoAmbiguousMatch):
            find_github_release(
                REPOSITORY,
                TAG,
            )

    @patch("src.zenodo_lookup.requests.get")
    def test_raises_if_record_has_no_doi(self, mock_get):
        record = make_record()
        record.pop("doi")

        mock_get.return_value = make_response(
            [record]
        )

        with self.assertRaises(ZenodoLookupError):
            find_github_release(
                REPOSITORY,
                TAG,
            )

    @patch("src.zenodo_lookup.requests.get")
    def test_queries_sandbox_by_default(self, mock_get):
        mock_get.return_value = make_response(
            [make_record()]
        )

        find_github_release(
            REPOSITORY,
            TAG,
        )

        mock_get.assert_called_once()

        url = mock_get.call_args.args[0]
        params = mock_get.call_args.kwargs["params"]

        self.assertEqual(
            url,
            "https://sandbox.zenodo.org/api/records",
        )
        self.assertEqual(
            params["q"],
            f'related.identifier:"{RELEASE_URL}"',
        )
        self.assertEqual(
            params["all_versions"],
            "true",
        )

    @patch("src.zenodo_lookup.requests.get")
    def test_can_query_production(self, mock_get):
        mock_get.return_value = make_response(
            [make_record()]
        )

        find_github_release(
            REPOSITORY,
            TAG,
            sandbox=False,
        )

        url = mock_get.call_args.args[0]

        self.assertEqual(
            url,
            "https://zenodo.org/api/records",
        )

class TestWaitForGithubRelease(unittest.TestCase):

    @patch("src.zenodo_lookup.find_github_release")
    def test_returns_immediately_if_record_exists(self, mock_find):
        expected = ZenodoRecord(
            record_id=598123,
            doi="10.5072/zenodo.598123",
            concept_doi="10.5072/zenodo.598122",
            version=TAG,
            github_release_url=RELEASE_URL,
        )
        mock_find.return_value = expected

        result = wait_for_github_release(
            REPOSITORY,
            TAG,
            timeout=60,
            poll_interval=1,
        )

        self.assertEqual(result, expected)
        mock_find.assert_called_once_with(
            REPOSITORY,
            TAG,
            sandbox=True,
        )

    @patch("src.zenodo_lookup.time.sleep")
    @patch("src.zenodo_lookup.find_github_release")
    def test_retries_not_found(
        self,
        mock_find,
        mock_sleep,
    ):
        expected = ZenodoRecord(
            record_id=598123,
            doi="10.5072/zenodo.598123",
            concept_doi="10.5072/zenodo.598122",
            version=TAG,
            github_release_url=RELEASE_URL,
        )

        mock_find.side_effect = [
            ZenodoRecordNotFound("not yet"),
            ZenodoRecordNotFound("still not yet"),
            expected,
        ]

        result = wait_for_github_release(
            REPOSITORY,
            TAG,
            timeout=60,
            poll_interval=1,
        )

        self.assertEqual(result, expected)
        self.assertEqual(mock_find.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("src.zenodo_lookup.time.sleep")
    @patch("src.zenodo_lookup.time.monotonic")
    @patch("src.zenodo_lookup.find_github_release")
    def test_times_out(
        self,
        mock_find,
        mock_monotonic,
        mock_sleep,
    ):
        mock_find.side_effect = ZenodoRecordNotFound("not yet")

        mock_monotonic.side_effect = [
            100.0,  # deadline calculation
            110.0,  # first retry check
        ]

        with self.assertRaises(ZenodoLookupTimeout):
            wait_for_github_release(
                REPOSITORY,
                TAG,
                timeout=10,
                poll_interval=1,
            )

        mock_sleep.assert_not_called()

    @patch("src.zenodo_lookup.find_github_release")
    def test_does_not_retry_ambiguous_match(self, mock_find):
        mock_find.side_effect = ZenodoAmbiguousMatch(
            "multiple records"
        )

        with self.assertRaises(ZenodoAmbiguousMatch):
            wait_for_github_release(
                REPOSITORY,
                TAG,
            )

        mock_find.assert_called_once()

    @patch("src.zenodo_lookup.find_github_release")
    def test_does_not_retry_other_lookup_errors(self, mock_find):
        mock_find.side_effect = ZenodoLookupError(
            "bad response"
        )

        with self.assertRaises(ZenodoLookupError):
            wait_for_github_release(
                REPOSITORY,
                TAG,
            )

        mock_find.assert_called_once()

    def test_rejects_zero_timeout(self):
        with self.assertRaises(ValueError):
            wait_for_github_release(
                REPOSITORY,
                TAG,
                timeout=0,
            )

    def test_rejects_zero_poll_interval(self):
        with self.assertRaises(ValueError):
            wait_for_github_release(
                REPOSITORY,
                TAG,
                poll_interval=0,
            )

if __name__ == "__main__":
    unittest.main()
