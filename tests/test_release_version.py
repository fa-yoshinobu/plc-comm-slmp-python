from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.check_release_version import (
    ROOT,
    source_versions,
    validate_dist,
    validate_source_versions,
    version_from_tag,
)

TEST_VERSION = source_versions()[0]
METADATA = f"Metadata-Version: 2.1\nName: plc-comm-slmp\nVersion: {TEST_VERSION}\n\n".encode()


class ReleaseVersionTests(unittest.TestCase):
    def test_release_workflow_is_bound_to_an_existing_tag(self) -> None:
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertIn("ref: refs/tags/${{ steps.release.outputs.tag }}", workflow)
        self.assertIn("set -euo pipefail", workflow)
        self.assertIn("--verify-tag", workflow)
        self.assertNotIn("v0.1.2", workflow)
        self.assertNotIn("--target ", workflow)

    def test_current_source_versions_match_release_tag(self) -> None:
        project_version, runtime_version = source_versions()
        self.assertEqual(runtime_version, project_version)
        self.assertEqual(validate_source_versions(f"v{project_version}"), project_version)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            validate_source_versions(f"v{project_version}.mismatch")
        with self.assertRaisesRegex(ValueError, "start with"):
            version_from_tag(project_version)

    def test_distribution_names_and_metadata_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            dist = Path(temporary_directory)
            wheel = dist / f"plc_comm_slmp-{TEST_VERSION}-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr(f"plc_comm_slmp-{TEST_VERSION}.dist-info/METADATA", METADATA)

            sdist = dist / f"plc_comm_slmp-{TEST_VERSION}.tar.gz"
            with tarfile.open(sdist, "w:gz") as archive:
                info = tarfile.TarInfo(f"plc_comm_slmp-{TEST_VERSION}/PKG-INFO")
                info.size = len(METADATA)
                archive.addfile(info, io.BytesIO(METADATA))

            validate_dist(dist, TEST_VERSION)
            (dist / "unexpected.txt").write_text("stale", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "artifact names mismatch"):
                validate_dist(dist, TEST_VERSION)


if __name__ == "__main__":
    unittest.main()
