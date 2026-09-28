from dataclasses import dataclass

from .github_release import GitHubReleaseSnapshot, get_github_release
from .zenodo_lookup import (
    ZenodoRecord,
    find_github_release,
    github_release_url,
    wait_for_github_release,
)


class ComponentReleaseError(RuntimeError):
    """Base exception for component release provenance failures."""


class ComponentReleaseMismatch(ComponentReleaseError):
    """GitHub and Zenodo metadata identify different releases."""


class ComponentReleaseMissingDOI(ComponentReleaseError):
    """The Zenodo record has no usable version DOI."""


class ComponentReleaseMissingConceptDOI(ComponentReleaseError):
    """The Zenodo record has no usable Concept DOI."""


@dataclass(frozen=True)
class ComponentRelease:
    """Verified provenance for one published EESSI component release."""

    repository: str
    tag: str
    commit: str
    github_release_url: str
    is_immutable: bool
    doi: str
    concept_doi: str


def combine_component_release(
    github: GitHubReleaseSnapshot,
    zenodo: ZenodoRecord,
) -> ComponentRelease:
    """Combine matching GitHub and Zenodo release provenance."""

    release = github.release
    expected_related_identifier = github_release_url(
        release.repository,
        release.tag,
    )

    if zenodo.github_release_url != expected_related_identifier:
        raise ComponentReleaseMismatch(
            "Zenodo related identifier "
            f"{zenodo.github_release_url!r} does not match "
            f"GitHub release {release.repository}:{release.tag}"
        )

    if not isinstance(zenodo.doi, str) or not zenodo.doi.strip():
        raise ComponentReleaseMissingDOI(
            f"Zenodo record {zenodo.record_id} has no usable DOI"
        )

    if (
        not isinstance(zenodo.concept_doi, str)
        or not zenodo.concept_doi.strip()
    ):
        raise ComponentReleaseMissingConceptDOI(
            f"Zenodo record {zenodo.record_id} has no usable Concept DOI"
        )

    return ComponentRelease(
        repository=release.repository,
        tag=release.tag,
        commit=github.commit,
        github_release_url=release.url,
        is_immutable=github.is_immutable,
        doi=zenodo.doi,
        concept_doi=zenodo.concept_doi,
    )


def get_component_release(
    repository: str,
    tag: str,
    *,
    sandbox: bool = True,
) -> ComponentRelease:
    """Resolve a component release using a one-shot Zenodo lookup."""

    github = get_github_release(repository, tag)
    zenodo = find_github_release(
        repository,
        tag,
        sandbox=sandbox,
    )

    return combine_component_release(github, zenodo)


def wait_for_component_release(
    repository: str,
    tag: str,
    *,
    sandbox: bool = True,
    timeout: int = 600,
    poll_interval: int = 10,
) -> ComponentRelease:
    """Resolve a component release, waiting for Zenodo ingestion."""

    github = get_github_release(repository, tag)
    zenodo = wait_for_github_release(
        repository,
        tag,
        sandbox=sandbox,
        timeout=timeout,
        poll_interval=poll_interval,
    )

    return combine_component_release(github, zenodo)
