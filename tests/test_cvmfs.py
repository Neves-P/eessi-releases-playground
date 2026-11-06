import unittest

from eessi_revisions.cvmfs import (
    CvmfsSnapshot,
    CvmfsSnapshotMismatch,
    CvmfsSnapshotValidationError,
    CvmfsTagOutputError,
    parse_cvmfs_tag_inspection,
    parse_cvmfs_tag_output,
)

REPOSITORY = "software.eessi.io"
SNAPSHOT = "software.eessi.io-rev0006"
ROOT_CATALOG_HASH = "2c1a337d7e0960b63cff163cb633904d7ea19744"
TAG_OUTPUT = (
    "software.eessi.io-rev0006 "
    "2c1a337d7e0960b63cff163cb633904d7ea19744 "
    "26624 30536 1793657696 (default)"
)


def make_tag_output(
    *,
    snapshot: str = SNAPSHOT,
    root_catalog_hash: str = ROOT_CATALOG_HASH,
    catalog_size: str = "26624",
    revision: str = "30536",
    timestamp: str = "1793657696",
    branch: str = "(default)",
) -> str:
    return (
        f"{snapshot} {root_catalog_hash} {catalog_size} "
        f"{revision} {timestamp} {branch}"
    )


class TestCvmfsSnapshot(unittest.TestCase):

    def test_snapshot_is_frozen(self):
        snapshot = CvmfsSnapshot(
            repository=REPOSITORY,
            snapshot=SNAPSHOT,
            revision=30536,
            root_catalog_hash=ROOT_CATALOG_HASH,
        )

        with self.assertRaises(AttributeError):
            snapshot.revision = (  # pyright: ignore[reportAttributeAccessIssue]
                30537
            )

    def test_rejects_empty_repository(self):
        for repository in ("", "   "):
            with self.subTest(repository=repository), self.assertRaises(
                CvmfsSnapshotValidationError
            ):
                CvmfsSnapshot(
                    repository=repository,
                    snapshot=SNAPSHOT,
                    revision=30536,
                    root_catalog_hash=ROOT_CATALOG_HASH,
                )

    def test_rejects_empty_snapshot(self):
        for snapshot in ("", "   "):
            with self.subTest(snapshot=snapshot), self.assertRaises(
                CvmfsSnapshotValidationError
            ):
                CvmfsSnapshot(
                    repository=REPOSITORY,
                    snapshot=snapshot,
                    revision=30536,
                    root_catalog_hash=ROOT_CATALOG_HASH,
                )

    def test_rejects_invalid_revision(self):
        for revision in (True, 0, -1):
            with self.subTest(revision=revision), self.assertRaises(
                CvmfsSnapshotValidationError
            ):
                CvmfsSnapshot(
                    repository=REPOSITORY,
                    snapshot=SNAPSHOT,
                    revision=revision,
                    root_catalog_hash=ROOT_CATALOG_HASH,
                )

    def test_rejects_invalid_root_catalog_hash(self):
        invalid_hashes = (
            "",
            "   ",
            "2c1a337d7e0960b63cff163cb633904d7ea1974",
            "2c1a337d7e0960b63cff163cb633904d7ea1974g",
            ROOT_CATALOG_HASH.upper(),
        )

        for root_hash in invalid_hashes:
            with self.subTest(root_hash=root_hash), self.assertRaises(
                CvmfsSnapshotValidationError
            ):
                CvmfsSnapshot(
                    repository=REPOSITORY,
                    snapshot=SNAPSHOT,
                    revision=30536,
                    root_catalog_hash=root_hash,
                )


