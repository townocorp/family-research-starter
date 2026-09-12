import json
from pathlib import Path
import stat
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from support import FamilyCase, ROOT
import project
from project import FOLDERS, RUNTIME_FILES, contained, initialise, load_project, no_links
from review_content import local_link_findings


class ProjectTests(FamilyCase):
    def test_exact_runtime_and_private_layout(self):
        for name in (*FOLDERS, *RUNTIME_FILES):
            self.assertTrue((self.family / name).exists(), name)
        for name in RUNTIME_FILES:
            if name.endswith(".md"):
                self.assertEqual(local_link_findings(self.family / name, self.family), [], name)
        self.assertFalse((self.family / ".git").exists())
        self.assertFalse((self.family / ".venv").exists())
        self.assertFalse((self.family / "tools/report/scripts/node_modules").exists())
        self.assertFalse((self.family / "tests").exists())
        for skill in ("family-research", "family-report"):
            relative = f".claude/skills/{skill}/SKILL.md"
            self.assertEqual((self.family / relative).read_bytes(), (ROOT / relative).read_bytes())
            self.assertEqual(local_link_findings(self.family / relative, self.family), [])
        self.assertEqual(load_project(self.family)[1]["canon"]["mode"], "markdown")

    def test_existing_canonical_store_is_not_opened_or_changed(self):
        store = self.parent / "canonical-workbook.bin"
        original = b"SYNTHETIC existing canonical-store sentinel"
        store.write_bytes(original)
        dest = initialise(self.parent / "existing", owner="P002", canon="existing",
                          canon_location=str(store), skills=False)
        self.assertEqual(store.read_bytes(), original)
        self.assertFalse((dest / "research/facts.md").exists())
        self.assertFalse((dest / ".claude").exists())
        self.assertEqual(load_project(dest)[1]["canon"]["location"], str(store))

    def test_licence_and_dependency_notices_are_preserved_in_both_canon_modes(self):
        existing = initialise(self.parent / "licensed-existing", owner="P002", canon="existing",
                              canon_location="Owner-managed application", skills=False)
        for root in (self.family, existing):
            for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
                self.assertEqual((root / name).read_bytes(), (ROOT / name).read_bytes())
                self.assertEqual(local_link_findings(root / name, root), [])
            scripts = root / "tools/report/scripts"
            manifest = json.loads((scripts / "package.json").read_text(encoding="utf-8"))
            lock = json.loads((scripts / "package-lock.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["license"], "MIT")
            self.assertEqual(lock["packages"][""]["license"], "MIT")
            self.assertFalse((root / "docs/example").exists())

    def test_existing_empty_or_populated_destination_refused(self):
        for name in ("empty", "populated"):
            path = self.parent / name
            path.mkdir()
            if name == "populated":
                (path / "sentinel").write_bytes(b"keep")
            with self.assertRaises(FileExistsError):
                initialise(path, owner="P001", canon="markdown", canon_location=None, skills=False)
            self.assertEqual(sorted(p.name for p in path.iterdir()), [] if name == "empty" else ["sentinel"])

    def test_invalid_choices_create_nothing(self):
        for options in ({"owner": ""}, {"canon": "existing"}, {"canon_location": "unexpected"}):
            kwargs = dict(owner="P001", canon="markdown", canon_location=None, skills=False)
            kwargs.update(options)
            dest = self.parent / "invalid"
            with self.assertRaises(ValueError):
                initialise(dest, **kwargs)
            self.assertFalse(dest.exists())

    def test_no_creation_inside_shareable_checkout(self):
        with self.assertRaises(ValueError):
            initialise(ROOT / "new-family", owner="P001", canon="markdown", canon_location=None, skills=False)
        self.assertFalse((ROOT / "new-family").exists())

    def test_private_project_cannot_seed_another_family(self):
        with self.assertRaisesRegex(ValueError, "another family's"):
            initialise(self.parent / "other", owner="P001", canon="markdown",
                       canon_location=None, skills=False, source=self.family)

    def test_path_escape_and_drive_relative_paths(self):
        for value in ("../outside", "C:outside", "\\\\host\\share", str(self.parent)):
            with self.assertRaises(ValueError):
                contained(self.family, value)

    def test_link_detection_checks_lexical_ancestors(self):
        target = self.family / "derived" / "link"
        actual_lstat = Path.lstat
        class LinkStat:
            st_mode = 0o120777
            st_file_attributes = 0
        fired = []
        def inspect(path, *args, **kwargs):
            if path == target:
                fired.append(path)
                return LinkStat()
            return actual_lstat(path, *args, **kwargs)
        with patch.object(Path, "lstat", inspect):
            with self.assertRaisesRegex(ValueError, "linked"):
                contained(self.family, "derived/link/../outside")
        self.assertTrue(fired)

    def test_initializer_write_failure_removes_only_its_new_files(self):
        dest = (self.parent / "failed-init").resolve()
        sibling = self.parent / "sentinel"
        sibling.write_bytes(b"keep")
        actual = project.write_new
        fired = []
        def fail(path, data):
            if Path(path).resolve() == dest / "tools" / "project.py":
                fired.append(path)
                raise OSError("synthetic write failure")
            return actual(path, data)
        with patch.object(project, "write_new", fail):
            with self.assertRaises(OSError):
                initialise(dest, owner="P001", canon="markdown", canon_location=None, skills=False)
        self.assertTrue(fired)
        self.assertFalse(dest.exists())
        self.assertEqual(sibling.read_bytes(), b"keep")

    def test_network_namespaces_are_rejected_before_any_filesystem_probe(self):
        values = (r"\\synthetic.invalid\share\file.txt", r"\\?\UNC\synthetic.invalid\share\file.txt",
                  r"\\.\UNC\synthetic.invalid\share\file.txt", r"\??\UNC\synthetic.invalid\share\file.txt",
                  "smb://synthetic.invalid/share/file.txt", "file://synthetic.invalid/share/file.txt")
        with patch.object(Path, "lstat", side_effect=AssertionError("network filesystem probe forbidden")) as probe:
            for value in values:
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "network|namespace"):
                    no_links(Path(value))
        probe.assert_not_called()

    def test_directory_link_count_is_not_treated_as_a_hardlinked_file(self):
        directory = (self.family / "derived").resolve()
        original = Path.lstat
        fired = []
        def inspect(path, *args, **kwargs):
            if path == directory:
                fired.append(path)
                return SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_nlink=99, st_file_attributes=0)
            return original(path, *args, **kwargs)
        with patch.object(Path, "lstat", inspect):
            self.assertEqual(no_links(directory), directory)
        self.assertTrue(fired)

    def test_reparse_attribute_is_refused_before_resolving(self):
        target = self.family / "derived"
        original = Path.lstat
        fired = []
        def inspect(path, *args, **kwargs):
            if path == target:
                fired.append(path)
                return SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_nlink=1, st_file_attributes=0x400)
            return original(path, *args, **kwargs)
        with patch.object(Path, "lstat", inspect):
            with self.assertRaisesRegex(ValueError, "reparse"):
                no_links(target)
        self.assertTrue(fired)


if __name__ == "__main__":
    unittest.main()
