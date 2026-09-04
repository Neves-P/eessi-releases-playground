import json
import subprocess
from dataclasses import dataclass


class GitHubError(RuntimeError):
    """Base exception for GitHub operations."""


@dataclass(frozen=True)
class GitHubRelease:
    repository: str
    tag: str
    name: str
    published_at: str
    url: str


def run_gh(*args: str) -> str:
    """Run GitHub CLI and return stdout."""

    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise GitHubError(
            f"GitHub CLI command failed: {' '.join(result.args)}\n"
            f"{result.stderr.strip()}"
        )

    return result.stdout


def run_gh_json(*args: str):
    """Run GitHub CLI and parse its JSON output."""

    output = run_gh(*args)

    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise GitHubError(
            "GitHub CLI returned invalid JSON"
        ) from exc
