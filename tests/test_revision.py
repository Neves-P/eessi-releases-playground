import unittest
from typing import cast

from eessi_revisions.component_release import ComponentRelease
from eessi_revisions.cvmfs_provenance import (
    CvmfsProvenanceDocument,
    create_cvmfs_provenance_document,
)
from eessi_revisions.revision import (
    POC_REQUIRED_COMPONENT_ROLES,
    PRODUCTION_REQUIRED_COMPONENT_ROLES,
    ComponentRole,
    DuplicateComponentRepository,
    DuplicateComponentRole,
    EESSIRevision,
    MissingComponentRoles,
    RevisionComponent,
    RevisionValidationError,
)

REVISION = "eessi-2026.09-poc.1"
SOFTWARE_REPOSITORY = "Neves-P/software-layer"
TAG_OUTPUT = (
    "software.eessi.io-rev0006 "
    "2c1a337d7e0960b63cff163cb633904d7ea19744 "
    "26624 30536 1793657696 (default)\n"
)


def make_release(
    repository: str = SOFTWARE_REPOSITORY,
) -> ComponentRelease:
    return ComponentRelease(
        repository=repository,
        tag=REVISION,
        commit="0123456789abcdef0123456789abcdef01234567",
        github_release_url=(
            f"https://github.com/{repository}/releases/tag/{REVISION}"
        ),
        is_immutable=True,
        doi="10.5072/zenodo.598123",
        concept_doi="10.5072/zenodo.598122",
    )


def make_component(
    role: ComponentRole = ComponentRole.SOFTWARE_LAYER,
    repository: str = SOFTWARE_REPOSITORY,
) -> RevisionComponent:
    return RevisionComponent(
        role=role,
        release=make_release(repository),
    )


def make_cvmfs_provenance() -> CvmfsProvenanceDocument:
    return create_cvmfs_provenance_document(
        repository="software.eessi.io",
        snapshot="software.eessi.io-rev0006",
        tag_output=TAG_OUTPUT,
        cvmfs_version="2.14.1",
    )


class TestRevisionComponent(unittest.TestCase):

    def test_binds_role_to_component_release(self):
        component = make_component()

        self.assertEqual(component.role, ComponentRole.SOFTWARE_LAYER)
        self.assertEqual(component.release.repository, SOFTWARE_REPOSITORY)

    def test_is_frozen(self):
        component = make_component()

        with self.assertRaises(AttributeError):
            component.role = (  # pyright: ignore[reportAttributeAccessIssue]
                ComponentRole.DOCUMENTATION
            )

    def test_rejects_invalid_role_type(self):
        with self.assertRaises(RevisionValidationError):
            RevisionComponent(
                role=cast(ComponentRole, "unsupported"),
                release=make_release(),
            )

    def test_rejects_invalid_release_type(self):
        with self.assertRaises(RevisionValidationError):
            RevisionComponent(
                role=ComponentRole.SOFTWARE_LAYER,
                release=cast(ComponentRelease, object()),
            )


