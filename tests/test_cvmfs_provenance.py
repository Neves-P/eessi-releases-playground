import json
import tempfile
import unittest
from pathlib import Path

from eessi_revisions.cvmfs import CvmfsTagOutputError
from eessi_revisions.cvmfs_provenance import (
    CVMFS_PROVENANCE_SCHEMA_VERSION,
    CvmfsProvenanceDocumentError,
    create_cvmfs_provenance_document,
    cvmfs_provenance_to_dict,
    main,
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
