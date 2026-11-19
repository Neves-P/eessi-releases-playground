import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, cast

from .component_release import get_component_release
from .cvmfs_provenance import (
    load_cvmfs_provenance,
    require_cvmfs_provenance_identity,
)
from .revision import (
    ComponentRole,
    EESSIRevision,
    RevisionComponent,
    RevisionError,
)
from .revision_manifest import (
    load_revision_manifest,
    write_revision_manifest,
)


class RevisionCreationError(RevisionError):
    """Inputs for coordinated revision creation are invalid."""


@dataclass(frozen=True)
class ComponentRequest:
    """A component role and exact GitHub release to resolve."""

    role: ComponentRole
    repository: str
    tag: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, ComponentRole):
            raise RevisionCreationError(
                "Component request role has an invalid type"
            )

        if not isinstance(self.repository, str) or not self.repository.strip():
            raise RevisionCreationError(
                "Component request repository must be a non-empty string"
            )

        if not isinstance(self.tag, str) or not self.tag.strip():
            raise RevisionCreationError(
                "Component request tag must be a non-empty string"
            )


def create_revision_manifest(
    revision: str,
    component_requests: Sequence[ComponentRequest],
    cvmfs_provenance_path: Path,
    expected_cvmfs_repository: str,
    expected_cvmfs_snapshot: str,
    output_path: Path,
    *,
    sandbox: bool = True,
) -> EESSIRevision:
    """Resolve provenance and write one coordinated revision manifest."""

    cvmfs = load_cvmfs_provenance(cvmfs_provenance_path)
    require_cvmfs_provenance_identity(
        cvmfs,
        expected_cvmfs_repository,
        expected_cvmfs_snapshot,
    )

    components = tuple(
        RevisionComponent(
            role=request.role,
            release=get_component_release(
                request.repository,
                request.tag,
                sandbox=sandbox,
            ),
        )
        for request in component_requests
    )
    coordinated_revision = EESSIRevision(
        revision=revision,
        components=components,
        cvmfs=cvmfs,
    )

    write_revision_manifest(output_path, coordinated_revision)

    return load_revision_manifest(output_path)


def _component_requests_from_args(
    parser: argparse.ArgumentParser,
    values: list[list[str]],
) -> tuple[ComponentRequest, ...]:
    requests = []
    supported_roles = ", ".join(role.value for role in ComponentRole)

    for role_text, repository, tag in values:
        try:
            role = ComponentRole(role_text)
        except ValueError:
            parser.error(
                f"unsupported component role {role_text!r}; "
                f"choose one of: {supported_roles}"
            )

        requests.append(
            ComponentRequest(
                role=role,
                repository=repository,
                tag=tag,
            )
        )

    return tuple(requests)


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve component releases and create a coordinated "
            "EESSI revision manifest."
        )
    )
    parser.add_argument(
        "--revision",
        required=True,
        help="Coordinated EESSI revision name",
    )
    parser.add_argument(
        "--component",
        required=True,
        action="append",
        nargs=3,
        metavar=("ROLE", "REPOSITORY", "TAG"),
        help="Component role, GitHub repository, and exact release tag",
    )
    parser.add_argument(
        "--cvmfs-provenance",
        required=True,
        type=Path,
        help="Canonical CVMFS provenance JSON file",
    )
    parser.add_argument(
        "--cvmfs-repository",
        required=True,
        help="Expected CVMFS repository name",
    )
    parser.add_argument(
        "--cvmfs-snapshot",
        required=True,
        help="Expected named CVMFS snapshot",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Revision manifest JSON file to create",
    )
    parser.add_argument(
        "--zenodo-production",
        action="store_true",
        help="Query production Zenodo instead of Zenodo Sandbox",
    )

    args = parser.parse_args(argv)
    component_values = cast(list[list[str]], args.component)
    component_requests = _component_requests_from_args(
        parser,
        component_values,
    )

    create_revision_manifest(
        revision=args.revision,
        component_requests=component_requests,
        cvmfs_provenance_path=args.cvmfs_provenance,
        expected_cvmfs_repository=args.cvmfs_repository,
        expected_cvmfs_snapshot=args.cvmfs_snapshot,
        output_path=args.output,
        sandbox=not args.zenodo_production,
    )


if __name__ == "__main__":
    main()
