import os
from collections import defaultdict

import yaml

# Directory paths
pr_metadata_dir = "data/pr_metadata"
release_metadata_dir = "data/release_metadata"


# Function to load YAML files from a directory
def load_yaml_files(directory):
    yaml_files = [f for f in os.listdir(directory) if f.endswith(".yaml")]
    data = []
    for file in yaml_files:
        with open(os.path.join(directory, file), "r") as f:
            data.extend(yaml.safe_load(f))
    return data


# Function to categorize changes by label
def categorize_changes(prs):
    categorized = defaultdict(list)
    for pr in prs:
        labels = pr.get("labels", [])
        if not labels:
            categorized["uncategorized"].append(pr)
        else:
            for label in labels:
                label_name = label.get("name", "")
                if label_name.startswith("20") and label_name.endswith(
                    "-software.eessi.io"
                ):
                    categorized[label_name].append(pr)
    return categorized


# Function to generate changelog for a milestone
# TODO: Expand with URL?
def generate_changelog(milestone, changes):
    changelog = f"# Changelog for {milestone}\n\n"
    for label, prs in changes.items():
        changelog += f"## {label}\n\n"
        for pr in prs:
            changelog += f"- {pr['title']} (#{pr['number']})\n"
    return changelog


# Main function
def main():
    # Load PR metadata
    pr_metadata = load_yaml_files(pr_metadata_dir)

    # Load release metadata
    # Note: for this to work, we need to start tagging releases
    # release_metadata = load_yaml_files(release_metadata_dir)

    # Categorize changes by label
    categorized_changes = categorize_changes(pr_metadata)

    # Generate changelog for each milestone
    for milestone, changes in categorized_changes.items():
        changelog = generate_changelog(milestone, {milestone: changes})

        # Save changelog to a file
        changelog_dir = "data/changelogs"
        os.makedirs(changelog_dir, exist_ok=True)
        changelog_file = os.path.join(changelog_dir, f"{milestone}.md")
        with open(changelog_file, "w") as f:
            f.write(changelog)


if __name__ == "__main__":
    main()
