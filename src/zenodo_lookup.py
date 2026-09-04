from dataclasses import asdict, dataclass
import argparse
import json
import time

import requests


SANDBOX_API_URL = "https://sandbox.zenodo.org/api"
PRODUCTION_API_URL = "https://zenodo.org/api"


class ZenodoLookupError(RuntimeError):
    """Base exception for Zenodo lookup failures."""


class ZenodoRecordNotFound(ZenodoLookupError):
    """No Zenodo record matched the requested GitHub release."""


class ZenodoAmbiguousMatch(ZenodoLookupError):
    """More than one Zenodo record matched the requested GitHub release."""

class ZenodoLookupTimeout(ZenodoLookupError):
    """Timed out waiting for a Zenodo record to appear."""

@dataclass(frozen=True)
class ZenodoRecord:
    """Information about a published Zenodo record."""

    record_id: int
    doi: str
    concept_doi: str | None
    version: str | None
    github_release_url: str


def github_release_url(repository: str, tag: str) -> str:
    """Return the GitHub tree URL used by the Zenodo GitHub integration."""

    return f"https://github.com/{repository}/tree/{tag}"


def _extract_hits(payload: object) -> list[dict]:
    """Extract record hits from a Zenodo search response.

    Zenodo API response formats have changed over time, so accept both the
    common ``{"hits": {"hits": [...]}}`` form and a plain list.
    """

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        hits = payload.get("hits", {})

        if isinstance(hits, dict):
            records = hits.get("hits", [])
            if isinstance(records, list):
                return records

    raise ZenodoLookupError("Unexpected response format from Zenodo")


def _related_identifiers(record: dict) -> list[str]:
    """Return all related identifier values from a Zenodo record."""

    metadata = record.get("metadata", {})
    related = metadata.get("related_identifiers", [])

    return [
        item["identifier"]
        for item in related
        if isinstance(item, dict) and "identifier" in item
    ]


def _get_doi(record: dict) -> str | None:
    """Extract a version-specific DOI from a Zenodo record."""

    if record.get("doi"):
        return record["doi"]

    # Also tolerate the newer InvenioRDM-style representation.
    return (
        record.get("pids", {})
        .get("doi", {})
        .get("identifier")
    )


def _get_concept_doi(record: dict) -> str | None:
    """Extract the concept DOI from a Zenodo record."""

    if record.get("conceptdoi"):
        return record["conceptdoi"]

    # Also tolerate the newer InvenioRDM-style representation.
    return (
        record.get("parent", {})
        .get("pids", {})
        .get("doi", {})
        .get("identifier")
    )


def find_github_release(
    repository: str,
    tag: str,
    *,
    sandbox: bool = True,
    timeout: int = 30,
) -> ZenodoRecord:
    """Find the Zenodo record corresponding to a GitHub release tag."""

    api_url = SANDBOX_API_URL if sandbox else PRODUCTION_API_URL
    release_url = github_release_url(repository, tag)

    query = f'related.identifier:"{release_url}"'

    response = requests.get(
        f"{api_url}/records",
        params={
            "q": query,
            "all_versions": "true",
            "size": 25,
        },
        timeout=timeout,
    )
    response.raise_for_status()

    hits = _extract_hits(response.json())

    # Do not trust the search result alone. Verify the exact GitHub URL.
    matches = [
        record
        for record in hits
        if release_url in _related_identifiers(record)
    ]

    if not matches:
        raise ZenodoRecordNotFound(
            f"No Zenodo record found for {repository} tag {tag}"
        )

    if len(matches) > 1:
        raise ZenodoAmbiguousMatch(
            f"Found {len(matches)} Zenodo records for "
            f"{repository} tag {tag}"
        )

    record = matches[0]
    doi = _get_doi(record)

    if doi is None:
        raise ZenodoLookupError(
            f"Zenodo record {record.get('id')} has no DOI"
        )

    return ZenodoRecord(
        record_id=int(record["id"]),
        doi=doi,
        concept_doi=_get_concept_doi(record),
        version=record.get("metadata", {}).get("version"),
        github_release_url=release_url,
    )

def wait_for_github_release(
    repository: str,
    tag: str,
    *,
    sandbox: bool = True,
    timeout: int = 600,
    poll_interval: int = 10,
) -> ZenodoRecord:
    """Wait for Zenodo to publish the record for a GitHub release.

    Only ZenodoRecordNotFound is considered retryable.

    Other errors, such as ambiguous matches, malformed responses, HTTP
    failures, or records without a DOI, are propagated immediately.
    """

    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    if poll_interval <= 0:
        raise ValueError("poll_interval must be greater than zero")

    deadline = time.monotonic() + timeout

    while True:
        try:
            return find_github_release(
                repository,
                tag,
                sandbox=sandbox,
            )

        except ZenodoRecordNotFound as exc:
            remaining = deadline - time.monotonic()

            if remaining <= 0:
                raise ZenodoLookupTimeout(
                    f"Timed out after {timeout} seconds waiting for "
                    f"Zenodo record for {repository} tag {tag}"
                ) from exc

            time.sleep(min(poll_interval, remaining))

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find the Zenodo record for a GitHub release."
    )
    parser.add_argument(
        "repository",
        help="GitHub repository in OWNER/REPO form",
    )
    parser.add_argument(
        "tag",
        help="GitHub release tag",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Query production Zenodo instead of Zenodo Sandbox",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for Zenodo to ingest the GitHub release",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Maximum seconds to wait (default: 600)",
    )

    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Seconds between lookup attempts (default: 10)",
    )

    args = parser.parse_args()

    lookup = (
        wait_for_github_release
        if args.wait
        else find_github_release
    )

    lookup_kwargs = {
        "sandbox": not args.production,
    }

    if args.wait:
        lookup_kwargs.update(
            timeout=args.timeout,
            poll_interval=args.poll_interval,
        )

    record = lookup(
        args.repository,
        args.tag,
        **lookup_kwargs,
    )

    print(json.dumps(asdict(record), indent=2))


if __name__ == "__main__":
    main()
