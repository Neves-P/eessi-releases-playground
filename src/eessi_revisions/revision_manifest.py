import json
import re
from pathlib import Path
from typing import cast

from .component_release import ComponentRelease
from .cvmfs_provenance import (
    CvmfsProvenanceDocumentError,
    cvmfs_provenance_from_dict,
    cvmfs_provenance_to_dict,
)
from .revision import (
    POC_REQUIRED_COMPONENT_ROLES,
    ComponentRole,
    EESSIRevision,
    RevisionComponent,
    RevisionError,
    RevisionValidationError,
)

REVISION_MANIFEST_SCHEMA_VERSION = 1

_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "revision",
        "components",
        "cvmfs",
    }
)
_COMPONENT_FIELDS = frozenset(
    {
        "role",
        "repository",
        "tag",
        "commit",
        "github_release_url",
        "is_immutable",
        "doi",
        "concept_doi",
    }
)
_GIT_COMMIT = re.compile(r"[0-9a-f]{40}")


class RevisionManifestError(RevisionError):
    """A coordinated EESSI revision manifest is invalid."""


class UnsupportedRevisionManifestSchema(RevisionManifestError):
    """A revision manifest uses an unsupported schema version."""


def _component_to_dict(
    component: RevisionComponent,
) -> dict[str, object]:
    release = component.release

    return {
        "role": component.role.value,
        "repository": release.repository,
        "tag": release.tag,
        "commit": release.commit,
        "github_release_url": release.github_release_url,
        "is_immutable": release.is_immutable,
        "doi": release.doi,
        "concept_doi": release.concept_doi,
    }


def revision_manifest_to_dict(
    revision: EESSIRevision,
) -> dict[str, object]:
    """Convert a coordinated revision to its manifest representation."""

    components = sorted(
        revision.components,
        key=lambda component: component.role.value,
    )

    return {
        "schema_version": REVISION_MANIFEST_SCHEMA_VERSION,
        "revision": revision.revision,
        "components": [
            _component_to_dict(component) for component in components
        ],
        "cvmfs": cvmfs_provenance_to_dict(revision.cvmfs),
    }


