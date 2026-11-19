import json
import tempfile
import unittest
from pathlib import Path
from typing import cast

from eessi_revisions.cvmfs import CvmfsTagOutputError
from eessi_revisions.cvmfs_provenance import (
    CVMFS_PROVENANCE_SCHEMA_VERSION,
    CvmfsProvenanceDocument,
    CvmfsProvenanceDocumentError,
    CvmfsProvenanceIdentityMismatch,
    CvmfsProvenanceSource,
    create_cvmfs_provenance_document,
    cvmfs_provenance_from_dict,
    cvmfs_provenance_to_dict,
    deserialize_cvmfs_provenance,
    load_cvmfs_provenance,
    main,
    require_cvmfs_provenance_identity,
    serialize_cvmfs_provenance,
    write_cvmfs_provenance,
)

REPOSITORY = "software.eessi.io"
SNAPSHOT = "software.eessi.io-rev0006"
ROOT_CATALOG_HASH = "2c1a337d7e0960b63cff163cb633904d7ea19744"
TAG_OUTPUT = (
    "software.eessi.io-rev0006 "
    "2c1a337d7e0960b63cff163cb633904d7ea19744 "
    "26624 30536 1793657696 (default)\n"
)
CVMFS_VERSION = "2.14.1"


def valid_payload() -> dict[str, object]:
    return {
        "schema_version": CVMFS_PROVENANCE_SCHEMA_VERSION,
        "repository": REPOSITORY,
        "snapshot": SNAPSHOT,
        "revision": 30536,
        "root_catalog_hash": ROOT_CATALOG_HASH,
        "source": {
            "type": "cvmfs_server_tag",
            "cvmfs_version": CVMFS_VERSION,
            "catalog_size_bytes": 26624,
            "snapshot_timestamp": 1793657696,
            "branch": "(default)",
        },
    }


def source_from(payload: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], payload["source"])


class TestCreateCvmfsProvenanceDocument(unittest.TestCase):

    def test_creates_document_from_real_output(self):
        document = create_cvmfs_provenance_document(
            repository=REPOSITORY,
            snapshot=SNAPSHOT,
            tag_output=TAG_OUTPUT,
            cvmfs_version=CVMFS_VERSION,
        )

        self.assertEqual(document.schema_version, 1)
        self.assertEqual(document.snapshot.repository, REPOSITORY)
        self.assertEqual(document.snapshot.snapshot, SNAPSHOT)
        self.assertEqual(document.snapshot.revision, 30536)
        self.assertEqual(
            document.snapshot.root_catalog_hash,
            ROOT_CATALOG_HASH,
        )
        self.assertEqual(document.source.cvmfs_version, CVMFS_VERSION)
        self.assertEqual(document.source.catalog_size_bytes, 26624)
        self.assertEqual(document.source.snapshot_timestamp, 1793657696)
        self.assertEqual(document.source.branch, "(default)")

    def test_rejects_empty_cvmfs_version(self):
        for version in ("", "   "):
            with self.subTest(version=version), self.assertRaises(
                CvmfsProvenanceDocumentError
            ):
                create_cvmfs_provenance_document(
                    repository=REPOSITORY,
                    snapshot=SNAPSHOT,
                    tag_output=TAG_OUTPUT,
                    cvmfs_version=version,
                )

    def test_propagates_tag_output_errors(self):
        with self.assertRaises(CvmfsTagOutputError):
            create_cvmfs_provenance_document(
                repository=REPOSITORY,
                snapshot=SNAPSHOT,
                tag_output="malformed",
                cvmfs_version=CVMFS_VERSION,
            )


