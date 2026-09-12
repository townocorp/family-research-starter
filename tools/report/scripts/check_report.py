"""Check paired local outputs: text, citations, attributed media and print DPI."""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import hashlib
from html.parser import HTMLParser
import io
import json
import math
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from project import json_object, load_project, no_links
from _lib_capture.media import inspect_image
from _lib_capture.rebuild_catalogue import records

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
EMU_PER_INCH, EMU_PER_PIXEL = 914400, 9525
PAGE_WIDTH, PAGE_HEIGHT, PAGE_MARGIN, CAPTION_RESERVE = 11906, 16838, 1440, 2880
IMAGE_WIDTH, IMAGE_HEIGHT = 528, 720


class CheckError(ValueError):
    pass


def normal(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_manifest(data_path: Path, project: Path, *, expected_data_hash: str | None = None) -> dict:
    root, _ = load_project(project)
    data_path = no_links(data_path)
    if not data_path.is_relative_to(root) or data_path.suffix != ".json":
        raise CheckError("report input must be project-local inert JSON")
    input_bytes = data_path.read_bytes()
    input_hash = hashlib.sha256(input_bytes).hexdigest()
    if expected_data_hash is not None and input_hash != expected_data_hash:
        raise CheckError("report JSON changed since staging")
    json_object(input_bytes.decode("utf-8"))
    records(root)
    env = dict(os.environ, FAMILY_RESEARCH_PYTHON=sys.executable, PYTHONUTF8="1")
    result = subprocess.run(
        ["node", str(Path(__file__).with_name("report_contract.js")), str(data_path),
         "--project", str(root), "--input-sha256", input_hash],
        capture_output=True, text=True, encoding="utf-8", timeout=90, env=env,
    )
    if result.returncode:
        raise CheckError("report preflight incomplete: " + result.stderr.strip())
    manifest = json_object(result.stdout)
    if manifest.get("schema") != 1 or manifest.get("input_sha256") != input_hash:
        raise CheckError("invalid report manifest schema")
    return manifest


class HtmlReport(HTMLParser):
    VOID = {"img", "br", "meta", "link", "hr", "input", "source", "wbr", "area", "base", "embed"}
    TAGS = {"html", "head", "meta", "title", "style", "body", "header", "main", "section",
            "h1", "h2", "h3", "p", "blockquote", "cite", "ul", "ol", "li", "a", "sup",
            "strong", "em", "figure", "img", "figcaption", "span"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.frames, self.texts, self.ids, self.links, self.citations, self.backlinks = [], [], [], [], [], []
        self.figures, self.references, self.chapters, self.errors = [], {}, [], []
        self.reference_text = {}
        self.blocks, self.styles, self.back_text = [], [], []
        self.block_frames = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag not in self.TAGS or len(attrs) != len(attributes):
            self.errors.append("HTML contains an unsupported element or duplicate attributes")
        if tag in ("meta", "title", "style") and not any(frame[0] == "head" for frame in self.frames):
            self.errors.append("HTML head-only markup appears in the report body")
        classes = (attrs.get("class") or "").split()
        if any(key in attrs for key in ("style", "hidden", "aria-hidden")):
            self.errors.append("HTML contains unsupported hiding/style attributes")
        hidden = any(frame[2] for frame in self.frames) or tag in ("head", "style", "script") or "back" in classes
        if "back" in classes and tag != "a":
            self.errors.append("HTML backlink boilerplate is not an anchor")
        if tag == "style":
            self.styles.append([])
        if tag in ("script", "iframe", "object", "embed", "link", "base"):
            self.errors.append("HTML contains an executable or external-resource element")
        if any(key.lower().startswith("on") for key in attrs) or "srcset" in attrs:
            self.errors.append("HTML contains active attributes")
        if tag == "meta" and attrs.get("http-equiv", "").lower() == "refresh":
            self.errors.append("HTML contains a redirect")
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "a":
            href = attrs.get("href", "")
            if not href.startswith("#"):
                self.errors.append("HTML contains a nonlocal link")
            else:
                self.links.append(href[1:])
            if "ref" in classes:
                self.citations.append((attrs.get("id"), href))
            if "back" in classes:
                parent = next((f[1].get("id") for f in reversed(self.frames) if f[0] == "li"), None)
                self.backlinks.append((parent, href))
                self.back_text.append([])
        if tag == "section" and "chapter" in classes:
            self.chapters.append(attrs.get("id"))
        if tag == "li" and attrs.get("id", "").startswith("ref-"):
            self.references[attrs["id"]] = attrs.get("value")
        if tag == "figure":
            self.figures.append({"evidenceId": attrs.get("data-evidence"), "caption": [], "source": [], "images": []})
        if tag == "img":
            if not any(f[0] == "figure" for f in self.frames):
                self.errors.append("HTML image is outside an attributed figure")
            else:
                self.figures[-1]["images"].append(attrs)
        if not hidden and tag in ("p", "li", "h1", "h2", "h3", "br", "cite"):
            self.texts.append(" ")
        if not hidden and tag in ("p", "li", "h1", "h2", "h3", "cite"):
            if self.block_frames:
                self.errors.append("HTML contains unsupported nested content blocks")
            self.blocks.append([])
            self.block_frames.append((tag, len(self.frames), len(self.blocks) - 1))
        if tag not in self.VOID:
            self.frames.append((tag, attrs, hidden))

    def handle_endtag(self, tag):
        for index in range(len(self.frames) - 1, -1, -1):
            if self.frames[index][0] == tag:
                del self.frames[index:]
                self.block_frames = [block for block in self.block_frames if block[1] < index]
                break
        if tag in ("p", "li", "h1", "h2", "h3", "cite"):
            self.texts.append(" ")

    def handle_data(self, data):
        if any(frame[0] == "style" for frame in self.frames):
            self.styles[-1].append(data)
            if re.search(r"url\s*\(|@import", data, re.I):
                self.errors.append("HTML CSS contains an external resource")
        if any("back" in frame[1].get("class", "").split() for frame in self.frames):
            self.back_text[-1].append(data)
        if self.frames and self.frames[-1][2]:
            return
        if self.block_frames:
            self.blocks[self.block_frames[-1][2]].append(data)
        elif data.strip():
            self.errors.append("HTML contains visible text outside declared content blocks")
        self.texts.append(data)
        if any(frame[0] == "figure" for frame in self.frames):
            for role in ("caption", "source"):
                if any(role in frame[1].get("class", "").split() for frame in self.frames):
                    self.figures[-1][role].append(data)
        if any("reference-text" in frame[1].get("class", "").split() for frame in self.frames):
            identity = next((f[1].get("id") for f in reversed(self.frames) if f[0] == "li"), None)
            self.reference_text.setdefault(identity, []).append(data)


def block_findings(expected: list[str], actual: list[str], label: str) -> list[str]:
    wanted, found = [normal(value) for value in expected], [normal(value) for value in actual]
    if wanted == found:
        return []
    return [f"{label}: complete ordered content blocks differ (expected {len(wanted)}, found {len(found)})"]


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join((node.text or "") if node.tag == f"{{{NS['w']}}}t" else " "
                   if node.tag in (f"{{{NS['w']}}}br", f"{{{NS['w']}}}tab") else ""
                   for node in paragraph.iter())


def check_report(data_path: Path, docx_path: Path, html_path: Path, project: Path, *,
                 print_mode: bool = False, min_dpi: float = 300,
                 expected_data_hash: str | None = None, expected_outputs: dict[str, str] | None = None) -> dict:
    if not math.isfinite(min_dpi) or min_dpi <= 0:
        raise CheckError("minimum DPI must be positive and finite")
    manifest = load_manifest(data_path, project, expected_data_hash=expected_data_hash)
    docx_bytes, html_bytes = no_links(docx_path).read_bytes(), no_links(html_path).read_bytes()
    audited_outputs = {"docx": hashlib.sha256(docx_bytes).hexdigest(), "html": hashlib.sha256(html_bytes).hexdigest()}
    if expected_outputs is not None and audited_outputs != expected_outputs:
        raise CheckError("rendered output changed before its audit")
    errors, warnings, figures = [], [], []
    assets = manifest["assets"]
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip() is not None:
            raise CheckError("DOCX contains duplicate or corrupt entries")
        document = ET.fromstring(archive.read("word/document.xml"))
        rels = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
        relationships = {node.attrib["Id"]: node.attrib for node in rels.findall(f"{{{PACKAGE_REL}}}Relationship")}
        paragraphs = document.findall(".//w:p", NS)
        docx_blocks = [paragraph_text(p) for p in paragraphs if normal(paragraph_text(p))]
        docx_text = normal(" ".join(paragraph_text(p) for p in paragraphs))
        if document.findall(".//w:vanish", NS) or document.findall(".//w:webHidden", NS):
            errors.append("DOCX contains unsupported hidden text")
        page = document.find(".//w:sectPr/w:pgSz", NS)
        margins = document.find(".//w:sectPr/w:pgMar", NS)
        if page is None or margins is None:
            raise CheckError("DOCX page geometry is missing")
        geometry = tuple(int(page.attrib[f"{{{NS['w']}}}{key}"]) for key in ("w", "h"))
        page_margins = tuple(int(margins.attrib[f"{{{NS['w']}}}{key}"]) for key in ("top", "right", "bottom", "left"))
        if geometry != (PAGE_WIDTH, PAGE_HEIGHT) or page_margins != (PAGE_MARGIN,) * 4:
            errors.append("DOCX page geometry differs from the controlled report layout")
        usable_width = (geometry[0] - page_margins[1] - page_margins[3]) * 635
        usable_height = (geometry[1] - page_margins[0] - page_margins[2] - CAPTION_RESERVE) * 635
        citations = [paragraph_text(run) for run in document.findall(".//w:r", NS)
                     if run.find("w:rPr/w:vertAlign[@w:val='superscript']", NS) is not None]
        if citations != [str(value) for value in manifest["citationOccurrences"]]:
            errors.append("DOCX citation occurrences differ from the source")
        placements = [(index, p.find(".//w:drawing", NS)) for index, p in enumerate(paragraphs)
                      if p.find(".//w:drawing", NS) is not None]
        if len(document.findall(".//w:drawing", NS)) != len(assets) or len(placements) != len(assets):
            errors.append("DOCX figure count differs from declared placements")
        for number, ((index, drawing), asset) in enumerate(zip(placements, assets), 1):
            extent, blip = drawing.find(".//wp:extent", NS), drawing.find(".//a:blip", NS)
            if extent is None or blip is None:
                errors.append(f"DOCX figure {number}: missing dimensions or image")
                continue
            rel = relationships.get(blip.attrib.get(f"{{{NS['r']}}}embed"))
            if rel is None or rel.get("TargetMode") == "External":
                errors.append(f"DOCX figure {number}: missing local image relationship")
                continue
            target = posixpath.normpath(posixpath.join("word", rel["Target"]))
            if target.startswith(("../", "/")):
                raise CheckError("unsafe DOCX package path")
            image = inspect_image(archive.read(target))
            cx, cy = int(extent.attrib["cx"]), int(extent.attrib["cy"])
            if min(cx, cy) <= 0:
                raise CheckError("nonpositive rendered image size")
            if cx > min(usable_width, IMAGE_WIDTH * EMU_PER_PIXEL) or cy > min(usable_height, IMAGE_HEIGHT * EMU_PER_PIXEL):
                errors.append(f"DOCX figure {number}: page-fit failure including caption/source reserve")
            if image.sha256 != asset["sha256"]:
                errors.append(f"DOCX figure {number}: image does not match captured evidence")
            if (cx, cy) != (round(asset["renderedWidth"] * EMU_PER_PIXEL), round(asset["renderedHeight"] * EMU_PER_PIXEL)):
                errors.append(f"DOCX figure {number}: wrong rendered dimensions")
            for offset, key, style in ((1, "caption", "Caption"), (2, "source", "EvidenceSource")):
                if index + offset >= len(paragraphs):
                    errors.append(f"DOCX figure {number}: missing {key}")
                    continue
                paragraph = paragraphs[index + offset]
                declaration = paragraph.find("w:pPr/w:pStyle", NS)
                if (normal(paragraph_text(paragraph)) != normal(asset[key]) or declaration is None
                        or declaration.attrib.get(f"{{{NS['w']}}}val") != style):
                    errors.append(f"DOCX figure {number}: wrong {key} association")
            dpi = [image.width * EMU_PER_INCH / cx, image.height * EMU_PER_INCH / cy]
            figures.append({"placement": number, "evidenceId": asset["evidenceId"], "dpi": dpi})
            if min(dpi) + 1e-6 < min_dpi:
                (errors if print_mode else warnings).append(f"Figure {number}: below {min_dpi:g} effective DPI")
    html = HtmlReport()
    html.feed(html_bytes.decode("utf-8"))
    template = (Path(__file__).resolve().parent.parent / "assets" / "html-template.html").read_text(encoding="utf-8")
    expected_styles = re.findall(r"<style>(.*?)</style>", template, flags=re.S)
    if ["".join(value).replace("\r\n", "\n") for value in html.styles] != [
            value.replace("\r\n", "\n") for value in expected_styles]:
        errors.append("HTML styles differ from the controlled template")
    errors.extend(html.errors)
    if len(html.ids) != len(set(html.ids)) or any(link not in html.ids for link in html.links):
        errors.append("HTML has duplicate IDs or broken citation/chapter links")
    if html.chapters != manifest["chapterIds"]:
        errors.append("HTML chapter order differs")
    counts, expected_citations = Counter(), []
    for identity in manifest["citationOccurrences"]:
        counts[identity] += 1
        suffix = "" if counts[identity] == 1 else f"-{counts[identity]}"
        expected_citations.append((f"body-ref-{identity}{suffix}", f"#ref-{identity}"))
    if html.citations != expected_citations:
        errors.append("HTML citation occurrences differ")
    expected_refs = {f"ref-{ref['id']}": str(ref["id"]) for ref in manifest["references"]}
    if html.references != expected_refs:
        errors.append("HTML reference numbering differs")
    expected_backlinks = [(f"ref-{ref['id']}", f"#body-ref-{ref['id']}") for ref in manifest["references"]]
    if html.backlinks != expected_backlinks:
        errors.append("HTML first-citation backlinks differ")
    if ["".join(value) for value in html.back_text] != ["Back"] * len(expected_backlinks):
        errors.append("HTML backlink boilerplate differs")
    if len(html.figures) != len(assets):
        errors.append("HTML figure count differs")
    for number, (figure, asset) in enumerate(zip(html.figures, assets), 1):
        if figure["evidenceId"] != asset["evidenceId"] or any(
                normal("".join(figure[key])) != normal(asset[key]) for key in ("caption", "source")):
            errors.append(f"HTML figure {number}: wrong evidence/caption/source association")
        if len(figure["images"]) != 1:
            errors.append(f"HTML figure {number}: expected one embedded image")
            continue
        attrs = figure["images"][0]
        match = re.fullmatch(r"data:image/(png|jpeg);base64,([A-Za-z0-9+/=]+)", attrs.get("src", ""))
        if not match:
            errors.append(f"HTML figure {number}: image is not embedded PNG/JPEG")
            continue
        image = inspect_image(base64.b64decode(match[2], validate=True))
        if image.sha256 != asset["sha256"] or attrs.get("alt") != asset["caption"]:
            errors.append(f"HTML figure {number}: wrong image bytes or alternative text")
        if attrs.get("width") != str(asset["renderedWidth"]) or attrs.get("height") != str(asset["renderedHeight"]):
            errors.append(f"HTML figure {number}: wrong rendered dimensions")
        try:
            width, height = int(attrs["width"]), int(attrs["height"])
            if not 0 < width <= IMAGE_WIDTH or not 0 < height <= IMAGE_HEIGHT:
                errors.append(f"HTML figure {number}: page-fit failure")
        except (KeyError, ValueError):
            errors.append(f"HTML figure {number}: invalid page-fit dimensions")
    visible = normal("".join(html.texts))
    errors.extend(block_findings(manifest["texts"], docx_blocks, "DOCX"))
    errors.extend(block_findings(manifest["texts"], ["".join(value) for value in html.blocks], "HTML"))
    if not docx_text or not visible or not manifest["texts"]:
        errors.append("nonempty source and paired output text required")
    return {"errors": errors, "warnings": warnings, "figures": figures,
            "audited_outputs": audited_outputs, "input_sha256": manifest["input_sha256"],
            "text_fields_checked": len(manifest["texts"]), "reference_count": len(manifest["references"]),
            "scope": "structural fidelity and source integrity, not historical truth or publication permission"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("data", type=Path)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--docx", type=Path, required=True)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--print", action="store_true", dest="print_mode")
    parser.add_argument("--min-dpi", type=float, default=300)
    args = parser.parse_args()
    try:
        result = check_report(args.data, args.docx, args.html, args.project,
                              print_mode=args.print_mode, min_dpi=args.min_dpi)
        print(json.dumps(result, indent=2))
        return 1 if result["errors"] else 0
    except (OSError, ValueError, ImportError, subprocess.SubprocessError, zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
        print(f"ERROR: report check incomplete: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
