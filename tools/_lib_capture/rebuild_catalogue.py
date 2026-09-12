"""Check only declared captures and regenerate a separate derived catalogue."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

from project import contained, load_project
from .atomic import write_bytes, write_new
from .sidecar import parse_frontmatter
from .slug import evidence_id, source_extension

HEADER = "# Evidence catalogue (generated)\n"


def records(project: Path) -> dict[str, dict]:
    root, _ = load_project(project)
    folder = contained(root, "evidence/captures")
    result = {}
    for entry in sorted(folder.iterdir()):
        path = contained(root, entry.relative_to(root))
        if not path.is_dir():
            raise ValueError("unexpected file in captures; move notes outside the capture store")
        identity = evidence_id(path.name)
        record_path = contained(root, path.relative_to(root) / "record.md")
        fields = parse_frontmatter(record_path.read_text(encoding="utf-8"))
        if fields["evidence_id"] != identity:
            raise ValueError(f"{identity}: sidecar identifier differs from directory")
        local = fields.get("local_artefact")
        if not isinstance(local, str) or not local.startswith("source."):
            raise ValueError(f"{identity}: invalid local_artefact")
        if local != "source" + source_extension(local[len("source"):]):
            raise ValueError(f"{identity}: noncanonical local_artefact extension")
        original = contained(root, path.relative_to(root) / local)
        raw = original.read_bytes()
        if not raw or type(fields.get("byte_size")) is not int or len(raw) != fields["byte_size"]:
            raise ValueError(f"{identity}: original is empty or its length changed")
        if hashlib.sha256(raw).hexdigest() != fields.get("sha256"):
            raise ValueError(f"{identity}: original hash changed")
        expected = {"record.md", local}
        if fields.get("transcript_sha256"):
            expected.add("transcript.txt")
            transcript_path = contained(root, path.relative_to(root) / "transcript.txt")
            transcript = transcript_path.read_bytes()
            if hashlib.sha256(transcript).hexdigest() != fields["transcript_sha256"]:
                raise ValueError(f"{identity}: transcript hash changed")
            text = transcript.decode("utf-8")
            start, end = fields.get("span_start"), fields.get("span_end")
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
                raise ValueError(f"{identity}: invalid transcript span")
            if text[start:end] != fields.get("quote"):
                raise ValueError(f"{identity}: quote no longer matches source span")
            for key in ("transcript_method", "transcript_author", "transcript_locator"):
                if not isinstance(fields.get(key), str) or not fields[key].strip():
                    raise ValueError(f"{identity}: missing {key}")
        if {child.name for child in path.iterdir()} != expected:
            raise ValueError(f"{identity}: unexpected files; capture revisions must use new IDs")
        for child in path.iterdir():
            contained(root, child.relative_to(root))
        result[identity] = fields
    for identity, fields in result.items():
        for link in fields["supporting_evidence"] + fields["opposing_evidence"]:
            if link not in result:
                raise ValueError(f"{identity}: missing linked evidence {link}")
    return result


def rebuild(project: Path) -> int:
    root, _ = load_project(project)
    found = records(root)
    lines = [HEADER, "Derived inventory only. This does not reconcile or prove canonical facts.\n",
             f"Captures: {len(found)}\n"]
    for identity, fields in found.items():
        lines.extend([
            f"## {identity}\n",
            f"[Provenance](captures/{identity}/record.md)\n",
            f"Claim: {fields['claim']}\n",
            f"Assessment: {fields['confidence']} ({fields['basis']}); {fields['rationale']}\n",
            f"Source locator: {fields['source_locator']}\n",
            f"Captured: {fields['captured']}; round: {fields['round']}\n",
            f"SHA-256: `{fields['sha256']}`\n",
            "Supporting: " + ", ".join(fields["supporting_evidence"]) + "\n",
            "Opposing: " + ", ".join(fields["opposing_evidence"]) + "\n",
        ])
    content = ("\n".join(lines) + "\n").encode("utf-8")
    output = contained(root, "evidence/catalogue.md")
    if output.exists():
        previous = output.read_bytes()
        if not previous.startswith(HEADER.encode("utf-8")):
            raise ValueError("catalogue path contains curated content; refusing replacement")
        if previous != content:
            write_bytes(output, content)
    else:
        write_new(output, content)
    return len(found)
