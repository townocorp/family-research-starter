from pathlib import Path
import json
import tempfile
import unittest

from support import ROOT
from quality_gate import NODE_CASES, collect_python, require_node_success, require_python_success, verify_node_dependencies


class QualityGateTests(unittest.TestCase):
    def test_missing_required_python_suite_fails(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-suite-") as directory:
            root = Path(directory).resolve()
            (root / "tests").mkdir()
            with self.assertRaisesRegex(ValueError, "missing"):
                collect_python(root, required=("test_required_missing.py",))

    def test_empty_required_python_suite_fails(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-suite-") as directory:
            root = Path(directory).resolve()
            (root / "tests").mkdir()
            (root / "tests/test_required_empty.py").write_text("# Synthetic empty suite\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no tests"):
                collect_python(root, required=("test_required_empty.py",))

    def test_positive_python_count_and_skip_controls(self):
        result = unittest.TestResult()
        result.testsRun = 1
        require_python_success(result, 1)
        with self.assertRaises(ValueError):
            require_python_success(result, 0)
        result.skipped.append(("synthetic test", "synthetic skip"))
        with self.assertRaisesRegex(ValueError, "without skips"):
            require_python_success(result, 1)

    def test_node_requires_real_declared_cases_and_positive_counts(self):
        names = "\n".join("# Subtest: " + name for name in NODE_CASES)
        good = names + "\n# tests 5\n# pass 5\n# fail 0\n# cancelled 0\n# skipped 0\n# todo 0\n"
        self.assertEqual(require_node_success(good), 5)
        for bad in (good.replace("# tests 5", "# tests 0").replace("# pass 5", "# pass 0"),
                    good.replace("# skipped 0", "# skipped 5"),
                    "# Subtest: empty-file.cjs\n# tests 1\n# pass 1\n# fail 0\n# cancelled 0\n# skipped 0\n# todo 0\n"):
            with self.assertRaises(ValueError):
                require_node_success(bad)

    def test_declared_locked_and_installed_node_versions_must_agree(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-dependencies-") as directory:
            scripts = Path(directory).resolve()
            manifest = {"name": "synthetic-report", "version": "0.1.0",
                        "dependencies": {"synthetic-package": "1.0.0"}}
            lock = {"name": manifest["name"], "version": manifest["version"], "lockfileVersion": 3,
                    "packages": {"": dict(manifest), "node_modules/synthetic-package": {"version": "1.0.0"}}}
            package = scripts / "node_modules/synthetic-package/package.json"
            package.parent.mkdir(parents=True)
            (scripts / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
            (scripts / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
            package.write_text('{"version":"1.0.0"}', encoding="utf-8")
            verify_node_dependencies(scripts)
            package.write_text('{"version":"0.9.0"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "installed dependency version"):
                verify_node_dependencies(scripts)
            package.write_text('{"version":"1.0.0"}', encoding="utf-8")
            manifest["dependencies"]["synthetic-package"] = "1.1.0"
            (scripts / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "declarations differ"):
                verify_node_dependencies(scripts)
            manifest["dependencies"]["synthetic-package"] = "1.0.0"
            (scripts / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
            lock["packages"]["node_modules/synthetic-package"]["version"] = "1.0.1"
            (scripts / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "locked direct dependency"):
                verify_node_dependencies(scripts)


if __name__ == "__main__":
    unittest.main()
