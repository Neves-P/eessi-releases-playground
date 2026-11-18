from dataclasses import InitVar, dataclass
from enum import Enum

from .component_release import ComponentRelease
from .cvmfs_provenance import CvmfsProvenanceDocument


class RevisionError(RuntimeError):
    """Base exception for coordinated EESSI revision failures."""


class RevisionValidationError(RevisionError):
    """A coordinated EESSI revision contains invalid data."""


class DuplicateComponentRole(RevisionValidationError):
    """A component role occurs more than once in a revision."""


class DuplicateComponentRepository(RevisionValidationError):
    """A GitHub repository occurs more than once in a revision."""


class MissingComponentRoles(RevisionValidationError):
    """A revision does not contain all roles required by its policy."""


class ComponentRole(str, Enum):
    """Stable semantic roles for independently released EESSI components."""

    SOFTWARE_LAYER = "software_layer"
    COMPATIBILITY_LAYER = "compatibility_layer"
    FILESYSTEM_LAYER = "filesystem_layer"
    DOCUMENTATION = "documentation"
    SOFTWARE_LAYER_SCRIPTS = "software_layer_scripts"


POC_REQUIRED_COMPONENT_ROLES = frozenset({ComponentRole.SOFTWARE_LAYER})
PRODUCTION_REQUIRED_COMPONENT_ROLES = frozenset(ComponentRole)


@dataclass(frozen=True)
class RevisionComponent:
    """One component release assigned to its role in an EESSI revision."""

    role: ComponentRole
    release: ComponentRelease

    def __post_init__(self) -> None:
        if not isinstance(self.role, ComponentRole):
            raise RevisionValidationError(
                "Revision component role has an invalid type"
            )

        if not isinstance(self.release, ComponentRelease):
            raise RevisionValidationError(
                "Revision component release has an invalid type"
            )


@dataclass(frozen=True)
class EESSIRevision:
    """Validated binding of component releases and one CVMFS snapshot."""

    revision: str
    components: tuple[RevisionComponent, ...]
    cvmfs: CvmfsProvenanceDocument
    required_roles: InitVar[frozenset[ComponentRole]] = (
        POC_REQUIRED_COMPONENT_ROLES
    )

    def __post_init__(
        self,
        required_roles: frozenset[ComponentRole],
    ) -> None:
        if not isinstance(self.revision, str) or not self.revision.strip():
            raise RevisionValidationError(
                "EESSI revision must be a non-empty string"
            )

        if not isinstance(self.components, tuple) or not all(
            isinstance(component, RevisionComponent)
            for component in self.components
        ):
            raise RevisionValidationError(
                "EESSI revision components must be a tuple of "
                "RevisionComponent objects"
            )

        if not isinstance(self.cvmfs, CvmfsProvenanceDocument):
            raise RevisionValidationError(
                "EESSI revision CVMFS provenance has an invalid type"
            )

        if (
            not isinstance(required_roles, frozenset)
            or not required_roles
            or not all(
                isinstance(role, ComponentRole)
                for role in required_roles
            )
        ):
            raise RevisionValidationError(
                "Required component roles must be a non-empty frozenset "
                "of ComponentRole values"
            )

        roles: set[ComponentRole] = set()
        repositories: set[str] = set()

        for component in self.components:
            if component.role in roles:
                raise DuplicateComponentRole(
                    f"Duplicate EESSI component role: "
                    f"{component.role.value}"
                )

            roles.add(component.role)
            repository = component.release.repository.casefold()

            if repository in repositories:
                raise DuplicateComponentRepository(
                    "Duplicate EESSI component repository: "
                    f"{component.release.repository}"
                )

            repositories.add(repository)

        missing_roles = required_roles - roles

        if missing_roles:
            formatted_roles = ", ".join(
                sorted(role.value for role in missing_roles)
            )
            raise MissingComponentRoles(
                f"EESSI revision is missing required component roles: "
                f"{formatted_roles}"
            )
