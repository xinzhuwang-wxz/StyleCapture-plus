"""Offline contract tests for the shareable Doubao virtual try-on skill."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "doubao-virtual-try-on"


class DoubaoSkillContractTest(unittest.TestCase):
    def test_cli_entry_points_are_available(self) -> None:
        for script in ("virtual_try_on.py", "batch_virtual_try_on.py"):
            path = SKILL_DIR / "scripts" / script
            help_run = subprocess.run(
                [sys.executable, "-B", str(path), "--help"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(help_run.returncode, 0, help_run.stderr)
            self.assertIn("--output-dir", help_run.stdout)

            version_run = subprocess.run(
                [sys.executable, "-B", str(path), "--version"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(version_run.returncode, 0, version_run.stderr)
            self.assertIn("1.2.0", version_run.stdout)

    def test_packager_emits_expected_archive_without_cache_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "skill.zip"
            run = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "package_doubao_skill.py"),
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue(output.is_file())
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
            self.assertIn("doubao-virtual-try-on/SKILL.md", names)
            self.assertIn(
                "doubao-virtual-try-on/scripts/virtual_try_on.py", names
            )
            self.assertFalse(any("__pycache__" in name for name in names))
            self.assertFalse(any(name.endswith(".pyc") for name in names))


if __name__ == "__main__":
    unittest.main()
