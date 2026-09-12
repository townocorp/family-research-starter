from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from support import ROOT
from review_content import candidate_files, review


class ContentReviewTests(unittest.TestCase):
    def test_generic_tree_has_valid_links_and_skill_metadata(self):
        self.assertEqual(review(ROOT), [])

    def test_synthetic_external_marker_is_reported_without_echoing_value(self):
        marker = "SYNTHETIC_" + "PRIVATE_MARKER_ONLY"
        with tempfile.TemporaryDirectory(prefix="synthetic-candidate-") as directory:
            root = Path(directory).resolve()
            (root / "README.md").write_text(marker, encoding="utf-8")
            findings = review(root, extra_markers=(marker,))
            self.assertTrue(any("external review marker" in item for item in findings))
            self.assertTrue(all(marker not in item for item in findings))

    def test_unexpected_private_folder_is_not_traversed(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-candidate-") as directory:
            root = Path(directory).resolve()
            (root / "originals").mkdir()
            (root / "originals" / "record.bin").write_bytes(b"synthetic only")
            findings = review(root)
            self.assertIn("unexpected candidate directory: originals", findings)

    def test_unreadable_candidate_subtree_fails_closed(self):
        fired = []
        def blocked(*args, **kwargs):
            fired.append(True)
            kwargs["onerror"](PermissionError("synthetic unreadable subtree"))
            return iter(())
        with patch("review_content.os.walk", blocked):
            with self.assertRaises(PermissionError):
                candidate_files(ROOT)
        self.assertTrue(fired)


if __name__ == "__main__":
    unittest.main()
