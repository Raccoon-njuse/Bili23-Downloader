"""Validate source-tree global command and Codex Skill registration."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PROJECT_DIR = Path(__file__).resolve().parents[1]
INSTALLER = PROJECT_DIR / "scripts" / "install-global.sh"


@unittest.skipIf(os.name == "nt", "The source registration script targets POSIX shells.")
class GlobalInstallTest(unittest.TestCase):
    """Ensure global links remain attached to the source checkout and are removable."""

    def test_registers_and_uninstalls_cli_and_skill(self):
        """The global CLI must resolve its source root even when invoked through a symlink."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            bin_dir = temporary_root / "bin"
            codex_home = temporary_root / "codex"
            environment = {
                **os.environ,
                "MEDIA_AGENT_BIN_DIR": str(bin_dir),
                "CODEX_HOME": str(codex_home),
                "MEDIA_AGENT_APPDATA_DIR": str(temporary_root / "appdata"),
            }

            first_install = self._run("--all", environment)
            self.assertEqual(first_install.returncode, 0, first_install.stderr)

            cli_link = bin_dir / "media-agent"
            skill_link = codex_home / "skills" / "media-agent-cli"
            self.assertTrue(cli_link.is_symlink())
            self.assertTrue(skill_link.is_symlink())
            self.assertEqual(cli_link.resolve(), PROJECT_DIR / "media-agent")
            self.assertEqual(skill_link.resolve(), PROJECT_DIR / ".agents" / "skills" / "media-agent-cli")

            global_command_environment = {
                **environment,
                "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            }
            help_result = subprocess.run(
                ["sh", "-c", "media-agent --help"],
                cwd = PROJECT_DIR,
                env = global_command_environment,
                text = True,
                capture_output = True,
                check = False,
            )
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn("usage: media-agent", help_result.stdout)

            repeat_install = self._run("--all", environment)
            self.assertEqual(repeat_install.returncode, 0, repeat_install.stderr)

            uninstall = self._run("--uninstall", environment)
            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)
            self.assertFalse(cli_link.exists())
            self.assertFalse(skill_link.exists())

    @staticmethod
    def _run(mode: str, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
        """Run the POSIX installer with isolated global-registration directories."""
        return subprocess.run(
            ["sh", str(INSTALLER), mode],
            cwd = PROJECT_DIR,
            env = environment,
            text = True,
            capture_output = True,
            check = False,
        )
