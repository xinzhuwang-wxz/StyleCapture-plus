from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SCRIPT = REPOSITORY_ROOT / "scripts" / "local.sh"


class LocalDeployScriptTest(unittest.TestCase):
    def test_init_creates_private_idempotent_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            test_root = Path(temporary_directory)
            (test_root / ".env.example").write_text(
                (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            env_file = test_root / ".env.local"
            environment = {
                **os.environ,
                "STYLECAPTURE_REPOSITORY_ROOT": str(test_root),
                "STYLECAPTURE_ENV_FILE": str(env_file),
            }

            first = subprocess.run(
                [str(LOCAL_SCRIPT), "init"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            original = env_file.read_text(encoding="utf-8")
            second = subprocess.run(
                [str(LOCAL_SCRIPT), "init"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertIn("Created local configuration", first.stdout)
            self.assertIn("Using existing local configuration", second.stdout)
            self.assertEqual(original, env_file.read_text(encoding="utf-8"))
            self.assertNotIn("replace-with-an-internal-gateway-secret", original)
            self.assertNotIn("replace-with-at-least-24-random-characters", original)
            self.assertNotIn("replace-with-a-distinct-session-signing-secret", original)
            self.assertEqual(stat.S_IMODE(env_file.stat().st_mode), 0o600)

    def test_help_documents_non_destructive_commands(self) -> None:
        result = subprocess.run(
            [str(LOCAL_SCRIPT), "help"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("up|init|doctor|status|logs|restart|down", result.stdout)
        self.assertIn("preserving database and upload volumes", result.stdout)
        self.assertIn("STYLECAPTURE_COMPOSE_PROJECT_NAME", result.stdout)

    def test_local_project_is_isolated_from_production_by_default(self) -> None:
        source = LOCAL_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            '${STYLECAPTURE_COMPOSE_PROJECT_NAME:-stylecapture-local}', source
        )

    def test_startup_retries_transient_docker_build_failures(self) -> None:
        source = LOCAL_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("for attempt in 1 2 3", source)
        self.assertIn("retrying with the existing build cache", source)
        self.assertIn("if compose build; then", source)
        self.assertIn("compose up -d", source)
        self.assertNotIn("compose up --build", source)

    def test_restart_reconciles_environment_without_deleting_data(self) -> None:
        source = LOCAL_SCRIPT.read_text(encoding="utf-8")

        restart_block = source.split('  restart)\n', maxsplit=1)[1].split(
            '    ;;\n  down)', maxsplit=1
        )[0]
        self.assertIn("compose up -d", restart_block)
        self.assertNotIn("\n    compose restart\n", restart_block)
        self.assertNotIn("down", restart_block)


if __name__ == "__main__":
    unittest.main()
