import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .cvmfs import (
    CvmfsProvenanceError,
    CvmfsSnapshot,
    parse_cvmfs_tag_inspection,
)

CVMFS_PROVENANCE_SCHEMA_VERSION = 1
CVMFS_PROVENANCE_SOURCE_TYPE = "cvmfs_server_tag"


class CvmfsProvenanceDocumentError(CvmfsProvenanceError):
    """A canonical CVMFS provenance document is invalid."""


@dataclass(frozen=True)
class CvmfsProvenanceSource:
    """Audit metadata from the manual CVMFS tag inspection."""

    cvmfs_version: str
    catalog_size_bytes: int
    snapshot_timestamp: int
    branch: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.cvmfs_version, str)
            or not self.cvmfs_version.strip()
        ):
            raise CvmfsProvenanceDocumentError(
                "CVMFS version must be a non-empty string"
            )

        if not isinstance(self.branch, str) or not self.branch.strip():
            raise CvmfsProvenanceDocumentError(
                "CVMFS branch must be a non-empty string"
            )


@dataclass(frozen=True)
class CvmfsProvenanceDocument:
    """Canonical manual handoff for one named CVMFS snapshot."""

    snapshot: CvmfsSnapshot
    source: CvmfsProvenanceSource
    schema_version: int = CVMFS_PROVENANCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CVMFS_PROVENANCE_SCHEMA_VERSION:
            raise CvmfsProvenanceDocumentError(
                f"Unsupported CVMFS provenance schema version: "
                f"{self.schema_version}"
            )


def create_cvmfs_provenance_document(
    repository: str,
    snapshot: str,
    tag_output: str,
    cvmfs_version: str,
) -> CvmfsProvenanceDocument:
    """Create canonical provenance from captured CVMFS command output."""

    inspection = parse_cvmfs_tag_inspection(
        repository,
        snapshot,
        tag_output,
    )

    return CvmfsProvenanceDocument(
        snapshot=inspection.snapshot,
        source=CvmfsProvenanceSource(
            cvmfs_version=cvmfs_version,
            catalog_size_bytes=inspection.catalog_size_bytes,
            snapshot_timestamp=inspection.snapshot_timestamp,
            branch=inspection.branch,
        ),
    )


def cvmfs_provenance_to_dict(
    document: CvmfsProvenanceDocument,
) -> dict[str, object]:
    """Convert a CVMFS provenance document to its JSON representation."""

    snapshot = document.snapshot
    source = document.source

    return {
        "schema_version": document.schema_version,
        "repository": snapshot.repository,
        "snapshot": snapshot.snapshot,
        "revision": snapshot.revision,
        "root_catalog_hash": snapshot.root_catalog_hash,
        "source": {
            "type": CVMFS_PROVENANCE_SOURCE_TYPE,
            "cvmfs_version": source.cvmfs_version,
            "catalog_size_bytes": source.catalog_size_bytes,
            "snapshot_timestamp": source.snapshot_timestamp,
            "branch": source.branch,
        },
    }


def serialize_cvmfs_provenance(
    document: CvmfsProvenanceDocument,
) -> str:
    """Serialize CVMFS provenance as deterministic, human-readable JSON."""

    return (
        json.dumps(
            cvmfs_provenance_to_dict(document),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def write_cvmfs_provenance(
    path: Path,
    document: CvmfsProvenanceDocument,
) -> None:
    """Write a canonical CVMFS provenance document."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        serialize_cvmfs_provenance(document),
        encoding="utf-8",
    )


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert captured cvmfs_server tag output into canonical "
            "CVMFS provenance JSON."
        )
    )
    parser.add_argument(
        "--repository",
        required=True,
        help="Fully qualified CVMFS repository name",
    )
    parser.add_argument(
        "--snapshot",
        required=True,
        help="Named CVMFS snapshot inspected by the operator",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="File containing captured cvmfs_server tag -i -x output",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Canonical provenance JSON file to create",
    )
    parser.add_argument(
        "--cvmfs-version",
        required=True,
        help="CVMFS version used for the manual inspection",
    )

    args = parser.parse_args(argv)
    tag_output = args.input.read_text(encoding="utf-8")
    document = create_cvmfs_provenance_document(
        repository=args.repository,
        snapshot=args.snapshot,
        tag_output=tag_output,
        cvmfs_version=args.cvmfs_version,
    )
    write_cvmfs_provenance(args.output, document)


if __name__ == "__main__":
    main()
