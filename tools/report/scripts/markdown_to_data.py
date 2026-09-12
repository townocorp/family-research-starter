"""Convert the documented report Markdown subset to inert JSON, never code."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from project import contained, load_project, no_links
from _lib_capture.atomic import write_new
from _lib_capture.sidecar import valid_date


def slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]
    return value or "section-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def parse_frontmatter(text: str) -> tuple[dict, list[str]]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("report requires explicit metadata frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("unclosed report frontmatter") from exc
    fields = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if not separator or key in fields or key not in ("title", "author", "date", "round"):
            raise ValueError("unsupported, duplicate or malformed report metadata")
        value = value.strip()
        if key == "round":
            if not re.fullmatch(r"\d+", value):
                raise ValueError("report round must be a nonnegative integer")
            fields[key] = int(value)
        else:
            fields[key] = json.loads(value) if value.startswith('"') else value
            if not isinstance(fields[key], str) or not fields[key].strip():
                raise ValueError(f"report {key} must be nonempty text")
    if fields.keys() != {"title", "author", "date", "round"}:
        raise ValueError("report metadata requires title, author, date and round")
    if not valid_date(fields["date"], unknown=True):
        raise ValueError("report date must be ISO, a year or 'unknown'")
    return fields, lines[end + 1:]


def convert(md_path: Path, project: Path) -> dict:
    root, _ = load_project(project)
    md_path = no_links(md_path)
    if not md_path.is_relative_to(root):
        raise ValueError("report draft must be inside the private project")
    meta, lines = parse_frontmatter(md_path.read_bytes().decode("utf-8"))
    chapters, references, paragraph = [], [], []
    ids = {"references"}
    reference_ids = set()
    current = None

    def append(section):
        if current is None:
            raise ValueError("narrative must follow a # chapter heading")
        current["sections"].append(section)

    def flush():
        if paragraph:
            append({"type": "p", "text": " ".join(paragraph)})
            paragraph.clear()

    for number, raw in enumerate(lines, 1):
        line = raw.rstrip()
        if not line:
            flush()
            continue
        ref = re.fullmatch(r"\[\^([1-9]\d*)\]:\s*(E\d{3,})\s*\|\s*([^|]+)\|\s*(.+)", line)
        if ref:
            flush()
            identity = int(ref[1])
            if identity in reference_ids:
                raise ValueError(f"duplicate reference {identity}")
            reference_ids.add(identity)
            locator, citation = ref[3].strip(), ref[4].strip()
            references.append({"id": identity, "evidenceId": ref[2], "locator": locator,
                               "short": ref[2], "long": f"{ref[2]}; {locator}; {citation}"})
            continue
        if re.match(r"^\[\^.*\]:", line):
            raise ValueError("reference syntax is [^N]: E001 | precise locator | full citation")
        heading = re.fullmatch(r"(#{1,3}) (.+)", line)
        if heading:
            flush()
            if len(heading[1]) == 1:
                identity = slugify(heading[2])
                base, suffix = identity, 2
                while identity in ids:
                    identity, suffix = f"{base}-{suffix}", suffix + 1
                ids.add(identity)
                current = {"id": identity, "title": heading[2], "sections": []}
                chapters.append(current)
            else:
                append({"type": "h" + str(len(heading[1])), "text": heading[2]})
            continue
        image = re.fullmatch(r"!\[(.*)\]\(([^)]+)\)", line)
        if image:
            flush()
            parts = [part.strip() for part in image[1].split("|")]
            if len(parts) != 3 or any(not part for part in parts):
                raise ValueError("figure syntax is ![E001|caption with citation|source attribution](relative-path)")
            path = no_links(md_path.parent / image[2])
            if not path.is_relative_to(root):
                raise ValueError("figure path escapes the private project")
            append({"type": "image", "evidenceId": parts[0], "caption": parts[1],
                    "source": parts[2], "file": path.relative_to(root).as_posix()})
            continue
        if line.startswith("> "):
            flush()
            text, separator, attribution = line[2:].rpartition(" | ")
            if not separator or not text or not attribution:
                raise ValueError("each quote line needs > text | speaker/context attribution")
            append({"type": "quote", "text": text, "attribution": attribution})
            continue
        if line.startswith("- "):
            flush()
            if not line[2:].strip():
                raise ValueError("empty bullet")
            append({"type": "bullet", "text": line[2:]})
            continue
        if (line[0].isspace() or line.startswith(("#", "```", "~~~", "|", "!", ">", "---", "<"))
                or re.match(r"\d+[.)]\s", line)):
            raise ValueError(f"unsupported report structure at body line {number}; see docs/reports.md")
        paragraph.append(line)
    flush()
    if not chapters or not any(
            section["type"] in ("p", "quote", "bullet")
            for chapter in chapters for section in chapter["sections"]):
        raise ValueError("report requires nonempty narrative")
    return {"schema": 1, "meta": meta, "chapters": chapters,
            "references": sorted(references, key=lambda ref: ref["id"])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("input", type=Path)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        root, _ = load_project(args.project)
        output = contained(root, args.out)
        data = (json.dumps(convert(args.input, root), ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
        write_new(output, data)
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: conversion incomplete: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
