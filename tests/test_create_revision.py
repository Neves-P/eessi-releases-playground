import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from eessi_revisions.component_release import ComponentRelease
from eessi_revisions.create_revision import (
    ComponentRequest,
    RevisionCreationError,
    create_revision_manifest,
    main,
)
from eessi_revisions.cvmfs_provenance import (
    CvmfsProvenanceIdentityMismatch,
    create_cvmfs_provenance_document,
    write_cvmfs_provenance,
)
from eessi_revisions.revision import ComponentRole
from eessi_revisions.revision_manifest import load_revision_manifest

REVISION = "eessi-2026.09-poc.1"
REPOSITORY = "Neves-P/software-layer"
TAG = "eessi-2026.09-poc.1"
COMMIT = "ba82ccf30517a2a22d801225875b0a4c791ba19b"
CVMFS_REPOSITORY = "software.eessi.io"
CVMFS_SNAPSHOT = "software.eessi.io-rev0006"
ROOT_CATALOG_HASH = "2c1a337d7e0960b63cff163cb633904d7ea19744"
TAG_OUTPUT = (
    f"{CVMFS_SNAPSHOT} {ROOT_CATALOG_HASH} "
    "26624 30536 1793657696 (default)\n"
)


def make_release() -> ComponentRelease:
    return ComponentRelease(
        repository=REPOSITORY,
        tag=TAG,
        commit=COMMIT,
        github_release_url=(
            "https://github.com/Neves-P/software-layer/"
            "releases/tag/eessi-2026.09-poc.1"
        ),
        is_immutable=False,
        doi="10.5072/zenodo.598123",
        concept_doi="10.5072/zenodo.598122",
    )


def write_cvmfs_input(path: Path) -> None:
    document = create_cvmfs_provenance_document(
        repository=CVMFS_REPOSITORY,
        snapshot=CVMFS_SNAPSHOT,
        tag_output=TAG_OUTPUT,
        cvmfs_version="2.14.1",
    )
    write_cvmfs_provenance(path, document)


class TestComponentRequest(unittest.TestCase):

    def test_accepts_exact_component_request(self):
        request = ComponentRequest(
            role=ComponentRole.SOFTWARE_LAYER,
            repository=REPOSITORY,
            tag=TAG,
        )

        self.assertEqual(request.role, ComponentRole.SOFTWARE_LAYER)
        self.assertEqual(request.repository, REPOSITORY)
        self.assertEqual(request.tag, TAG)

    def test_rejects_invalid_values(self):
        cases = (
            (cast(ComponentRole, "unknown"), REPOSITORY, TAG),
            (ComponentRole.SOFTWARE_LAYER, "", TAG),
            (ComponentRole.SOFTWARE_LAYER, REPOSITORY, "   "),
        )

        for role, repository, tag in cases:
            with self.subTest(
                role=role,
                repository=repository,
                tag=tag,
            ), self.assertRaises(RevisionCreationError):
                ComponentRequest(
                    role=role,
                    repository=repository,
                    tag=tag,
                )


