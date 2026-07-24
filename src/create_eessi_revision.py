import os
import subprocess
from datetime import datetime

import yaml

from manage_zenodo import Zenodo

# Configuration
with open("../config/config.yaml", "r") as file:
    config = yaml.safe_load(file)

GITHUB_REPOS = config["github_repos"]
CVMFS_REPO = config["cvmfs_repo"]
CVMFS_SERVER = config["cvmfs_server"]


def clone_or_pull_repos():
    """Clone or pull GitHub repositories"""
    for repo in GITHUB_REPOS:
        repo_dir = repo.split("/")[-1]
        if os.path.exists(repo_dir):
            subprocess.run(["git", "pull"], cwd=repo_dir)
        else:
            subprocess.run(["gh", "repo", "clone", repo])


def get_latest_tag(repo_dir):
    """Get the latest tag from a Git repository"""
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def create_cvmfs_snapshot(tag, doi):
    """Create a CVMFS snapshot and tag it with the release information"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_name = f"{tag}_{timestamp}"

    # Create a new CVMFS transaction
    subprocess.run(["cvmfs_server", "transaction", CVMFS_REPO])

    # Create a directory for the release
    release_dir = os.path.join(CVMFS_REPO, "releases", tag)
    os.makedirs(release_dir, exist_ok=True)

    # Create a metadata file with the DOI
    metadata = {"tag": tag, "doi": doi, "timestamp": timestamp}
    with open(os.path.join(release_dir, "metadata.yaml"), "w") as f:
        yaml.dump(metadata, f)

    # Publish the transaction
    subprocess.run(["cvmfs_server", "publish", "-a", CVMFS_REPO])

    # Create a tag in the CVMFS repository
    subprocess.run(["cvmfs_server", "tag", CVMFS_REPO, snapshot_name, tag])

    return snapshot_name


def main():
    # Clone or pull repositories
    clone_or_pull_repos()

    # Process each repository
    for repo in GITHUB_REPOS:
        repo_dir = repo.split("/")[-1]
        tag = get_latest_tag(repo_dir)

        # Create or update Zenodo record
        doi = create_cvmfs_snapshot(repo_dir, tag)

        # Create CVMFS snapshot
        snapshot_name = create_cvmfs_snapshot(tag, doi)

        print(f"Processed {repo_dir}:")
        print(f"  Tag: {tag}")
        print(f"  DOI: {doi}")
        print(f"  CVMFS Snapshot: {snapshot_name}")


if __name__ == "__main__":
    main()
