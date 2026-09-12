"""All fixture people, records and media are synthetic and generated locally."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "report" / "scripts"))
from project import initialise
from capture import capture


def metadata(identity="E001", **changes):
    value = {
        "evidence_id": identity, "source_type": "oral-history", "source_date": "unknown",
        "captured": "2000-01-01", "source_locator": "synthetic document, line 1",
        "custody": "Generated fixture; synthetic Person P001 supplied the text",
        "rights": "Synthetic test material only", "consent": "Synthetic test; no real narrator",
        "claim": "The synthetic source attributes a memory to Person P001",
        "basis": "source", "confidence": "Tentative", "rationale": "Synthetic and uncorroborated",
        "people": ["P001", "P002"], "round": 1, "supporting_evidence": [identity],
        "opposing_evidence": [], "summary": "A generated source, not a historical finding", "url": "",
    }
    value.update(changes)
    return value


def image_bytes(width=1650, height=1100):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (width, height), "white")
    ImageDraw.Draw(image).text((10, 10), "SYNTHETIC Person P001", fill="black")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def report_markdown(image=True):
    figure = "\n![E002|Synthetic caption [^7]|Generated image; no historical subject](../../evidence/captures/E002/source.png)\n" if image else ""
    ref = "\n[^7]: E002 | entire synthetic image | Generated test fixture." if image else ""
    return (
        '---\ntitle: "Synthetic research report"\nauthor: "P001"\ndate: "unknown"\nround: 1\n---\n'
        "# Findings\n\nPerson P001 recalls Person P002. This is an attributed memory, not proof.[^1][^1]\n\n"
        "> A synthetic recollection. [^1] | Person P001; synthetic context, date unknown.\n"
        + figure +
        "\n## Uncertainty and next steps\n\n- Seek independent evidence before accepting the relationship.[^1]\n\n"
        "[^1]: E001 | line 1 | Person P001; generated oral-history fixture, source date unknown."
        + ref + "\n")


class FamilyCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="synthetic-family-")
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name).resolve()
        self.family = initialise(self.parent / "family", owner="P001", canon="markdown",
                                 canon_location=None, skills=True)
        self.env = dict(os.environ, FAMILY_RESEARCH_PYTHON=sys.executable, PYTHONUTF8="1",
                        NODE_PATH=str(ROOT / "tools" / "report" / "scripts" / "node_modules"))
        self.patch_env = patch.dict(os.environ, self.env)
        self.patch_env.start()
        self.addCleanup(self.patch_env.stop)

    def add_capture(self, identity="E001", content=b"Person P001 remembers Person P002.\r\n", suffix=".txt", **changes):
        source = self.family / "originals" / ("photos" if suffix == ".png" else "stories") / (identity + suffix)
        source.write_bytes(content)
        meta = self.family / "evidence" / (identity + ".json")
        meta.write_text(json.dumps(metadata(identity, **changes), ensure_ascii=False), encoding="utf-8")
        capture(self.family, source, meta)
        return source, meta

    def make_report(self, *, image=True, pixels=(1650, 1100)):
        self.add_capture()
        if image:
            self.add_capture("E002", image_bytes(*pixels), ".png", source_type="local")
        draft = self.family / "reports" / "drafts" / "round-001.md"
        draft.write_text(report_markdown(image), encoding="utf-8")
        return draft

    def cli(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(self.family / "tools" / "starter.py"), *map(str, args)],
                                cwd=self.family, env=self.env, capture_output=True, text=True, encoding="utf-8")
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result
