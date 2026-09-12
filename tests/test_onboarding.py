import hashlib
import json
from pathlib import Path
import unittest

from support import FamilyCase, image_bytes, metadata, report_markdown


class OnboardingTests(FamilyCase):
    def test_entire_fresh_project_workflow_using_installed_commands(self):
        family = self.family
        original_text = b"Person P001 remembers Person P002.\r\nThis is a synthetic eulogy fixture.\n"
        eulogy = family / "originals/eulogies/E001.txt"
        eulogy.write_bytes(original_text)
        transcript = family / "derived/transcripts/E001.txt"
        transcript.write_bytes(original_text)
        export = family / "originals/gedcom/E003.ged"
        export.write_bytes(b"0 HEAD\n1 SOUR SYNTHETIC\n1 GEDC\n2 VERS 7.0\n0 @P001@ INDI\n1 NAME Person P001\n0 TRLR\n")
        image = family / "originals/photos/E002.png"
        image.write_bytes(image_bytes())
        source_hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (eulogy, export, image, transcript)}
        for identity, source, changes in (
            ("E001", eulogy, {"basis": "first-hand", "transcript": {
                "file": "derived/transcripts/E001.txt", "method": "human transcription",
                "author": "P001", "source_locator": "synthetic eulogy, line 1",
                "start": 0, "end": 11, "quote": "Person P001"}}),
            ("E002", image, {"source_type": "local"}),
            ("E003", export, {"source_type": "gedcom", "custody": "Synthetic export, version 7.0; fixture-owned; no external tree",
                              "consent": "Synthetic export permission for tests; not real family consent"}),
        ):
            meta = family / "evidence" / (identity + ".json")
            meta.write_text(json.dumps(metadata(identity, **changes)), encoding="utf-8")
            self.cli("capture", "--project", ".", "--file", source, "--metadata", meta)
        (family / "research/rounds/round-001.md").write_text(
            "# Synthetic round 001\n\nQuestion: what does the attributed memory say?\n"
            "Completed: local synthetic index query P001, whole fixture, no matches; entered in negative ledger.\n"
            "Blocked: unrelated synthetic archive unavailable; not a negative finding.\n"
            "Correction C001 proposes narrowing a relationship claim to an attributed memory, E001; owner review pending.\n"
            "Lead L001: seek independent evidence; no access or purchase authorised.\n"
            "Stop: agreed fixture scope complete. Canonical change remains a proposal.\n", encoding="utf-8")
        with (family / "research/negative-searches.md").open("a", encoding="utf-8") as ledger:
            ledger.write("\nSynthetic round 001: completed local fixture index query P001; no match in entire fixture only.\n")
        with (family / "research/corrections.md").open("a", encoding="utf-8") as ledger:
            ledger.write("\nC001: previous proposed relationship -> attributed memory only; E001; owner decision pending.\n")
        with (family / "research/leads.md").open("a", encoding="utf-8") as ledger:
            ledger.write("\nL001: seek an independent source for E001; proposed, not authorised.\n")
        canon_before = (family / "research/facts.md").read_bytes()
        self.cli("catalogue", "--project", ".")
        self.cli("check", "--project", ".")
        draft = family / "reports/drafts/round-001.md"
        draft.write_text(report_markdown(), encoding="utf-8")
        response = self.cli("report", "--project", ".", "--draft", "reports/drafts/round-001.md",
                            "--output", "reports/releases/round-001", "--print")
        delivered = json.loads(response.stdout)
        self.assertTrue(delivered["delivered"])
        self.assertEqual(delivered["check"]["reference_count"], 2)
        self.assertEqual(delivered["check"]["errors"], [])
        html = Path(delivered["html"]).read_text(encoding="utf-8")
        for value in ("Person P001", "Person P002", "attributed memory", "E001", "E002", "Synthetic caption"):
            self.assertIn(value, html)
        self.assertEqual((family / "research/facts.md").read_bytes(), canon_before)
        self.assertEqual(source_hashes, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_hashes})
        self.assertIn("Captures: 3", (family / "evidence/catalogue.md").read_text(encoding="utf-8"))
        self.assertNotIn("unavailable", (family / "research/negative-searches.md").read_text(encoding="utf-8"))
        before = {p: p.read_bytes() for p in (family / "reports/releases").iterdir()}
        self.cli("report", "--project", ".", "--draft", "reports/drafts/round-001.md",
                 "--output", "reports/releases/round-001", ok=False)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertFalse((family / ".git").exists())
        self.assertFalse((family / "tools/report/scripts/node_modules").exists())


if __name__ == "__main__":
    unittest.main()
