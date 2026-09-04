from datetime import datetime
from pathlib import Path

import yaml

from src.github import GitHubError, GitHubRelease, run_gh_json


CONFIG_PATH = Path("config/config.yaml")
PR_METADATA_DIR = Path("data/pr_metadata")
RELEASE_METADATA_DIR = Path("data/release_metadata")


def load_config(path: Path = CONFIG_PATH) -> dict:
    """Load collector configuration."""

    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise TypeError(
            f"Configuration file {path} does not contain a mapping"
        )

    github_repos = config.get("github_repos")

    if not isinstance(github_repos, list):
        raise TypeError(
            f"Configuration file {path} has no valid 'github_repos' list"
        )

    return config


def repository_from_url(repo_url: str) -> str:
    """Convert a GitHub repository URL to OWNER/REPO form."""

    parts = repo_url.rstrip("/").rsplit("/", 2)

    if len(parts) < 3:
        raise ValueError(
            f"Invalid GitHub repository URL: {repo_url}"
        )

    owner = parts[-2]
    repo = parts[-1].removesuffix(".git")

    return f"{owner}/{repo}"


def collect_github_pr_metadata(repo_url: str) -> list[dict]:
    """Collect metadata for merged pull requests."""

    repository = repository_from_url(repo_url)

    merged_prs = run_gh_json(
        "pr",
        "list",
        "--repo",
        repository,
        "--state",
        "merged",
        "--json",
        "number,title,labels,author,mergedAt,mergedBy,url",
        "--limit",
        "2000",
    )

    if not isinstance(merged_prs, list):
        raise GitHubError(
            f"Unexpected pull request response for {repository}"
        )

    return [
        {
            "number": pr["number"],
            "title": pr["title"],
            "labels": pr["labels"],
            "author": pr["author"],
            "merged_at": pr["mergedAt"],
            "merged_by": pr["mergedBy"],
            "url": pr["url"],
        }
        for pr in merged_prs
    ]


def collect_github_releases(
    repo_url: str,
) -> list[GitHubRelease]:
    """Collect published stable GitHub releases."""

    repository = repository_from_url(repo_url)

    releases = run_gh_json(
        "release",
        "list",
        "--repo",
        repository,
        "--exclude-drafts",
        "--exclude-pre-releases",
        "--json",
        "tagName,name,publishedAt,url",
        "--limit",
        "2000",
    )

    if not isinstance(releases, list):
        raise GitHubError(
            f"Unexpected release response for {repository}"
        )

    return [
        GitHubRelease(
            repository=repository,
            tag=release["tagName"],
            name=release["name"] or release["tagName"],
            published_at=release["publishedAt"],
            url=release["url"],
        )
        for release in releases
    ]


def release_to_metadata(
    release: GitHubRelease,
) -> dict:
    """Convert a GitHubRelease to the collector's YAML format.

    Keep the existing release metadata schema for compatibility with
    downstream consumers.
    """

    return {
        "tag": release.tag,
        "name": release.name,
        "published_at": release.published_at,
    }


def write_yaml(path: Path, data: object) -> None:
    """Write data to a YAML file."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(
            data,
            file,
            sort_keys=False,
            allow_unicode=True,
        )


def main() -> None:
    """Collect GitHub metadata for all configured repositories."""

    config = load_config()

    # Use one timestamp for the complete collector run.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for repo_url in config["github_repos"]:
        repository = repository_from_url(repo_url)
        repo_name = repository.split("/", 1)[1]

        try:
            pr_metadata = collect_github_pr_metadata(
                repo_url
            )
        except GitHubError as exc:
            print(
                f"Failed to collect pull requests "
                f"for {repository}: {exc}"
            )
        else:
            if pr_metadata:
                output_path = (
                    PR_METADATA_DIR
                    / f"{repo_name}_pr_{timestamp}.yaml"
                )

                write_yaml(
                    output_path,
                    pr_metadata,
                )

        try:
            releases = collect_github_releases(
                repo_url
            )
        except GitHubError as exc:
            print(
                f"Failed to collect releases "
                f"for {repository}: {exc}"
            )
        else:
            if releases:
                release_metadata = [
                    release_to_metadata(release)
                    for release in releases
                ]

                output_path = (
                    RELEASE_METADATA_DIR
                    / f"{repo_name}_release_{timestamp}.yaml"
                )

                write_yaml(
                    output_path,
                    release_metadata,
                )


if __name__ == "__main__":
    main()