class TestSerializeCvmfsProvenance(unittest.TestCase):

    def setUp(self):
        self.document = create_cvmfs_provenance_document(
            repository=REPOSITORY,
            snapshot=SNAPSHOT,
            tag_output=TAG_OUTPUT,
            cvmfs_version=CVMFS_VERSION,
        )

    def test_converts_document_to_expected_mapping(self):
        self.assertEqual(
            cvmfs_provenance_to_dict(self.document),
            {
                "schema_version": CVMFS_PROVENANCE_SCHEMA_VERSION,
                "repository": REPOSITORY,
                "snapshot": SNAPSHOT,
                "revision": 30536,
                "root_catalog_hash": ROOT_CATALOG_HASH,
                "source": {
                    "type": "cvmfs_server_tag",
                    "cvmfs_version": CVMFS_VERSION,
                    "catalog_size_bytes": 26624,
                    "snapshot_timestamp": 1793657696,
                    "branch": "(default)",
                },
            },
        )

    def test_serializes_deterministically_with_final_newline(self):
        first = serialize_cvmfs_provenance(self.document)
        second = serialize_cvmfs_provenance(self.document)

        self.assertEqual(first, second)
        self.assertTrue(first.endswith("\n"))
        self.assertEqual(
            json.loads(first),
            cvmfs_provenance_to_dict(self.document),
        )

    def test_writes_document_and_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "nested" / "provenance.json"

            write_cvmfs_provenance(output, self.document)

            self.assertEqual(
                output.read_text(encoding="utf-8"),
                serialize_cvmfs_provenance(self.document),
            )


