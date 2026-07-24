import subprocess
from datetime import date

import yaml

from manage_zenodo import Zenodo


def create_cvmfs_metadata(zenodo_deposition: int, tag):
    # TODO: Create metadata yml to put in /cvmfs/software.eessi.io/versions/{eessi_version}/revisions
    # Should include: {software,compat,filesystem}-layer version; revision; DOI; timestamp; URLs(?)
    # create_cvmfs_metadata()
    # TODO: rework config path in zenodo constructor
    response = Zenodo("../config/config.yaml").get_zenodo_deposition(zenodo_deposition)
    # Change this to actual DOI? Or maybe we can make use of the prereserve one?
    deposition_doi = response.json()["metadata"]["prereserve_doi"]["doi"]

    # TODO: Implement this. It must:
    # - Read metadata files per layer
    # - These need to be collected from output of collect_github_releases(repo_url) (from data/release_metadata/)
    # - For this we need versions/tags in all those repositories
    # - Consider implementing as EESSILayer class?
    # software_layer_version, software_layer_commit, software_layer_url = read_latest_metadata("software_layer")
    # compatibility_layer_version, compatibility_layer_commit, compatibility_layer_url = read_latest_metadata("compatibility_layer")
    # filesystem_layer_version, filesystem_layer_commit, filesystem_layer_url = read_latest_metadata("filesystem_layer")

    data = {
        "name": "EESSI revision",
        "organization": "EESSI",
        "metadata": {
            "title": "EESSI revision testing",
            "doi": deposition_doi,
            "tagcreators": [
                {"name": "Doe, Jane", "affiliation": "University of Nowhere"}
            ],
        },
        "software-layer": {
            "version": software_layer_version,
            "commit": software_layer_commit,
            "repo_url": software_layer_url,
        },
        "filesystem-layer": {
            "version": filesystem_layer_version,
            "commit": filesystem_layer_commit,
            "repo_url": filesystem_layer_url,
        },
        "compatibility-layer": {
            "tag": compatibility_layer_tag,
            "commit": compatibility_layer_commit,
            "repo_url": compatibility_layer_url,
        },
    }

    # Dump to a string
    yaml_string = yaml.dump(data)
    print(yaml_string)


def cvmfs_snapshotter(cvmfs_revision, eessi_version, cvmfs_repo, cvmfs_server):
    """Publish named snapshot with tag to the CVMFS repository"""
    tag = f"v{eessi_version}-rev-{cvmfs_revision}-{date.today().strftime('%Y%m%d')}"
    tag_description = f"Tagging EESSI revision {cvmfs_revision} using compat layer version {eessi_version}"
    print(f"Using '{tag}' as tag.")
    print(f"Using '{tag_description}' as tag description.")
    zenodo_deposition = Zenodo()
    subprocess.run(["cvmfs_server", "transaction", CVMFS_REPO])
    create_cvmfs_metadata()
    subprocess.run(
        ["cvmfs_server", "publish", "-a", tag, CVMFS_REPO, "-m", tag_description]
    )


if __name__ == "__main__":
    # Example usage (Testing only!)

    # Load configuration
    with open("config/config.yaml", "r") as file:
        config = yaml.safe_load(file)

    cvmfs_repo = config["cvmfs_repo"]
    cvmfs_server = config["cvmfs_server"]

    # Test vars
    cvmfs_revision = 1
    eessi_version = 2025.06
    zenodo_deposition = 509009

    # TODO: Get arguments from main function
    cvmfs_snapshotter(cvmfs_revision, eessi_version, cvmfs_repo, cvmfs_server)
