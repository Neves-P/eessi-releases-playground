import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, cast

from .cvmfs import (
    CvmfsProvenanceError,
    CvmfsSnapshot,
    parse_cvmfs_tag_inspection,
)

CVMFS_PROVENANCE_SCHEMA_VERSION = 1
CVMFS_PROVENANCE_SOURCE_TYPE = "cvmfs_server_tag"

_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "repository",
        "snapshot",
        "revision",
        "root_catalog_hash",
        "source",
    }
)
_SOURCE_FIELDS = frozenset(
    {
        "type",
        "cvmfs_version",
        "catalog_size_bytes",
        "snapshot_timestamp",
        "branch",
    }
)


class CvmfsProvenanceDocumentError(CvmfsProvenanceError):
    """A canonical CVMFS provenance document is invalid."""


class CvmfsProvenanceIdentityMismatch(CvmfsProvenanceDocumentError):
    """CVMFS provenance does not identify the expected snapshot."""


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

        if (
            isinstance(self.catalog_size_bytes, bool)
            or not isinstance(self.catalog_size_bytes, int)
            or self.catalog_size_bytes < 0
        ):
            raise CvmfsProvenanceDocumentError(
                "CVMFS catalog size must be a non-negative integer"
            )

        if (
            isinstance(self.snapshot_timestamp, bool)
            or not isinstance(self.snapshot_timestamp, int)
            or self.snapshot_timestamp <= 0
        ):
            raise CvmfsProvenanceDocumentError(
                "CVMFS snapshot timestamp must be a positive integer"
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
        if not isinstance(self.snapshot, CvmfsSnapshot):
            raise CvmfsProvenanceDocumentError(
                "CVMFS provenance snapshot has an invalid type"
            )

        if not isinstance(self.source, CvmfsProvenanceSource):
            raise CvmfsProvenanceDocumentError(
                "CVMFS provenance source has an invalid type"
            )

        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != CVMFS_PROVENANCE_SCHEMA_VERSION
        ):
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


def _as_mapping(
    value: object,
    context: str,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CvmfsProvenanceDocumentError(
            f"{context} must be a JSON object"
        )

    if not all(isinstance(key, str) for key in value):
        raise CvmfsProvenanceDocumentError(
            f"{context} field names must be strings"
        )

    return cast(dict[str, object], value)


def _require_exact_fields(
    mapping: dict[str, object],
    expected: frozenset[str],
    context: str,
) -> None:
    actual = set(mapping)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)

    if missing or unexpected:
        details = []

        if missing:
            details.append(f"missing fields: {', '.join(missing)}")

        if unexpected:
            details.append(
                f"unexpected fields: {', '.join(unexpected)}"
            )

        raise CvmfsProvenanceDocumentError(
            f"{context} has invalid fields ({'; '.join(details)})"
        )


def _require_string(
    mapping: dict[str, object],
    field: str,
    context: str,
) -> str:
    value = mapping[field]

    if not isinstance(value, str) or not value.strip():
        raise CvmfsProvenanceDocumentError(
            f"{context} field {field!r} must be a non-empty string"
        )

    return value


def _require_integer(
    mapping: dict[str, object],
    field: str,
    context: str,
    *,
    minimum: int,
) -> int:
    value = mapping[field]

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
    ):
        raise CvmfsProvenanceDocumentError(
            f"{context} field {field!r} must be an integer "
            f"of at least {minimum}"
        )

    return value