class TestLoadCvmfsProvenance(unittest.TestCase):

    def setUp(self):
        self.document = create_cvmfs_provenance_document(
            repository=REPOSITORY,
            snapshot=SNAPSHOT,
            tag_output=TAG_OUTPUT,
            cvmfs_version=CVMFS_VERSION,
        )

    def test_round_trip(self):
        loaded = deserialize_cvmfs_provenance(
            serialize_cvmfs_provenance(self.document)
        )

        self.assertEqual(loaded, self.document)

    def test_loads_valid_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "provenance.json"
            path.write_text(
                serialize_cvmfs_provenance(self.document),
                encoding="utf-8",
            )

            self.assertEqual(load_cvmfs_provenance(path), self.document)

    def test_rejects_invalid_json(self):
        with self.assertRaisesRegex(
            CvmfsProvenanceDocumentError,
            "invalid JSON",
        ):
            deserialize_cvmfs_provenance("{")

    def test_rejects_non_string_json_input(self):
        with self.assertRaisesRegex(
            CvmfsProvenanceDocumentError,
            "must be a string",
        ):
            deserialize_cvmfs_provenance(cast(str, b"{}"))

    def test_rejects_non_object_document(self):
        for value in ("[]", '"value"', "null"):
            with self.subTest(value=value), self.assertRaisesRegex(
                CvmfsProvenanceDocumentError,
                "must be a JSON object",
            ):
                deserialize_cvmfs_provenance(value)

    def test_rejects_missing_and_unexpected_top_level_fields(self):
        missing = valid_payload()
        del missing["repository"]
        unexpected = valid_payload()
        unexpected["extra"] = "value"

        for payload, message in (
            (missing, "missing fields: repository"),
            (unexpected, "unexpected fields: extra"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(
                CvmfsProvenanceDocumentError,
                message,
            ):
                cvmfs_provenance_from_dict(payload)

    def test_rejects_missing_and_unexpected_source_fields(self):
        missing = valid_payload()
        del source_from(missing)["branch"]
        unexpected = valid_payload()
        source_from(unexpected)["extra"] = "value"

        for payload, message in (
            (missing, "missing fields: branch"),
            (unexpected, "unexpected fields: extra"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(
                CvmfsProvenanceDocumentError,
                message,
            ):
                cvmfs_provenance_from_dict(payload)

    def test_rejects_invalid_schema_versions(self):
        for version in (True, 0, 2, "1"):
            payload = valid_payload()
            payload["schema_version"] = version

            with self.subTest(version=version), self.assertRaises(
                CvmfsProvenanceDocumentError
            ):
                cvmfs_provenance_from_dict(payload)

    def test_rejects_wrong_source_type(self):
        payload = valid_payload()
        source_from(payload)["type"] = "other"

        with self.assertRaisesRegex(
            CvmfsProvenanceDocumentError,
            "Unsupported CVMFS provenance source type",
        ):
            cvmfs_provenance_from_dict(payload)

    def test_rejects_invalid_top_level_values(self):
        cases = (
            ("repository", ""),
            ("snapshot", 6),
            ("revision", True),
            ("revision", 0),
            ("revision", "30536"),
            ("root_catalog_hash", "not-a-hash"),
            ("root_catalog_hash", ROOT_CATALOG_HASH.upper()),
        )

        for field, value in cases:
            payload = valid_payload()
            payload[field] = value

            with self.subTest(field=field, value=value), self.assertRaises(
                CvmfsProvenanceDocumentError
            ):
                cvmfs_provenance_from_dict(payload)

    def test_rejects_invalid_source_values(self):
        cases = (
            ("cvmfs_version", ""),
            ("catalog_size_bytes", True),
            ("catalog_size_bytes", -1),
            ("catalog_size_bytes", "26624"),
            ("snapshot_timestamp", True),
            ("snapshot_timestamp", 0),
            ("branch", "   "),
        )

        for field, value in cases:
            payload = valid_payload()
            source_from(payload)[field] = value

            with self.subTest(field=field, value=value), self.assertRaises(
                CvmfsProvenanceDocumentError
            ):
                cvmfs_provenance_from_dict(payload)

    def test_rejects_duplicate_top_level_field(self):
        text = serialize_cvmfs_provenance(self.document).replace(
            '"schema_version": 1,',
            '"schema_version": 1, "schema_version": 1,',
        )

        with self.assertRaisesRegex(
            CvmfsProvenanceDocumentError,
            "Duplicate JSON field: 'schema_version'",
        ):
            deserialize_cvmfs_provenance(text)

    def test_rejects_duplicate_nested_field(self):
        text = serialize_cvmfs_provenance(self.document).replace(
            '"branch": "(default)",',
            '"branch": "(default)", "branch": "(default)",',
        )

        with self.assertRaisesRegex(
            CvmfsProvenanceDocumentError,
            "Duplicate JSON field: 'branch'",
        ):
            deserialize_cvmfs_provenance(text)

    def test_requires_expected_identity(self):
        require_cvmfs_provenance_identity(
            self.document,
            REPOSITORY,
            SNAPSHOT,
        )

        for repository, snapshot in (
            ("other.eessi.io", SNAPSHOT),
            (REPOSITORY, "software.eessi.io-rev0007"),
        ):
            with self.subTest(
                repository=repository,
                snapshot=snapshot,
            ), self.assertRaises(CvmfsProvenanceIdentityMismatch):
                require_cvmfs_provenance_identity(
                    self.document,
                    repository,
                    snapshot,
                )


class TestCvmfsProvenanceRuntimeValidation(unittest.TestCase):

    def test_source_rejects_invalid_numeric_values(self):
        invalid_values = (
            (cast(int, True), 1793657696),
            (-1, 1793657696),
            (26624, cast(int, True)),
            (26624, 0),
        )

        for catalog_size, timestamp in invalid_values:
            with self.subTest(
                catalog_size=catalog_size,
                timestamp=timestamp,
            ), self.assertRaises(CvmfsProvenanceDocumentError):
                CvmfsProvenanceSource(
                    cvmfs_version=CVMFS_VERSION,
                    catalog_size_bytes=catalog_size,
                    snapshot_timestamp=timestamp,
                    branch="(default)",
                )

    def test_document_rejects_boolean_schema_version(self):
        document = create_cvmfs_provenance_document(
            repository=REPOSITORY,
            snapshot=SNAPSHOT,
            tag_output=TAG_OUTPUT,
            cvmfs_version=CVMFS_VERSION,
        )

        with self.assertRaises(CvmfsProvenanceDocumentError):
            CvmfsProvenanceDocument(
                snapshot=document.snapshot,
                source=document.source,
                schema_version=cast(int, True),
            )


class TestCvmfsProvenanceMain(unittest.TestCase):

    def test_converts_captured_output_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            captured_output = root / "cvmfs-tag-output.txt"
            provenance_output = root / "provenance" / "snapshot.json"
            captured_output.write_text(TAG_OUTPUT, encoding="utf-8")

            main(
                [
                    "--repository",
                    REPOSITORY,
                    "--snapshot",
                    SNAPSHOT,
                    "--input",
                    str(captured_output),
                    "--output",
                    str(provenance_output),
                    "--cvmfs-version",
                    CVMFS_VERSION,
                ]
            )

            payload = json.loads(
                provenance_output.read_text(encoding="utf-8")
            )
            self.assertEqual(payload["repository"], REPOSITORY)
            self.assertEqual(payload["snapshot"], SNAPSHOT)
            self.assertEqual(payload["revision"], 30536)
            self.assertEqual(
                payload["root_catalog_hash"],
                ROOT_CATALOG_HASH,
            )


if __name__ == "__main__":
    unittest.main()
