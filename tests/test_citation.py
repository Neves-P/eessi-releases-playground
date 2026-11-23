import os
import unittest
from pathlib import Path
from unittest.mock import patch

from eessi_revisions.citation import main


class TestCitationMain(unittest.TestCase):

    @patch("eessi_revisions.citation.convert_zenodo_to_cff")
    def test_parses_input_and_output_paths(self, mock_convert):
        main(
            [
                "--input",
                "metadata/zenodo.json",
                "--output",
                "metadata/CITATION.cff",
            ]
        )

        mock_convert.assert_called_once_with(
            Path("metadata/zenodo.json"),
            Path("metadata/CITATION.cff"),
        )

    @patch("eessi_revisions.citation.convert_zenodo_to_cff")
    def test_uses_github_workspace_for_default_paths(self, mock_convert):
        with patch.dict(
            os.environ,
            {"GITHUB_WORKSPACE": "/workspace/eessi-revisions"},
        ):
            main([])

        workspace = Path("/workspace/eessi-revisions")
        mock_convert.assert_called_once_with(
            workspace / ".zenodo.json",
            workspace / "CITATION.cff",
        )


if __name__ == "__main__":
    unittest.main()
