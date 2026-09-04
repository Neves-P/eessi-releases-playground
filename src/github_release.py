from dataclasses import asdict, dataclass
import argparse
import json
from urllib.parse import quote

from src.github import (
    GitHubError,
    GitHubRelease,
    run_gh_json,
)


class GitHubReleaseError(GitHubError):
    """Base exception for exact GitHub release lookup failures."""


class GitHubReleaseNotPublished(GitHubReleaseError):
    """The requested GitHub release is not a published stable release."""


@dataclass(frozen=True)
class GitHubReleaseSnapshot:
    """A published GitHub release resolved to an exact Git commit."""

    release: GitHubRelease
    commit: str
    is_immutable: bool


def resolve_commit(
    repository: str,
    tag: str,
) -> str:
    """Resolve a Git tag to its exact commit SHA."""

    ref = quote(
        f"tags/{tag}",
        safe="",
    )

    payload = run_gh_json(
        "api",
        f"repos/{repository}/commits/{ref}",
    )

    if not isinstance(payload, dict):
        raise GitHubReleaseError(
            f"Unexpected commit response for {repository}:{tag}"
        )

    sha = payload.get("sha")

    if not isinstance(sha, str) or not sha:
        raise GitHubReleaseError(
            f"Could not resolve {repository}:{tag} to a commit"
        )

    return sha


def get_github_release(
    repository: str,
    tag: str,
) -> GitHubReleaseSnapshot:
    """Return an exact published GitHub release and its commit."""

    payload = run_gh_json(
        "release",
        "view",
        tag,
        "--repo",
        repository,
        "--json",
        (
            "tagName,name,publishedAt,url,"
            "isDraft,isPrerelease,isImmutable"
        ),
    )

    if not isinstance(payload, dict):
        raise GitHubReleaseError(
            f"Unexpected release response for {repository}:{tag}"
        )

    returned_tag = payload.get("tagName")

    if returned_tag != tag:
        raise GitHubReleaseError(
            f"GitHub returned tag {returned_tag!r}, "
            f"expected {tag!r}"
        )

    if payload.get("isDraft"):
        raise GitHubReleaseNotPublished(
            f"GitHub release {repository}:{tag} is a draft"
        )

    if payload.get("isPrerelease"):
        raise GitHubReleaseNotPublished(
            f"GitHub release {repository}:{tag} is a prerelease"
        )

    published_at = payload.get("publishedAt")

    if not isinstance(published_at, str) or not published_at:
        raise GitHubReleaseNotPublished(
            f"GitHub release {repository}:{tag} "
            "has no publication timestamp"
        )

    url = payload.get("url")

    if not isinstance(url, str) or not url:
        raise GitHubReleaseError(
            f"GitHub release {repository}:{tag} has no URL"
        )

    is_immutable = payload.get("isImmutable")

    if not isinstance(is_immutable, bool):
        raise GitHubReleaseError(
            f"GitHub release {repository}:{tag} "
            "has no valid immutability status"
        )

    name = payload.get("name")

    if not isinstance(name, str) or not name:
        name = tag

    release = GitHubRelease(
        repository=repository,
        tag=tag,
        name=name,
        published_at=published_at,
        url=url,
    )

    return GitHubReleaseSnapshot(
        release=release,
        commit=resolve_commit(
            repository,
            tag,
        ),
        is_immutable=is_immutable,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Get a published GitHub Release and resolve "
            "its tag to an exact commit."
        )
    )

    parser.add_argument(
        "repository",
        help="GitHub repository in OWNER/REPO form",
    )

    parser.add_argument(
        "tag",
        help="GitHub release tag",
    )

    args = parser.parse_args()

    snapshot = get_github_release(
        args.repository,
        args.tag,
    )

    print(
        json.dumps(
            asdict(snapshot),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
