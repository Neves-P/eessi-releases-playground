import json
import os
import subprocess

import yaml


def convert_zenodo_to_cff(zenodo_json_path, cff_path):
    # Load the Zenodo JSON file
    with open(zenodo_json_path, 'r') as file:
        zenodo_data = json.load(file)

    upload_type = zenodo_data.get("upload_type", "software")
    # TODO: If upload_type not in cff schema, use "misc"
    if upload_type == "event":
        upload_type = "software"

    cff = {
        "cff-version": "1.2.0",
        "title": zenodo_data.get("title", ""),
        "version": zenodo_data.get("version", "1.0.0"),
        "license": zenodo_data.get("license", ""),
        "type": upload_type,
        "abstract": zenodo_data.get("description", ""),
        "message": 'If you use this record, please cite it as below.',
        "authors": [],
        "keywords": zenodo_data.get("keywords", []),
    }
    for creator in zenodo_data.get("creators", []):
        name = creator["name"]

        if ", " in name:
            family, given = name.split(", ", 1)
        else:
            parts = name.split()
            given = " ".join(parts[:-1])
            family = parts[-1]

        author = {
            "given-names": given,
            "family-names": family,
        }

        if creator.get("affiliation"):
            author["affiliation"] = creator["affiliation"]

        if creator.get("orcid"):
            if not creator["orcid"].startswith("http://orcid.org/"):
                author["orcid"] = f"https://orcid.org/{creator['orcid']}"
            else:
                author["orcid"] = creator["orcid"]

        cff["authors"].append(author)

    with open(cff_path, "w") as f:
        yaml.safe_dump(cff, f, sort_keys=False, allow_unicode=True)


    # Validate the CFF file using the cffconvert command-line tool
    subprocess.run(['cffconvert', '--validate', '-i', cff_path], check=True)

if __name__ == '__main__':
    # Get the root of the repository
    repo_root = os.getenv('GITHUB_WORKSPACE', '..')

    # Construct the paths
    zenodo_json_path = os.path.join(repo_root, '.zenodo.json')
    cff_path = os.path.join(repo_root, 'CITATION.cff')

    convert_zenodo_to_cff(zenodo_json_path, cff_path)
