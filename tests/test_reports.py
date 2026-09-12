import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import unittest
import zipfile

from support import FamilyCase, report_markdown
import release_report as release
from check_report import CheckError, HtmlReport, check_report, load_manifest
from markdown_to_data import convert


class ReportTests(FamilyCase):
    def setUp(self):
        super().setUp()
        self.here = self.family / "tools/report/scripts"
        override = patch.object(release, "HERE", self.here)
        override.start()
        self.addCleanup(override.stop)

    def rendered(self, *, image=True):
        draft = self.make_report(image=image)
        data = self.family / "reports/drafts/data.json"
        data.write_text(json.dumps(convert(draft, self.family)), encoding="utf-8")
        outputs = [self.family / "reports/releases/direct.docx", self.family / "reports/releases/direct.html"]
        for name, output in zip(("create_docx.js", "create_html.js"), outputs):
            result = subprocess.run(["node", str(self.here / name), str(data), str(output),
                                     "--project", str(self.family)], env=self.env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        return data, outputs

    def test_new_checked_pair_with_sparse_repeated_citations_and_print_dpi(self):
        draft = self.make_report()
        snapshot = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (self.family / "originals").rglob("*") if p.is_file()}
        result = release.release_report(self.family, draft, "reports/releases/round-001",
                                        print_mode=True, min_dpi=300)
        self.assertTrue(result["delivered"])
        self.assertEqual(result["check"]["errors"], [])
        self.assertEqual(result["check"]["reference_count"], 2)
        self.assertEqual(result["check"]["figures"][0]["dpi"], [300.0, 300.0])
        for key in ("docx", "html"):
            self.assertGreater(Path(result[key]).stat().st_size, 100)
        html = Path(result["html"]).read_text(encoding="utf-8")
        self.assertIn("data:image/png;base64,", html)
        self.assertIn('id="body-ref-1-2"', html)
        self.assertNotIn(self.family.as_posix(), html)
        self.assertEqual(snapshot, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot})
        self.assertFalse(list((self.family / "reports/releases").glob(".report-*")))

    def test_repeat_output_refused_and_explicit_overwrite_checked(self):
        draft = self.make_report(image=False)
        output = "reports/releases/repeat"
        first = release.release_report(self.family, draft, output)
        previous = {key: Path(first[key]).read_bytes() for key in ("docx", "html")}
        with self.assertRaises(FileExistsError):
            release.release_report(self.family, draft, output)
        self.assertEqual(previous, {key: Path(first[key]).read_bytes() for key in previous})
        self.assertTrue(release.release_report(self.family, draft, output, overwrite=True)["delivered"])

    def test_print_threshold_above_exact_boundary_fails_without_outputs(self):
        draft = self.make_report()
        with self.assertRaisesRegex(CheckError, "DPI"):
            release.release_report(self.family, draft, "reports/releases/too-high", print_mode=True, min_dpi=300.01)
        self.assertFalse((self.family / "reports/releases/too-high.docx").exists())

    def test_low_resolution_digital_warning_but_print_failure(self):
        draft = self.make_report(pixels=(1649, 1100))
        result = release.release_report(self.family, draft, "reports/releases/digital")
        self.assertTrue(result["check"]["warnings"])
        with self.assertRaisesRegex(CheckError, "DPI"):
            release.release_report(self.family, draft, "reports/releases/print", print_mode=True)

    def test_nonfinite_nonpositive_dpi_rejected(self):
        draft = self.make_report(image=False)
        for dpi in (0, -1, float("inf"), float("nan")):
            with self.subTest(dpi=dpi), self.assertRaises(CheckError):
                release.release_report(self.family, draft, "reports/releases/invalid", min_dpi=dpi)

    def test_json_only_every_renderer_and_contract(self):
        probe = self.family / "reports/drafts/input.js"
        sentinel = self.family / "executed.txt"
        probe.write_text("require('node:fs').writeFileSync(" + json.dumps(str(sentinel)) + ", 'bad');", encoding="utf-8")
        for name in ("create_docx.js", "create_html.js", "report_contract.js"):
            args = ["node", str(self.here / name), str(probe)]
            if name != "report_contract.js":
                args.append(str(self.family / "reports/releases/output"))
            result = subprocess.run(args + ["--project", str(self.family)], env=self.env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("JSON", result.stderr.upper())
        self.assertFalse(sentinel.exists())

    def test_unfilled_template_cannot_be_released(self):
        self.add_capture()
        with self.assertRaisesRegex(CheckError, "placeholder"):
            release.release_report(self.family, self.family / "reports/drafts/report-template.md",
                                    "reports/releases/unfilled")

    def test_undefined_uncited_and_unsupported_sections_rejected(self):
        draft = self.make_report(image=False)
        original = draft.read_text(encoding="utf-8")
        for replacement in (original.replace("[^1]", "[^2]", 1),
                            original + "\n[^3]: E001 | line 1 | Unused synthetic reference.\n",
                            original + "\n| unsupported | table |\n"):
            draft.write_text(replacement, encoding="utf-8")
            with self.assertRaises(ValueError):
                release.release_report(self.family, draft, "reports/releases/invalid")
        self.assertFalse((self.family / "reports/releases/invalid.docx").exists())

    def test_wrong_figure_reference_and_output_path_fail(self):
        draft = self.make_report()
        draft.write_text(draft.read_text(encoding="utf-8").replace("caption [^7]", "caption [^1]"), encoding="utf-8")
        with self.assertRaisesRegex(CheckError, "own evidence"):
            release.release_report(self.family, draft, "reports/releases/wrong-figure")
        with self.assertRaisesRegex(CheckError, "reports/releases"):
            release.release_report(self.family, draft, "originals/unsafe")

    def test_missing_or_corrupt_media_is_not_a_successful_draft(self):
        draft = self.make_report()
        (self.family / "evidence/captures/E002/source.png").write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            release.release_report(self.family, draft, "reports/releases/corrupt")
        self.assertFalse((self.family / "reports/releases/corrupt.docx").exists())

    def test_missing_node_is_an_incomplete_release_not_skip(self):
        draft = self.make_report(image=False)
        with patch.object(release.subprocess, "run", side_effect=FileNotFoundError("synthetic missing Node")) as fault:
            with self.assertRaises(FileNotFoundError):
                release.release_report(self.family, draft, "reports/releases/missing")
        self.assertTrue(fault.called)
        self.assertFalse((self.family / "reports/releases/missing.docx").exists())

    def test_changed_source_during_stage_blocks_delivery(self):
        draft = self.make_report(image=False)
        source = (self.family / "evidence/captures/E001/source.txt").resolve()
        actual = release.check_report
        fired = []
        def change(*args, **kwargs):
            result = actual(*args, **kwargs)
            source.write_bytes(b"synthetic concurrent source change")
            fired.append(source)
            return result
        with patch.object(release, "check_report", change):
            with self.assertRaisesRegex(CheckError, "changed during staging"):
                release.release_report(self.family, draft, "reports/releases/stale")
        self.assertTrue(fired)
        self.assertFalse((self.family / "reports/releases/stale.docx").exists())

    def test_changed_intermediate_json_during_stage_blocks_delivery(self):
        draft = self.make_report(image=False)
        actual = release.check_report
        fired = []
        def change(data_path, *args, **kwargs):
            result = actual(data_path, *args, **kwargs)
            path = Path(data_path).resolve()
            path.write_bytes(path.read_bytes() + b"\n")
            fired.append(path)
            return result
        with patch.object(release, "check_report", change):
            with self.assertRaisesRegex(CheckError, "changed during staging"):
                release.release_report(self.family, draft, "reports/releases/stale-data")
        self.assertTrue(fired)

    def test_existing_output_change_after_snapshot_is_preserved(self):
        draft = self.make_report(image=False)
        base = self.family / "reports/releases/concurrent"
        target = Path(str(base) + ".docx").resolve()
        target.write_bytes(b"old synthetic output")
        actual = release.check_report
        fired = []
        def change(*args, **kwargs):
            result = actual(*args, **kwargs)
            target.write_bytes(b"new external synthetic output")
            fired.append(target)
            return result
        with patch.object(release, "check_report", change):
            with self.assertRaisesRegex(CheckError, "output changed"):
                release.release_report(self.family, draft, "reports/releases/concurrent", overwrite=True)
        self.assertTrue(fired)
        self.assertEqual(target.read_bytes(), b"new external synthetic output")

    def test_pair_failure_restores_previous_outputs(self):
        draft = self.make_report(image=False)
        targets = [self.family / "reports/releases/rollback.docx", self.family / "reports/releases/rollback.html"]
        for target in targets:
            target.write_bytes(b"old synthetic output " + target.suffix.encode())
        previous = {p: p.read_bytes() for p in targets}
        actual = release.os.replace
        fired = []
        def fail(source, destination):
            if Path(destination).resolve() == targets[1].resolve() and Path(source).name == "delivery-1.bin":
                fired.append(destination)
                raise OSError("synthetic second-file delivery failure")
            return actual(source, destination)
        with patch.object(release.os, "replace", fail):
            with self.assertRaisesRegex(CheckError, "prior outputs restored"):
                release.release_report(self.family, draft, "reports/releases/rollback", overwrite=True)
        self.assertTrue(fired)
        self.assertEqual(previous, {p: p.read_bytes() for p in targets})

    def test_incomplete_rollback_retains_recovery_files(self):
        draft = self.make_report(image=False)
        targets = [self.family / "reports/releases/recovery.docx", self.family / "reports/releases/recovery.html"]
        for target in targets:
            target.write_bytes(b"old synthetic output")
        actual = release.os.replace
        fired = []
        def fail(source, destination):
            if Path(destination).resolve() == targets[1].resolve() or Path(source).name == "previous-0.backup":
                fired.append((source, destination))
                raise OSError("synthetic rollback failure")
            return actual(source, destination)
        with patch.object(release.os, "replace", fail):
            with self.assertRaises(release.RecoveryRequired):
                release.release_report(self.family, draft, "reports/releases/recovery", overwrite=True)
        self.assertGreaterEqual(len(fired), 2)
        retained = list((self.family / "reports/releases").glob(".report-stage-*/previous-0.backup"))
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0].read_bytes(), b"old synthetic output")

    def test_output_hardlink_to_original_is_rejected(self):
        draft = self.make_report(image=False)
        original = self.family / "evidence/captures/E001/source.txt"
        target = self.family / "reports/releases/alias.docx"
        os.link(original, target)
        before = original.read_bytes()
        with self.assertRaisesRegex(ValueError, "linked"):
            release.release_report(self.family, draft, "reports/releases/alias", overwrite=True)
        self.assertEqual(original.read_bytes(), before)

    def test_tampered_html_caption_number_and_network_image_are_detected(self):
        data, outputs = self.rendered()
        original = outputs[1].read_text(encoding="utf-8")
        for changed in (
            original.replace('class="caption">Synthetic caption', 'class="caption">Wrong caption'),
            original.replace('value="7"', 'value="8"'),
            original.replace("data:image/png;base64,", "https://example.invalid/image/"),
        ):
            outputs[1].write_text(changed, encoding="utf-8")
            self.assertTrue(check_report(data, *outputs, self.family)["errors"])

    def test_tampered_docx_caption_association_is_detected(self):
        data, outputs = self.rendered()
        with zipfile.ZipFile(outputs[0]) as source:
            entries = {name: source.read(name) for name in source.namelist()}
        self.assertIn(b"Synthetic caption", entries["word/document.xml"])
        entries["word/document.xml"] = entries["word/document.xml"].replace(b"Synthetic caption", b"Wrong caption")
        with zipfile.ZipFile(outputs[0], "w") as target:
            for name, value in entries.items():
                target.writestr(name, value)
        findings = check_report(data, *outputs, self.family)["errors"]
        self.assertTrue(any("caption association" in item for item in findings), findings)

    def test_duplicate_json_is_rejected_by_checker(self):
        draft = self.make_report(image=False)
        path = self.family / "reports/drafts/data.json"
        value = json.dumps(convert(draft, self.family)).replace('"schema": 1', '"schema": 1, "schema": 1')
        path.write_text(value)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_manifest(path, self.family)

    def test_json_mutation_before_renderer_preserves_prior_pair(self):
        draft = self.make_report(image=False)
        targets = [self.family / "reports/releases/frozen.docx", self.family / "reports/releases/frozen.html"]
        for target in targets:
            target.write_bytes(b"previous synthetic output")
        previous = {path: path.read_bytes() for path in targets}
        original_markdown = draft.read_bytes()
        actual = release.subprocess.run
        fired = []
        def change(command, *args, **kwargs):
            if str(command[1]).endswith("create_docx.js"):
                data_path = Path(command[2]).resolve()
                data = json.loads(data_path.read_text())
                data["chapters"][0]["sections"][0]["text"] = "Altered synthetic narrative.[^1]"
                data_path.write_text(json.dumps(data), encoding="utf-8")
                fired.append(data_path)
            return actual(command, *args, **kwargs)
        with patch.object(release.subprocess, "run", change):
            with self.assertRaisesRegex(CheckError, "JSON changed"):
                release.release_report(self.family, draft, "reports/releases/frozen", overwrite=True)
        self.assertTrue(fired)
        self.assertEqual(draft.read_bytes(), original_markdown)
        self.assertEqual(previous, {path: path.read_bytes() for path in targets})

    def test_html_mutation_after_audit_is_never_delivered(self):
        draft = self.make_report(image=False)
        targets = [self.family / "reports/releases/audited.docx", self.family / "reports/releases/audited.html"]
        for target in targets:
            target.write_bytes(b"previous synthetic output")
        previous = {path: path.read_bytes() for path in targets}
        actual = release.check_report
        fired = []
        def change(data, docx, html, *args, **kwargs):
            result = actual(data, docx, html, *args, **kwargs)
            self.assertEqual(result["errors"], [])
            Path(html).write_bytes(b"synthetic junk substituted after audit")
            fired.append(Path(html).resolve())
            return result
        with patch.object(release, "check_report", change):
            with self.assertRaisesRegex(CheckError, "audited output changed"):
                release.release_report(self.family, draft, "reports/releases/audited", overwrite=True)
        self.assertTrue(fired)
        self.assertEqual(previous, {path: path.read_bytes() for path in targets})

    def test_extra_narrative_and_hidden_text_fail_complete_content_check(self):
        data, outputs = self.rendered(image=False)
        original = outputs[1].read_text(encoding="utf-8")
        self.assertEqual(check_report(data, *outputs, self.family)["errors"], [])
        variants = (
            original.replace("</body>", "<p>Unsupported synthetic narrative.</p></body>"),
            original.replace("<p>Person P001", '<p style="display:none">Person P001'),
            original.replace("</body>", "Unsupported text outside a block.</body>"),
            original.replace("body {", "body { visibility: hidden;"),
            original.replace("<main>", "<main><template>").replace("</main>", "</template></main>"),
            original.replace("<main>", "<main><dialog>").replace("</main>", "</dialog></main>"),
            original.replace("<p>Person P001", "<p><title>Person P001").replace("proof.", "proof.</title>"),
        )
        for changed in variants:
            self.assertNotEqual(changed, original)
            outputs[1].write_text(changed, encoding="utf-8")
            self.assertTrue(check_report(data, *outputs, self.family)["errors"])
        outputs[1].write_text(original, encoding="utf-8")
        self.assertEqual(check_report(data, *outputs, self.family)["errors"], [])

    def test_controlled_styles_accept_lf_and_crlf_serialization_only(self):
        data, outputs = self.rendered(image=False)
        original = outputs[1].read_text(encoding="utf-8")
        for content in (original, original.replace("\n", "\r\n")):
            outputs[1].write_bytes(content.encode("utf-8"))
            self.assertEqual(check_report(data, *outputs, self.family)["errors"], [])

    def test_dollars_and_literal_template_slots_survive_exactly(self):
        draft = self.make_report(image=False)
        literal = 'The symbol is "$"; preserve $$, $&, $`, $\' and {{TITLE}} / {{BODY}} literally.[^1]'
        title = "Synthetic literal {{BODY}} and {{TITLE}}: $$ $&"
        text = draft.read_text(encoding="utf-8")
        text = text.replace('title: "Synthetic research report"', "title: " + json.dumps(title))
        text = text.replace("Person P001 recalls Person P002. This is an attributed memory, not proof.[^1][^1]", literal)
        draft.write_text(text, encoding="utf-8")
        result = release.release_report(self.family, draft, "reports/releases/literals")
        parser = HtmlReport()
        parser.feed(Path(result["html"]).read_text(encoding="utf-8"))
        blocks = ["".join(block) for block in parser.blocks]
        self.assertIn(title, blocks)
        self.assertIn(literal.replace("[^1]", "1"), blocks)
        self.assertEqual(result["check"]["errors"], [])

    def test_tall_scan_fits_height_and_width_with_caption_reserve(self):
        draft = self.make_report(pixels=(2400, 7200))
        result = release.release_report(self.family, draft, "reports/releases/tall", print_mode=True)
        self.assertEqual(result["check"]["errors"], [])
        parser = HtmlReport()
        parser.feed(Path(result["html"]).read_text(encoding="utf-8"))
        attrs = parser.figures[0]["images"][0]
        self.assertEqual((int(attrs["width"]), int(attrs["height"])), (240, 720))
        self.assertEqual(result["check"]["figures"][0]["dpi"], [960.0, 960.0])

    def test_page_fit_is_checked_independently_of_good_dpi(self):
        data, outputs = self.rendered()
        with zipfile.ZipFile(outputs[0]) as source:
            entries = {name: source.read(name) for name in source.namelist()}
        old = b'cy="' + str(352 * 9525).encode() + b'"'
        new = b'cy="' + str(1584 * 9525).encode() + b'"'
        self.assertIn(old, entries["word/document.xml"])
        entries["word/document.xml"] = entries["word/document.xml"].replace(old, new)
        with zipfile.ZipFile(outputs[0], "w") as target:
            for name, content in entries.items():
                target.writestr(name, content)
        errors = check_report(data, *outputs, self.family, min_dpi=1)["errors"]
        self.assertTrue(any("page-fit" in value for value in errors), errors)


if __name__ == "__main__":
    unittest.main()
