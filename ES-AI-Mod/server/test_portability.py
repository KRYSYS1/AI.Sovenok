"""Optional installations never replace or disable development coverage."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_paths


class PortabilityTests(unittest.TestCase):
    def test_absent_overrides_do_not_fall_back_to_existing_defaults(self):
        with tempfile.TemporaryDirectory(dir=test_paths.TEMP) as directory:
            absent = os.path.join(directory, "absent")
            with patch.dict(os.environ, ESAI_WORKSHOP_ROOT=absent, ESAI_GAME_ROOT=absent):
                self.assertEqual(test_paths.optional_root("ESAI_WORKSHOP_ROOT", directory, "fallback"), absent)
                self.assertEqual(test_paths.optional_root("ESAI_GAME_ROOT", directory, "fallback"), absent)
                self.assertEqual(test_paths.existing_paths((directory, absent)), (directory,))

    def test_relocated_helper_keeps_core_and_skips_only_optionals(self):
        source = Path(test_paths.__file__).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(dir=test_paths.TEMP) as directory:
            project = Path(directory) / "relocated-project"
            (project / "mod").mkdir(parents=True)
            env = {"__file__": str(project / "server/test_paths.py")}
            with patch.dict(os.environ, ESAI_WORKSHOP_ROOT=str(project / "absent-workshop"),
                            ESAI_GAME_ROOT=str(project / "absent-game")):
                exec(compile(source, env["__file__"], "exec"), env)
            self.assertEqual(env["PROJECT_ROOT"], str(project))
            self.assertEqual(env["ROOTS"], (str(project / "mod"),))
            called = []

            class Cases(unittest.TestCase):
                def test_core(self):
                    for root in env["ROOTS"]:
                        called.append(root)
                        self.assertTrue(os.path.isdir(root))

                @unittest.skipUnless(os.path.isdir(env["WORKSHOP_ROOT"]), "No Workshop")
                def test_workshop(self):
                    self.fail("Absent installation was selected")

                @unittest.skipUnless(os.path.isfile(os.path.join(env["GAME_ROOT"], "lib/windows-i686/python.exe")), "No Python 2")
                def test_python2(self):
                    self.fail("Absent interpreter was selected")

            result = unittest.TestResult()
            unittest.defaultTestLoader.loadTestsFromTestCase(Cases).run(result)
            self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
            self.assertEqual(result.testsRun, 3)
            self.assertEqual(len(result.skipped), 2)
            self.assertEqual(called, [str(project / "mod")])

    def test_test_helpers_are_not_runtime_manifest_entries(self):
        from test_deploy_workshop import deploy
        self.assertIn("server/test_paths.py", deploy.POLICY["development_only"])
        self.assertNotIn("server/test_paths.py", deploy.PATHS)
        self.assertFalse(any(Path(name).name.startswith("test_") for name in deploy.PATHS))