class TestParseCvmfsTagOutput(unittest.TestCase):

    def test_parses_real_cvmfs_2_14_1_output(self):
        result = parse_cvmfs_tag_output(
            REPOSITORY,
            SNAPSHOT,
            TAG_OUTPUT,
        )

        self.assertEqual(
            result,
            CvmfsSnapshot(
                repository=REPOSITORY,
                snapshot=SNAPSHOT,
                revision=30536,
                root_catalog_hash=ROOT_CATALOG_HASH,
            ),
        )

    def test_preserves_source_metadata(self):
        result = parse_cvmfs_tag_inspection(
            REPOSITORY,
            SNAPSHOT,
            TAG_OUTPUT,
        )

        self.assertEqual(result.catalog_size_bytes, 26624)
        self.assertEqual(result.snapshot_timestamp, 1793657696)
        self.assertEqual(result.branch, "(default)")

    def test_accepts_surrounding_blank_lines(self):
        result = parse_cvmfs_tag_output(
            REPOSITORY,
            SNAPSHOT,
            f"\n{TAG_OUTPUT}\n\n",
        )

        self.assertEqual(result.revision, 30536)

    def test_rejects_empty_output(self):
        for output in ("", "\n\n"):
            with self.subTest(output=output), self.assertRaises(
                CvmfsTagOutputError
            ):
                parse_cvmfs_tag_output(
                    REPOSITORY,
                    SNAPSHOT,
                    output,
                )

    def test_rejects_multiple_non_empty_lines(self):
        with self.assertRaises(CvmfsTagOutputError):
            parse_cvmfs_tag_output(
                REPOSITORY,
                SNAPSHOT,
                f"{TAG_OUTPUT}\n{TAG_OUTPUT}",
            )

    def test_rejects_wrong_field_count(self):
        for output in (
            " ".join(TAG_OUTPUT.split()[:-1]),
            f"{TAG_OUTPUT} unexpected",
        ):
            with self.subTest(output=output), self.assertRaises(
                CvmfsTagOutputError
            ):
                parse_cvmfs_tag_output(
                    REPOSITORY,
                    SNAPSHOT,
                    output,
                )

    def test_rejects_snapshot_mismatch(self):
        with self.assertRaises(CvmfsSnapshotMismatch):
            parse_cvmfs_tag_output(
                REPOSITORY,
                SNAPSHOT,
                make_tag_output(snapshot="something-else"),
            )

    def test_rejects_invalid_root_catalog_hash(self):
        for root_hash in (
            "not-a-hash",
            ROOT_CATALOG_HASH.upper(),
        ):
            with self.subTest(root_hash=root_hash), self.assertRaises(
                CvmfsTagOutputError
            ):
                parse_cvmfs_tag_output(
                    REPOSITORY,
                    SNAPSHOT,
                    make_tag_output(root_catalog_hash=root_hash),
                )

    def test_rejects_non_decimal_numeric_fields(self):
        invalid_fields = (
            {"catalog_size": "26KiB"},
            {"revision": "30.536"},
            {"timestamp": "2026-11-02"},
        )

        for fields in invalid_fields:
            with self.subTest(fields=fields), self.assertRaises(
                CvmfsTagOutputError
            ):
                parse_cvmfs_tag_output(
                    REPOSITORY,
                    SNAPSHOT,
                    make_tag_output(**fields),
                )

    def test_rejects_non_positive_revision(self):
        for revision in ("0", "-1"):
            with self.subTest(revision=revision), self.assertRaises(
                CvmfsTagOutputError
            ):
                parse_cvmfs_tag_output(
                    REPOSITORY,
                    SNAPSHOT,
                    make_tag_output(revision=revision),
                )

    def test_rejects_non_positive_timestamp(self):
        for timestamp in ("0", "-1"):
            with self.subTest(timestamp=timestamp), self.assertRaises(
                CvmfsTagOutputError
            ):
                parse_cvmfs_tag_output(
                    REPOSITORY,
                    SNAPSHOT,
                    make_tag_output(timestamp=timestamp),
                )

    def test_rejects_negative_catalog_size(self):
        with self.assertRaises(CvmfsTagOutputError):
            parse_cvmfs_tag_output(
                REPOSITORY,
                SNAPSHOT,
                make_tag_output(catalog_size="-1"),
            )

    def test_rejects_empty_requested_identity(self):
        for repository, snapshot in (
            ("", SNAPSHOT),
            (REPOSITORY, ""),
        ):
            with self.subTest(
                repository=repository,
                snapshot=snapshot,
            ), self.assertRaises(CvmfsSnapshotValidationError):
                parse_cvmfs_tag_output(
                    repository,
                    snapshot,
                    TAG_OUTPUT,
                )


if __name__ == "__main__":
    unittest.main()
