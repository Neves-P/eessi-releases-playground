import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import cast

from eessi_revisions.component_release import ComponentRelease
from eessi_revisions.cvmfs_provenance import (
    CvmfsProvenanceDocument,
    create_cvmfs_provenance_document,
)
from eessi_revisions.revision import (
    PRODUCTION_REQUIRED_COMPONENT_ROLES,
    ComponentRole,
    EESSIRevision,
    RevisionComponent,
)
from eessi_revisions.revision_manifest import (
    REVISION_MANIFEST_SCHEMA_VERSION,
    RevisionManifestError,
    UnsupportedRevisionManifestSchema,
    deserialize_revision_manifest,
    load_revision_manifest,
    revision_manifest_from_dict,
    revision_manifest_to_dict,
    serialize_revision_manifest,
    write_revision_manifest,
)

REVISION = "eessi-2026.09-poc.1"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
ROOT_CATALOG_HASH = "2c1a337d7e0960b63cff163cb633904d7ea19744"
TAG_OUTPUT = (
    "software.eessi.io-rev0006 "
    f"{ROOT_CATALOG_HASH} "
    "26624 30536 1793657696 (default)\n"
)


def make_release(repository: str) -> ComponentRelease:
    slug = repository.replace("/", "-").lower()

    return ComponentRelease(
        repository=repository,
        tag=REVISION,
        commit=COMMIT,
        github_release_url=(
            f"https://github.com/{repository}/releases/tag/{REVISION}"
        ),
        is_immutable=True,
        doi=f"10.5072/zenodo.{slug}",
        concept_doi=f"10.5072/zenodo.{slug}.concept",
    )


def make_component(
    role: ComponentRole,
    repository: str,
) -> RevisionComponent:
    return RevisionComponent(
        role=role,
        release=make_release(repository),
    )


def make_cvmfs() -> CvmfsProvenanceDocument:
    return create_cvmfs_provenance_document(
        repository="software.eessi.io",
        snapshot="software.eessi.io-rev0006",
        tag_output=TAG_OUTPUT,
        cvmfs_version="2.14.1",
    )


def make_poc_revision(
    *,
    include_documentation: bool = False,
) -> EESSIRevision:
    components = [
        make_component(
            ComponentRole.SOFTWARE_LAYER,
            "Neves-P/software-layer",
        )
    ]

    if include_documentation:
        components.append(
            make_component(
                ComponentRole.DOCUMENTATION,
                "EESSI/docs",
            )
        )

    return EESSIRevision(
        revision=REVISION,
        components=tuple(components),
        cvmfs=make_cvmfs(),
    )


def make_production_revision() -> EESSIRevision:
    components = tuple(
        make_component(role, f"EESSI/{role.value}")
        for role in ComponentRole
    )

    return EESSIRevision(
        revision="eessi-2026.09",
        components=components,
        cvmfs=make_cvmfs(),
        required_roles=PRODUCTION_REQUIRED_COMPONENT_ROLES,
    )


def component_payload(
    payload: dict[str, object],
    index: int = 0,
) -> dict[str, object]:
    components = cast(list[object], payload["components"])
    return cast(dict[str, object], components[index])


class TestRevisionManifestSerialization(unittest.TestCase):

    def test_converts_revision_to_expected_mapping(self):
        revision = make_poc_revision()

        self.assertEqual(
            revision_manifest_to_dict(revision),
            {
                "schema_version": REVISION_MANIFEST_SCHEMA_VERSION,
                "revision": REVISION,
                "components": [
                    {
                        "role": "software_layer",
                        "repository": "Neves-P/software-layer",
                        "tag": REVISION,
                        "commit": COMMIT,
                        "github_release_url": (
                            "https://github.com/Neves-P/software-layer/"
                            f"releases/tag/{REVISION}"
                        ),
                        "is_immutable": True,
                        "doi": (
                            "10.5072/zenodo."
                            "neves-p-software-layer"
                        ),
                        "concept_doi": (
                            "10.5072/zenodo."
                            "neves-p-software-layer.concept"
                        ),
                    }
                ],
                "cvmfs": {
                    "schema_version": 1,
                    "repository": "software.eessi.io",
                    "snapshot": "software.eessi.io-rev0006",
                    "revision": 30536,
                    "root_catalog_hash": ROOT_CATALOG_HASH,
                    "source": {
                        "type": "cvmfs_server_tag",
                        "cvmfs_version": "2.14.1",
                        "catalog_size_bytes": 26624,
                        "snapshot_timestamp": 1793657696,
                        "branch": "(default)",
                    },
                },
            },
        )

    def test_sorts_components_by_role(self):
        revision = make_poc_revision(include_documentation=True)

        payload = revision_manifest_to_dict(revision)
        roles = [
            cast(dict[str, object], component)["role"]
            for component in cast(list[object], payload["components"])
        ]

        self.assertEqual(roles, ["documentation", "software_layer"])

    def test_excludes_publication_and_policy_metadata(self):
        payload = revision_manifest_to_dict(make_poc_revision())

        for field in (
            "doi",
            "concept_doi",
            "required_roles",
            "generated_at",
        ):
            with self.subTest(field=field):
                self.assertNotIn(field, payload)

    def test_serializes_deterministically_with_final_newline(self):
        revision = make_poc_revision(include_documentation=True)
        first = serialize_revision_manifest(revision)
        second = serialize_revision_manifest(revision)

        self.assertEqual(first, second)
        self.assertTrue(first.endswith("\n"))
        self.assertEqual(
            json.loads(first),
            revision_manifest_to_dict(revision),
        )

    def test_writes_manifest_and_creates_parent_directories(self):
        revision = make_poc_revision()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "revision.json"

            write_revision_manifest(path, revision)

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                serialize_revision_manifest(revision),
            )


