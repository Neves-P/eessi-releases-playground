import os
import subprocess
from datetime import datetime

import yaml

# Load configuration
with open("config/config.yaml", "r") as file:
    config = yaml.safe_load(file)


# Function to collect metadata from GitHub repositories
def collect_github_pr_metadata(repo_url):
    # Extract repository owner and name from URL
    repo_owner, repo_name = repo_url.split("/")[-2:]

    # Command to get merged pull request metadata using gh CLI
    command = [
        "gh",
        "pr",
        "list",
        "--repo",
        f"{repo_owner}/{repo_name}",
        "--state",
        "merged",
        "--json",
        "number,title,labels,author,mergedAt,mergedBy,url",
        "--limit",
        "2000",
    ]

    # Execute the command
    result = subprocess.run(command, capture_output=True, text=True)

    # Check if the command was successful
    if result.returncode == 0:
        # Parse the JSON output
        merged_prs = yaml.safe_load(result.stdout)

        # Collect metadata for each merged pull request
        metadata = []
        for pr in merged_prs:
            pr_metadata = {
                "number": pr["number"],
                "title": pr["title"],
                "labels": pr["labels"],
                "author": pr["author"],
                "merged_at": pr["mergedAt"],
                "merged_by": pr["mergedBy"],
                "url": pr["url"],
            }
            metadata.append(pr_metadata)

        return metadata
    else:
        # Print error message if the command was not successful
        print(f"Error: {result.stderr}")
        return None


def collect_github_releases(repo_url):
    # Extract repository owner and name from URL
    repo_owner, repo_name = repo_url.split("/")[-2:]

    # Command to get merged pull request metadata using gh CLI
    command = [
        "gh",
        "release",
        "list",
        "--repo",
        f"{repo_owner}/{repo_name}",
        "--exclude-drafts",
        "--exclude-pre-releases",
        "--json",
        "tagName,name,publishedAt",
        "--limit",
        "2000",
    ]

    # Execute the command
    result = subprocess.run(command, capture_output=True, text=True)

    # Check if the command was successful
    if result.returncode == 0:
        # Parse the JSON output
        merged_prs = yaml.safe_load(result.stdout)

        # Collect metadata for each merged pull request
        metadata = []
        for pr in merged_prs:
            pr_metadata = {
                "tag": pr["tagName"],
                "name": pr["name"],
                "published_at": pr["publishedAt"],
            }
            metadata.append(pr_metadata)

        return metadata
    else:
        # Print error message if the command was not successful
        print(f"Error: {result.stderr}")
        return None


# Main function
def main():
    # Collect metadata for each repository
    for repo_url in config["github_repos"]:
        pr_metadata = collect_github_pr_metadata(repo_url)
        release_metadata = collect_github_releases(repo_url)

        # Save metadata to a file
        if pr_metadata:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data/pr_metadata/{repo_url.split('/')[-1]}_pr_{timestamp}.yaml"
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w") as file:
                yaml.dump(pr_metadata, file)

        if release_metadata:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data/release_metadata/{repo_url.split('/')[-1]}_release_{timestamp}.yaml"
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w") as file:
                yaml.dump(release_metadata, file)


if __name__ == "__main__":
    main()