class TestEESSIRevision(unittest.TestCase):

    def test_poc_requires_only_software_layer(self):
        revision = EESSIRevision(
            revision=REVISION,
            components=(make_component(),),
            cvmfs=make_cvmfs_provenance(),
        )

        self.assertEqual(revision.revision, REVISION)
        self.assertEqual(len(revision.components), 1)
        self.assertEqual(
            revision.cvmfs.snapshot.revision,
            30536,
        )
        self.assertEqual(
            POC_REQUIRED_COMPONENT_ROLES,
            frozenset({ComponentRole.SOFTWARE_LAYER}),
        )

    def test_poc_allows_additional_supported_components(self):
        revision = EESSIRevision(
            revision=REVISION,
            components=(
                make_component(),
                make_component(
                    ComponentRole.DOCUMENTATION,
                    "EESSI/docs",
                ),
            ),
            cvmfs=make_cvmfs_provenance(),
        )

        self.assertEqual(len(revision.components), 2)

    def test_production_requires_all_component_roles(self):
        components = tuple(
            make_component(role, f"EESSI/{role.value}")
            for role in ComponentRole
        )

        revision = EESSIRevision(
            revision="eessi-2026.09",
            components=components,
            cvmfs=make_cvmfs_provenance(),
            required_roles=PRODUCTION_REQUIRED_COMPONENT_ROLES,
        )

        self.assertEqual(
            {component.role for component in revision.components},
            set(ComponentRole),
        )
        self.assertEqual(
            PRODUCTION_REQUIRED_COMPONENT_ROLES,
            frozenset(ComponentRole),
        )

    def test_production_rejects_missing_roles(self):
        with self.assertRaisesRegex(
            MissingComponentRoles,
            "compatibility_layer",
        ):
            EESSIRevision(
                revision="eessi-2026.09",
                components=(make_component(),),
                cvmfs=make_cvmfs_provenance(),
                required_roles=PRODUCTION_REQUIRED_COMPONENT_ROLES,
            )

    def test_rejects_duplicate_roles(self):
        with self.assertRaisesRegex(
            DuplicateComponentRole,
            "software_layer",
        ):
            EESSIRevision(
                revision=REVISION,
                components=(
                    make_component(),
                    make_component(
                        ComponentRole.SOFTWARE_LAYER,
                        "EESSI/other-software-layer",
                    ),
                ),
                cvmfs=make_cvmfs_provenance(),
            )

    def test_rejects_duplicate_repositories_case_insensitively(self):
        with self.assertRaisesRegex(
            DuplicateComponentRepository,
            "neves-p/SOFTWARE-LAYER",
        ):
            EESSIRevision(
                revision=REVISION,
                components=(
                    make_component(),
                    make_component(
                        ComponentRole.DOCUMENTATION,
                        "neves-p/SOFTWARE-LAYER",
                    ),
                ),
                cvmfs=make_cvmfs_provenance(),
            )

    def test_rejects_missing_poc_software_layer(self):
        with self.assertRaisesRegex(
            MissingComponentRoles,
            "software_layer",
        ):
            EESSIRevision(
                revision=REVISION,
                components=(
                    make_component(
                        ComponentRole.DOCUMENTATION,
                        "EESSI/docs",
                    ),
                ),
                cvmfs=make_cvmfs_provenance(),
            )

    def test_rejects_empty_revision(self):
        for value in ("", "   "):
            with self.subTest(value=value), self.assertRaises(
                RevisionValidationError
            ):
                EESSIRevision(
                    revision=value,
                    components=(make_component(),),
                    cvmfs=make_cvmfs_provenance(),
                )

    def test_rejects_mutable_component_collection(self):
        with self.assertRaises(RevisionValidationError):
            EESSIRevision(
                revision=REVISION,
                components=cast(
                    tuple[RevisionComponent, ...],
                    [make_component()],
                ),
                cvmfs=make_cvmfs_provenance(),
            )

    def test_rejects_invalid_cvmfs_type(self):
        with self.assertRaises(RevisionValidationError):
            EESSIRevision(
                revision=REVISION,
                components=(make_component(),),
                cvmfs=cast(CvmfsProvenanceDocument, object()),
            )

    def test_rejects_invalid_required_role_policy(self):
        invalid_policies = (
            frozenset(),
            cast(
                frozenset[ComponentRole],
                frozenset({"unsupported"}),
            ),
        )

        for policy in invalid_policies:
            with self.subTest(policy=policy), self.assertRaises(
                RevisionValidationError
            ):
                EESSIRevision(
                    revision=REVISION,
                    components=(make_component(),),
                    cvmfs=make_cvmfs_provenance(),
                    required_roles=policy,
                )

    def test_is_frozen(self):
        revision = EESSIRevision(
            revision=REVISION,
            components=(make_component(),),
            cvmfs=make_cvmfs_provenance(),
        )

        with self.assertRaises(AttributeError):
            revision.revision = (  # pyright: ignore[reportAttributeAccessIssue]
                "something-else"
            )


if __name__ == "__main__":
    unittest.main()