def cvmfs_provenance_from_dict(
    payload: object,
) -> CvmfsProvenanceDocument:
    """Validate a JSON-compatible object as CVMFS provenance."""

    mapping = _as_mapping(payload, "CVMFS provenance document")
    _require_exact_fields(
        mapping,
        _TOP_LEVEL_FIELDS,
        "CVMFS provenance document",
    )

    schema_version = _require_integer(
        mapping,
        "schema_version",
        "CVMFS provenance document",
        minimum=1,
    )

    if schema_version != CVMFS_PROVENANCE_SCHEMA_VERSION:
        raise CvmfsProvenanceDocumentError(
            f"Unsupported CVMFS provenance schema version: "
            f"{schema_version}"
        )

    repository = _require_string(
        mapping,
        "repository",
        "CVMFS provenance document",
    )
    snapshot_name = _require_string(
        mapping,
        "snapshot",
        "CVMFS provenance document",
    )
    revision = _require_integer(
        mapping,
        "revision",
        "CVMFS provenance document",
        minimum=1,
    )
    root_catalog_hash = _require_string(
        mapping,
        "root_catalog_hash",
        "CVMFS provenance document",
    )

    source_mapping = _as_mapping(
        mapping["source"],
        "CVMFS provenance source",
    )
    _require_exact_fields(
        source_mapping,
        _SOURCE_FIELDS,
        "CVMFS provenance source",
    )

    source_type = _require_string(
        source_mapping,
        "type",
        "CVMFS provenance source",
    )

    if source_type != CVMFS_PROVENANCE_SOURCE_TYPE:
        raise CvmfsProvenanceDocumentError(
            f"Unsupported CVMFS provenance source type: {source_type!r}"
        )

    source = CvmfsProvenanceSource(
        cvmfs_version=_require_string(
            source_mapping,
            "cvmfs_version",
            "CVMFS provenance source",
        ),
        catalog_size_bytes=_require_integer(
            source_mapping,
            "catalog_size_bytes",
            "CVMFS provenance source",
            minimum=0,
        ),
        snapshot_timestamp=_require_integer(
            source_mapping,
            "snapshot_timestamp",
            "CVMFS provenance source",
            minimum=1,
        ),
        branch=_require_string(
            source_mapping,
            "branch",
            "CVMFS provenance source",
        ),
    )

    try:
        snapshot = CvmfsSnapshot(
            repository=repository,
            snapshot=snapshot_name,
            revision=revision,
            root_catalog_hash=root_catalog_hash,
        )
    except CvmfsProvenanceError as exc:
        raise CvmfsProvenanceDocumentError(str(exc)) from exc

    return CvmfsProvenanceDocument(
        snapshot=snapshot,
        source=source,
        schema_version=schema_version,
    )


def _reject_duplicate_fields(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    mapping: dict[str, object] = {}

    for key, value in pairs:
        if key in mapping:
            raise CvmfsProvenanceDocumentError(
                f"Duplicate JSON field: {key!r}"
            )

        mapping[key] = value

    return mapping


def _require_json_text(value: object) -> str:
    if not isinstance(value, str):
        raise CvmfsProvenanceDocumentError(
            "CVMFS provenance JSON must be a string"
        )

    return value


def deserialize_cvmfs_provenance(
    text: str,
) -> CvmfsProvenanceDocument:
    """Deserialize and strictly validate CVMFS provenance JSON."""

    json_text = _require_json_text(text)

    try:
        payload = json.loads(
            json_text,
            object_pairs_hook=_reject_duplicate_fields,
        )
    except json.JSONDecodeError as exc:
        raise CvmfsProvenanceDocumentError(
            "CVMFS provenance file contains invalid JSON"
        ) from exc

    return cvmfs_provenance_from_dict(payload)


def load_cvmfs_provenance(
    path: Path,
) -> CvmfsProvenanceDocument:
    """Load and strictly validate a CVMFS provenance JSON file."""

    return deserialize_cvmfs_provenance(
        path.read_text(encoding="utf-8")
    )


def require_cvmfs_provenance_identity(
    document: CvmfsProvenanceDocument,
    repository: str,
    snapshot: str,
) -> None:
    """Require a provenance document to identify the expected snapshot."""

    actual = document.snapshot

    if actual.repository != repository or actual.snapshot != snapshot:
        raise CvmfsProvenanceIdentityMismatch(
            "CVMFS provenance identifies "
            f"{actual.repository}:{actual.snapshot}, expected "
            f"{repository}:{snapshot}"
        )


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
