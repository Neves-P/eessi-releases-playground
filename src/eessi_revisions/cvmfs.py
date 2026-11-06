import re
from dataclasses import dataclass

_ROOT_CATALOG_HASH = re.compile(r"[0-9a-f]{40}")
_DECIMAL_INTEGER = re.compile(r"[0-9]+")


class CvmfsProvenanceError(RuntimeError):
    """Base exception for CVMFS provenance failures."""


class CvmfsSnapshotValidationError(CvmfsProvenanceError):
    """A CVMFS snapshot contains invalid provenance fields."""


class CvmfsTagOutputError(CvmfsProvenanceError):
    """Machine-readable CVMFS tag output is malformed."""


class CvmfsSnapshotMismatch(CvmfsProvenanceError):
    """CVMFS returned a different snapshot than requested."""


@dataclass(frozen=True)
class CvmfsSnapshot:
    """Authoritative identity of a named CVMFS snapshot."""

    repository: str
    snapshot: str
    revision: int
    root_catalog_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.repository, str) or not self.repository.strip():
            raise CvmfsSnapshotValidationError(
                "CVMFS repository must be a non-empty string"
            )

        if not isinstance(self.snapshot, str) or not self.snapshot.strip():
            raise CvmfsSnapshotValidationError(
                "CVMFS snapshot must be a non-empty string"
            )

        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision <= 0
        ):
            raise CvmfsSnapshotValidationError(
                "CVMFS revision must be a positive integer"
            )

        if (
            not isinstance(self.root_catalog_hash, str)
            or _ROOT_CATALOG_HASH.fullmatch(
                self.root_catalog_hash
            ) is None
        ):
            raise CvmfsSnapshotValidationError(
                "CVMFS root catalog hash must be 40 lowercase "
                "hexadecimal characters"
            )


def _parse_decimal_field(
    field_name: str,
    value: str,
    *,
    minimum: int,
) -> int:
    if _DECIMAL_INTEGER.fullmatch(value) is None:
        raise CvmfsTagOutputError(
            f"CVMFS {field_name} must be a decimal integer"
        )

    parsed = int(value)

    if parsed < minimum:
        raise CvmfsTagOutputError(
            f"CVMFS {field_name} must be at least {minimum}"
        )

    return parsed


def parse_cvmfs_tag_output(
    repository: str,
    snapshot: str,
    output: str,
) -> CvmfsSnapshot:
    """Parse machine-readable output from ``cvmfs_server tag -i -x``.

    The command itself is intentionally not run here. The caller supplies
    output captured by an authorized operator on the CVMFS server.
    """

    if not isinstance(repository, str) or not repository.strip():
        raise CvmfsSnapshotValidationError(
            "CVMFS repository must be a non-empty string"
        )

    if not isinstance(snapshot, str) or not snapshot.strip():
        raise CvmfsSnapshotValidationError(
            "CVMFS snapshot must be a non-empty string"
        )

    if not isinstance(output, str):
        raise CvmfsTagOutputError(
            "CVMFS tag output must be a string"
        )

    lines = [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]

    if len(lines) != 1:
        raise CvmfsTagOutputError(
            "CVMFS tag output must contain exactly one non-empty line"
        )

    fields = lines[0].split()

    if len(fields) != 5:
        raise CvmfsTagOutputError(
            "CVMFS tag output must contain exactly five fields"
        )

    (
        returned_snapshot,
        root_catalog_hash,
        catalog_size_text,
        revision_text,
        timestamp_text,
    ) = fields

    if returned_snapshot != snapshot:
        raise CvmfsSnapshotMismatch(
            f"CVMFS returned snapshot {returned_snapshot!r}, "
            f"expected {snapshot!r}"
        )

    if _ROOT_CATALOG_HASH.fullmatch(root_catalog_hash) is None:
        raise CvmfsTagOutputError(
            "CVMFS root catalog hash must be 40 lowercase "
            "hexadecimal characters"
        )

    _parse_decimal_field(
        "catalog size",
        catalog_size_text,
        minimum=0,
    )
    revision = _parse_decimal_field(
        "revision",
        revision_text,
        minimum=1,
    )
    _parse_decimal_field(
        "timestamp",
        timestamp_text,
        minimum=1,
    )

    return CvmfsSnapshot(
        repository=repository,
        snapshot=snapshot,
        revision=revision,
        root_catalog_hash=root_catalog_hash,
    )