def serialize_revision_manifest(revision: EESSIRevision) -> str:
    """Serialize a revision manifest as deterministic, readable JSON."""

    return (
        json.dumps(
            revision_manifest_to_dict(revision),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def write_revision_manifest(
    path: Path,
    revision: EESSIRevision,
) -> None:
    """Write a canonical coordinated revision manifest."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        serialize_revision_manifest(revision),
        encoding="utf-8",
    )


def _as_mapping(
    value: object,
    context: str,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RevisionManifestError(f"{context} must be a JSON object")

    if not all(isinstance(key, str) for key in value):
        raise RevisionManifestError(
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

        raise RevisionManifestError(
            f"{context} has invalid fields ({'; '.join(details)})"
        )


def _require_string(
    mapping: dict[str, object],
    field: str,
    context: str,
) -> str:
    value = mapping[field]

    if not isinstance(value, str) or not value.strip():
        raise RevisionManifestError(
            f"{context} field {field!r} must be a non-empty string"
        )

    return value


def _require_boolean(
    mapping: dict[str, object],
    field: str,
    context: str,
) -> bool:
    value = mapping[field]

    if not isinstance(value, bool):
        raise RevisionManifestError(
            f"{context} field {field!r} must be a boolean"
        )

    return value


def _component_from_dict(
    payload: object,
    index: int,
) -> RevisionComponent:
    context = f"Revision manifest component {index}"
    mapping = _as_mapping(payload, context)
    _require_exact_fields(mapping, _COMPONENT_FIELDS, context)

    role_value = _require_string(mapping, "role", context)

    try:
        role = ComponentRole(role_value)
    except ValueError as exc:
        raise RevisionManifestError(
            f"{context} has unsupported role: {role_value!r}"
        ) from exc

    commit = _require_string(mapping, "commit", context)

    if _GIT_COMMIT.fullmatch(commit) is None:
        raise RevisionManifestError(
            f"{context} field 'commit' must be 40 lowercase "
            "hexadecimal characters"
        )

    release = ComponentRelease(
        repository=_require_string(mapping, "repository", context),
        tag=_require_string(mapping, "tag", context),
        commit=commit,
        github_release_url=_require_string(
            mapping,
            "github_release_url",
            context,
        ),
        is_immutable=_require_boolean(
            mapping,
            "is_immutable",
            context,
        ),
        doi=_require_string(mapping, "doi", context),
        concept_doi=_require_string(mapping, "concept_doi", context),
    )

    return RevisionComponent(role=role, release=release)


def revision_manifest_from_dict(
    payload: object,
    *,
    required_roles: frozenset[ComponentRole] = (
        POC_REQUIRED_COMPONENT_ROLES
    ),
) -> EESSIRevision:
    """Validate a JSON-compatible object as a revision manifest."""

    mapping = _as_mapping(payload, "Revision manifest")
    _require_exact_fields(
        mapping,
        _TOP_LEVEL_FIELDS,
        "Revision manifest",
    )

    schema_version = mapping["schema_version"]

    if isinstance(schema_version, bool) or not isinstance(
        schema_version,
        int,
    ):
        raise RevisionManifestError(
            "Revision manifest field 'schema_version' must be an integer"
        )

    if schema_version != REVISION_MANIFEST_SCHEMA_VERSION:
        raise UnsupportedRevisionManifestSchema(
            f"Unsupported revision manifest schema version: "
            f"{schema_version}"
        )

    revision = _require_string(mapping, "revision", "Revision manifest")
    components_payload = mapping["components"]

    if not isinstance(components_payload, list):
        raise RevisionManifestError(
            "Revision manifest field 'components' must be a JSON array"
        )

    components = tuple(
        _component_from_dict(component, index)
        for index, component in enumerate(components_payload)
    )

    try:
        cvmfs = cvmfs_provenance_from_dict(mapping["cvmfs"])
    except CvmfsProvenanceDocumentError as exc:
        raise RevisionManifestError(
            f"Revision manifest contains invalid CVMFS provenance: {exc}"
        ) from exc

    try:
        return EESSIRevision(
            revision=revision,
            components=components,
            cvmfs=cvmfs,
            required_roles=required_roles,
        )
    except RevisionValidationError as exc:
        raise RevisionManifestError(
            f"Revision manifest violates revision policy: {exc}"
        ) from exc


def _reject_duplicate_fields(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    mapping: dict[str, object] = {}

    for key, value in pairs:
        if key in mapping:
            raise RevisionManifestError(
                f"Duplicate JSON field: {key!r}"
            )

        mapping[key] = value

    return mapping


def _require_json_text(value: object) -> str:
    if not isinstance(value, str):
        raise RevisionManifestError(
            "Revision manifest JSON must be a string"
        )

    return value


def deserialize_revision_manifest(
    text: str,
    *,
    required_roles: frozenset[ComponentRole] = (
        POC_REQUIRED_COMPONENT_ROLES
    ),
) -> EESSIRevision:
    """Deserialize and strictly validate revision manifest JSON."""

    json_text = _require_json_text(text)

    try:
        payload = json.loads(
            json_text,
            object_pairs_hook=_reject_duplicate_fields,
        )
    except json.JSONDecodeError as exc:
        raise RevisionManifestError(
            "Revision manifest file contains invalid JSON"
        ) from exc

    return revision_manifest_from_dict(
        payload,
        required_roles=required_roles,
    )


def load_revision_manifest(
    path: Path,
    *,
    required_roles: frozenset[ComponentRole] = (
        POC_REQUIRED_COMPONENT_ROLES
    ),
) -> EESSIRevision:
    """Load and strictly validate a coordinated revision manifest."""

    return deserialize_revision_manifest(
        path.read_text(encoding="utf-8"),
        required_roles=required_roles,
    )
