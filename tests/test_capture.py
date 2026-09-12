import hashlib
import io
import json
import os
from pathlib import Path
from unittest.mock import patch
import unittest

from support import FamilyCase, image_bytes, metadata
from capture import capture
from _lib_capture.media import inspect_image, inspect_original
from _lib_capture.rebuild_catalogue import rebuild, records
from _lib_capture.sidecar import validate_metadata
from _lib_capture.slug import slugify_segment


class CaptureTests(FamilyCase):
    def test_original_bytes_and_idempotence(self):
        content = b"Person P001 remembers Person P002.\r\n"
        source, meta = self.add_capture(content=content)
        before = {p.name: p.read_bytes() for p in (self.family / "evidence/captures/E001").iterdir()}
        self.assertTrue(capture(self.family, source, meta)["unchanged"])
        self.assertEqual(source.read_bytes(), content)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.family / "evidence/captures/E001").iterdir()})
        self.assertEqual(records(self.family)["E001"]["sha256"], hashlib.sha256(content).hexdigest())

    def test_differing_source_or_metadata_never_overwrites_capture(self):
        source, meta = self.add_capture()
        captured = self.family / "evidence/captures/E001/source.txt"
        old = captured.read_bytes()
        source.write_bytes(b"changed synthetic source")
        with self.assertRaises(FileExistsError):
            capture(self.family, source, meta)
        self.assertEqual(captured.read_bytes(), old)
        source.write_bytes(old)
        value = json.loads(meta.read_text())
        value["rationale"] = "Changed synthetic assessment"
        meta.write_text(json.dumps(value))
        with self.assertRaises(FileExistsError):
            capture(self.family, source, meta)

    def test_metadata_quotes_controls_and_unicode_round_trip(self):
        value = 'Synthetic "quote": line one\nline two\t\u00e9'
        self.add_capture(summary=value)
        self.assertEqual(records(self.family)["E001"]["summary"], value)

    def test_unknown_false_negative_and_model_confidence_rejected(self):
        for changes in ({"confidence": "Negative"}, {"confidence": 0.99}, {"round": True},
                        {"basis": "model agreement"}, {"people": ["P001", "P001"]},
                        {"captured": "2000-02-30"}, {"source_date": "yesterday"},
                        {"url": "https://name:password@example.invalid/"},
                        {"confidence": "Supported", "supporting_evidence": []}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_metadata(metadata(**changes))

    def test_confidence_is_claim_scoped_and_requires_rationale(self):
        with self.assertRaises(ValueError):
            validate_metadata(metadata(rationale=""))
        validate_metadata(metadata(confidence="Supported", supporting_evidence=["E001"]))
        with self.assertRaises(ValueError):
            validate_metadata(metadata(supporting_evidence=["E001"], opposing_evidence=["E001"]))

    def test_exact_transcript_span_preserves_crlf_and_bom(self):
        raw = b"\xef\xbb\xbfPerson P001\r\nPerson P002\n"
        transcript = self.family / "derived/transcripts/E001.txt"
        transcript.write_bytes(raw)
        text = raw.decode("utf-8")
        value = {"file": "derived/transcripts/E001.txt", "method": "human transcription",
                 "author": "P001", "source_locator": "synthetic recording 00:01-00:02",
                 "start": 1, "end": 12, "quote": text[1:12]}
        self.add_capture(transcript=value)
        self.assertEqual((self.family / "evidence/captures/E001/transcript.txt").read_bytes(), raw)
        self.assertEqual(records(self.family)["E001"]["quote"], "Person P001")

    def test_invalid_transcript_span_creates_no_capture(self):
        (self.family / "derived/transcripts/E001.txt").write_bytes(b"Person P001\r\n")
        for start, end, quote in ((0, 999, "Person P001"), (0, 11, "Wrong"), (False, 11, "Person P001")):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                self.add_capture(transcript={"file": "derived/transcripts/E001.txt",
                    "method": "human", "author": "P001", "source_locator": "line 1",
                    "start": start, "end": end, "quote": quote})
            self.assertFalse((self.family / "evidence/captures/E001").exists())

    def test_corrupt_truncated_and_mismatched_media_fail(self):
        for data, suffix in ((b"", ".txt"), (b"<html>not an image</html>", ".jpg"),
                             (image_bytes()[:80], ".png"), (image_bytes(), ".jpg"),
                             (b"%PDF-1.7\nbroken", ".pdf")):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                inspect_original(data, suffix)

    def test_pdf_is_preserved_without_claiming_visual_or_ocr_check(self):
        from pypdf import PdfWriter
        stream = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(stream)
        source, _ = self.add_capture(content=stream.getvalue(), suffix=".pdf")
        self.assertEqual(source.read_bytes(), stream.getvalue())
        self.assertIn("not visual/OCR", records(self.family)["E001"]["media_check"])

    def test_missing_or_changed_original_leaves_last_catalogue(self):
        self.add_capture()
        rebuild(self.family)
        catalogue = self.family / "evidence/catalogue.md"
        before = catalogue.read_bytes()
        (self.family / "evidence/captures/E001/source.txt").write_bytes(b"modified")
        with self.assertRaises(ValueError):
            rebuild(self.family)
        self.assertEqual(catalogue.read_bytes(), before)

    def test_malformed_duplicate_sidecar_and_extra_files_fail(self):
        self.add_capture()
        sidecar = self.family / "evidence/captures/E001/record.md"
        content = sidecar.read_text(encoding="utf-8")
        sidecar.write_text(content.replace('schema: 1', 'schema: 1\nschema: 1'), encoding="utf-8")
        with self.assertRaises(ValueError):
            records(self.family)
        sidecar.write_text(content, encoding="utf-8")
        (sidecar.parent / "unmanaged.txt").write_bytes(b"extra")
        with self.assertRaises(ValueError):
            records(self.family)

    def test_catalogue_does_not_replace_curated_prose(self):
        self.add_capture()
        catalogue = self.family / "evidence/catalogue.md"
        catalogue.write_bytes(b"Human curated research")
        with self.assertRaises(ValueError):
            rebuild(self.family)
        self.assertEqual(catalogue.read_bytes(), b"Human curated research")

    def test_unsupported_or_missing_stored_provenance_is_rejected(self):
        self.add_capture()
        sidecar = self.family / "evidence/captures/E001/record.md"
        content = sidecar.read_text(encoding="utf-8")
        variants = (
            content.replace("schema: 1", "schema: true"),
            content.replace("schema: 1", 'schema: 1\nunexpected: "synthetic"'),
            content.replace('original_name: "E001.txt"', 'original_name: ""'),
            content.replace('transcript_method: ""', 'transcript_method: "no matching transcript"'),
        )
        for variant in variants:
            self.assertNotEqual(content, variant)
            sidecar.write_text(variant, encoding="utf-8")
            with self.assertRaises(ValueError):
                records(self.family)
        sidecar.write_text(content, encoding="utf-8")

    def test_duplicate_json_input_is_an_error(self):
        source = self.family / "originals/stories/E001.txt"
        source.write_bytes(b"Synthetic input")
        meta = self.family / "evidence/bad.json"
        meta.write_text('{"evidence_id":"E001","evidence_id":"E002"}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            capture(self.family, source, meta)

    def test_no_silent_missing_media_dependency(self):
        import builtins
        actual = builtins.__import__
        fired = []
        def missing(name, *args, **kwargs):
            if name == "PIL":
                fired.append(name)
                raise ImportError("synthetic missing Pillow")
            return actual(name, *args, **kwargs)
        data = image_bytes()
        with patch("builtins.__import__", missing):
            with self.assertRaises(ImportError):
                inspect_original(data, ".png")
        self.assertTrue(fired)

    def test_slug_rejects_empty_and_reserved_device_names(self):
        for value in ("", "!!!", "CON", "LPT1"):
            with self.assertRaises(ValueError):
                slugify_segment(value)

    def test_mislabeled_eps_never_reaches_external_decoder(self):
        from PIL import EpsImagePlugin
        eps = b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\n%%EndComments\nshowpage\n"
        with patch.object(EpsImagePlugin, "Ghostscript",
                          side_effect=AssertionError("external decoder must not run")) as decoder:
            with self.assertRaises(ValueError):
                inspect_original(eps, ".png")
            with self.assertRaises(ValueError):
                inspect_image(eps)
            self.assertIn("fully decoded PNG", inspect_original(image_bytes(), ".png"))
        decoder.assert_not_called()

    def test_hardlinked_capture_file_is_refused_without_mutating_it(self):
        self.add_capture()
        original = self.family / "evidence/captures/E001/source.txt"
        previous = original.read_bytes()
        os.link(original, self.parent / "synthetic-alias.txt")
        with self.assertRaisesRegex(ValueError, "multiply-linked"):
            records(self.family)
        self.assertEqual(original.read_bytes(), previous)

    def test_unicode_line_separators_round_trip_through_capture_and_catalogue(self):
        for number, separator in enumerate(("\u0085", "\u2028", "\u2029"), 1):
            identity = f"E{number:03d}"
            summary = "Synthetic first" + separator + "synthetic second"
            self.add_capture(identity, summary=summary)
            self.assertEqual(records(self.family)[identity]["summary"], summary)
        self.assertEqual(rebuild(self.family), 3)

    def test_unserializable_generated_sidecar_is_rejected_before_capture_creation(self):
        with patch("_lib_capture.sidecar.render_frontmatter", return_value="---\nschema: 1\n---\n") as fault:
            with self.assertRaises(ValueError):
                self.add_capture()
        self.assertTrue(fault.called)
        self.assertFalse((self.family / "evidence/captures/E001").exists())

    def test_unsupported_unicode_extension_creates_no_capture(self):
        with self.assertRaisesRegex(ValueError, "ASCII"):
            self.add_capture(suffix=".\u00e9")
        self.assertFalse((self.family / "evidence/captures/E001").exists())


if __name__ == "__main__":
    unittest.main()