class TestRevisionManifestLoading(unittest.TestCase):

    def setUp(self):
        self.revision = make_poc_revision()
        self.payload = revision_manifest_to_dict(self.revision)

    def test_reconstructs_revision_from_mapping(self):
        loaded = revision_manifest_from_dict(self.payload)

        self.assertEqual(loaded, self.revision)

    def test_round_trip_is_stable(self):
        first = serialize_revision_manifest(self.revision)
        loaded = deserialize_revision_manifest(first)
        second = serialize_revision_manifest(loaded)

        self.assertEqual(loaded, self.revision)
        self.assertEqual(second, first)

    def test_loads_valid_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "revision.json"
            path.write_text(
                serialize_revision_manifest(self.revision),
                encoding="utf-8",
            )

            self.assertEqual(load_revision_manifest(path), self.revision)

    def test_rejects_invalid_json(self):
        with self.assertRaisesRegex(
            RevisionManifestError,
            "invalid JSON",
        ):
            deserialize_revision_manifest("{")

    def test_rejects_non_string_json_input(self):
        with self.assertRaisesRegex(
            RevisionManifestError,
            "must be a string",
        ):
            deserialize_revision_manifest(cast(str, b"{}"))

    def test_rejects_non_object_manifest(self):
        for text in ("[]", '"manifest"', "null"):
            with self.subTest(text=text), self.assertRaisesRegex(
                RevisionManifestError,
                "must be a JSON object",
            ):
                deserialize_revision_manifest(text)

    def test_rejects_missing_and_unexpected_top_level_fields(self):
        missing = copy.deepcopy(self.payload)
        del missing["revision"]
        unexpected = copy.deepcopy(self.payload)
        unexpected["top_level_doi"] = "10.5072/zenodo.example"

        for payload, message in (
            (missing, "missing fields: revision"),
            (unexpected, "unexpected fields: top_level_doi"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(
                RevisionManifestError,
                message,
            ):
                revision_manifest_from_dict(payload)

    def test_rejects_invalid_schema_version_type(self):
        for version in (True, "1", None):
            payload = copy.deepcopy(self.payload)
            payload["schema_version"] = version

            with self.subTest(version=version), self.assertRaisesRegex(
                RevisionManifestError,
                "must be an integer",
            ):
                revision_manifest_from_dict(payload)

    def test_rejects_unsupported_schema_version(self):
        for version in (0, 2):
            payload = copy.deepcopy(self.payload)
            payload["schema_version"] = version

            with self.subTest(version=version), self.assertRaises(
                UnsupportedRevisionManifestSchema
            ):
                revision_manifest_from_dict(payload)

    def test_rejects_empty_revision(self):
        for value in ("", "   ", 1):
            payload = copy.deepcopy(self.payload)
            payload["revision"] = value

            with self.subTest(value=value), self.assertRaises(
                RevisionManifestError
            ):
                revision_manifest_from_dict(payload)

    def test_rejects_non_array_components(self):
        for value in ({}, "component", None):
            payload = copy.deepcopy(self.payload)
            payload["components"] = value

            with self.subTest(value=value), self.assertRaisesRegex(
                RevisionManifestError,
                "must be a JSON array",
            ):
                revision_manifest_from_dict(payload)

    def test_rejects_non_object_component(self):
        payload = copy.deepcopy(self.payload)
        payload["components"] = ["software_layer"]

        with self.assertRaisesRegex(
            RevisionManifestError,
            "component 0 must be a JSON object",
        ):
            revision_manifest_from_dict(payload)

    def test_rejects_missing_and_unexpected_component_fields(self):
        missing = copy.deepcopy(self.payload)
        del component_payload(missing)["doi"]
        unexpected = copy.deepcopy(self.payload)
        component_payload(unexpected)["record_id"] = 598123

        for payload, message in (
            (missing, "missing fields: doi"),
            (unexpected, "unexpected fields: record_id"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(
                RevisionManifestError,
                message,
            ):
                revision_manifest_from_dict(payload)

    def test_rejects_unknown_component_role(self):
        payload = copy.deepcopy(self.payload)
        component_payload(payload)["role"] = "unknown"

        with self.assertRaisesRegex(
            RevisionManifestError,
            "unsupported role",
        ):
            revision_manifest_from_dict(payload)

    def test_rejects_invalid_component_strings(self):
        fields = (
            "role",
            "repository",
            "tag",
            "github_release_url",
            "doi",
            "concept_doi",
        )

        for field in fields:
            payload = copy.deepcopy(self.payload)
            component_payload(payload)[field] = ""

            with self.subTest(field=field), self.assertRaises(
                RevisionManifestError
            ):
                revision_manifest_from_dict(payload)

    def test_rejects_invalid_commit(self):
        for value in (
            "",
            "not-a-commit",
            COMMIT.upper(),
            True,
        ):
            payload = copy.deepcopy(self.payload)
            component_payload(payload)["commit"] = value

            with self.subTest(value=value), self.assertRaises(
                RevisionManifestError
            ):
                revision_manifest_from_dict(payload)

    def test_rejects_non_boolean_immutability(self):
        for value in (1, 0, "true", None):
            payload = copy.deepcopy(self.payload)
            component_payload(payload)["is_immutable"] = value

            with self.subTest(value=value), self.assertRaisesRegex(
                RevisionManifestError,
                "must be a boolean",
            ):
                revision_manifest_from_dict(payload)

    def test_rejects_duplicate_json_fields_at_any_level(self):
        texts = (
            '{"schema_version": 1, "schema_version": 1}',
            (
                '{"components": [{"role": "software_layer", '
                '"role": "software_layer"}]}'
            ),
            (
                '{"cvmfs": {"repository": "software.eessi.io", '
                '"repository": "software.eessi.io"}}'
            ),
        )

        for text in texts:
            with self.subTest(text=text), self.assertRaisesRegex(
                RevisionManifestError,
                "Duplicate JSON field",
            ):
                deserialize_revision_manifest(text)

    def test_rejects_invalid_embedded_cvmfs_provenance(self):
        payload = copy.deepcopy(self.payload)
        cvmfs = cast(dict[str, object], payload["cvmfs"])
        cvmfs["root_catalog_hash"] = "invalid"

        with self.assertRaisesRegex(
            RevisionManifestError,
            "invalid CVMFS provenance",
        ):
            revision_manifest_from_dict(payload)

    def test_rejects_duplicate_component_roles(self):
        payload = copy.deepcopy(self.payload)
        duplicate = copy.deepcopy(component_payload(payload))
        duplicate["repository"] = "EESSI/other-software-layer"
        cast(list[object], payload["components"]).append(duplicate)

        with self.assertRaisesRegex(
            RevisionManifestError,
            "Duplicate EESSI component role",
        ):
            revision_manifest_from_dict(payload)

    def test_rejects_duplicate_component_repositories(self):
        payload = copy.deepcopy(self.payload)
        duplicate = copy.deepcopy(component_payload(payload))
        duplicate["role"] = "documentation"
        duplicate["repository"] = "neves-p/SOFTWARE-LAYER"
        cast(list[object], payload["components"]).append(duplicate)

        with self.assertRaisesRegex(
            RevisionManifestError,
            "Duplicate EESSI component repository",
        ):
            revision_manifest_from_dict(payload)

    def test_production_policy_rejects_incomplete_manifest(self):
        with self.assertRaisesRegex(
            RevisionManifestError,
            "missing required component roles",
        ):
            revision_manifest_from_dict(
                self.payload,
                required_roles=PRODUCTION_REQUIRED_COMPONENT_ROLES,
            )

    def test_production_policy_accepts_all_roles(self):
        revision = make_production_revision()
        text = serialize_revision_manifest(revision)

        loaded = deserialize_revision_manifest(
            text,
            required_roles=PRODUCTION_REQUIRED_COMPONENT_ROLES,
        )

        self.assertEqual(
            {component.role for component in loaded.components},
            set(ComponentRole),
        )
        self.assertEqual(serialize_revision_manifest(loaded), text)


if __name__ == "__main__":
    unittest.main()
