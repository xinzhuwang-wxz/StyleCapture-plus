"""Offline contract tests for the shareable pixel-character-card Skill."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skills" / "pixel-character-card"


class PixelCharacterCardSkillContractTest(unittest.TestCase):
    def test_skill_is_chinese_product_api_facade(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: pixel-character-card", skill)
        self.assertIn("竖版 3:4", skill)
        self.assertIn("Product API", skill)
        self.assertIn("scripts/generate_pixel_card.py", skill)
        self.assertNotIn("doubao-seedream", skill.lower())
        self.assertNotIn("ARK_API_KEY", skill)

    def test_script_help_exposes_bounded_workflow(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SKILL_ROOT / "scripts" / "generate_pixel_card.py"),
                "--help",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--api-base-url", completed.stdout)
        self.assertIn("--timeout-seconds", completed.stdout)
        self.assertIn("--output", completed.stdout)

    def test_skill_does_not_bypass_product_api(self) -> None:
        script = (SKILL_ROOT / "scripts" / "generate_pixel_card.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("/v1/pixel-trials", script)
        self.assertIn("/v1/uploads/prepare", script)
        self.assertNotIn("/images/generations", script)
        self.assertNotIn("ark.cn-beijing", script)


if __name__ == "__main__":
    unittest.main()