class TestCreateRevisionManifest(unittest.TestCase):

    @patch(
        "eessi_revisions.create_revision.get_component_release"
    )
    def test_resolves_and_writes_strict_manifest(self, mock_get_release):
        mock_get_release.return_value = make_release()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cvmfs_path = root / "provenance" / "snapshot.json"
            output_path = root / "revisions" / f"{REVISION}.json"
            write_cvmfs_input(cvmfs_path)

            revision = create_revision_manifest(
                revision=REVISION,
                component_requests=(
                    ComponentRequest(
                        role=ComponentRole.SOFTWARE_LAYER,
                        repository=REPOSITORY,
                        tag=TAG,
                    ),
                ),
                cvmfs_provenance_path=cvmfs_path,
                expected_cvmfs_repository=CVMFS_REPOSITORY,
                expected_cvmfs_snapshot=CVMFS_SNAPSHOT,
                output_path=output_path,
                sandbox=False,
            )

            self.assertEqual(revision, load_revision_manifest(output_path))
            self.assertEqual(revision.revision, REVISION)
            self.assertEqual(revision.components[0].release.commit, COMMIT)
            self.assertEqual(
                revision.cvmfs.snapshot.root_catalog_hash,
                ROOT_CATALOG_HASH,
            )
            mock_get_release.assert_called_once_with(
                REPOSITORY,
                TAG,
                sandbox=False,
            )

    @patch(
        "eessi_revisions.create_revision.get_component_release"
    )
    def test_rejects_cvmfs_identity_before_network_lookup(
        self,
        mock_get_release,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cvmfs_path = root / "snapshot.json"
            output_path = root / "revision.json"
            write_cvmfs_input(cvmfs_path)

            with self.assertRaises(CvmfsProvenanceIdentityMismatch):
                create_revision_manifest(
                    revision=REVISION,
                    component_requests=(
                        ComponentRequest(
                            role=ComponentRole.SOFTWARE_LAYER,
                            repository=REPOSITORY,
                            tag=TAG,
                        ),
                    ),
                    cvmfs_provenance_path=cvmfs_path,
                    expected_cvmfs_repository=CVMFS_REPOSITORY,
                    expected_cvmfs_snapshot="different-snapshot",
                    output_path=output_path,
                )

            mock_get_release.assert_not_called()
            self.assertFalse(output_path.exists())


class TestCreateRevisionMain(unittest.TestCase):

    @patch(
        "eessi_revisions.create_revision.create_revision_manifest"
    )
    def test_parses_cli_arguments(self, mock_create):
        main(
            [
                "--revision",
                REVISION,
                "--component",
                "software_layer",
                REPOSITORY,
                TAG,
                "--cvmfs-provenance",
                "provenance/snapshot.json",
                "--cvmfs-repository",
                CVMFS_REPOSITORY,
                "--cvmfs-snapshot",
                CVMFS_SNAPSHOT,
                "--output",
                "revisions/revision.json",
                "--zenodo-production",
            ]
        )

        mock_create.assert_called_once_with(
            revision=REVISION,
            component_requests=(
                ComponentRequest(
                    role=ComponentRole.SOFTWARE_LAYER,
                    repository=REPOSITORY,
                    tag=TAG,
                ),
            ),
            cvmfs_provenance_path=Path("provenance/snapshot.json"),
            expected_cvmfs_repository=CVMFS_REPOSITORY,
            expected_cvmfs_snapshot=CVMFS_SNAPSHOT,
            output_path=Path("revisions/revision.json"),
            sandbox=False,
        )

    @patch(
        "eessi_revisions.create_revision.create_revision_manifest"
    )
    def test_uses_zenodo_sandbox_by_default(self, mock_create):
        main(
            [
                "--revision",
                REVISION,
                "--component",
                "software_layer",
                REPOSITORY,
                TAG,
                "--cvmfs-provenance",
                "provenance/snapshot.json",
                "--cvmfs-repository",
                CVMFS_REPOSITORY,
                "--cvmfs-snapshot",
                CVMFS_SNAPSHOT,
                "--output",
                "revisions/revision.json",
            ]
        )

        self.assertTrue(mock_create.call_args.kwargs["sandbox"])

    @patch(
        "eessi_revisions.create_revision.create_revision_manifest"
    )
    def test_rejects_unknown_component_role(self, mock_create):
        with self.assertRaises(SystemExit):
            main(
                [
                    "--revision",
                    REVISION,
                    "--component",
                    "unknown",
                    REPOSITORY,
                    TAG,
                    "--cvmfs-provenance",
                    "provenance/snapshot.json",
                    "--cvmfs-repository",
                    CVMFS_REPOSITORY,
                    "--cvmfs-snapshot",
                    CVMFS_SNAPSHOT,
                    "--output",
                    "revisions/revision.json",
                ]
            )

        mock_create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
