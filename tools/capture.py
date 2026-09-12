"""Lossless, explicit local-file capture. Originals are never opened for writing."""
from __future__ import annotations

import hashlib
from pathlib import Path

from project import contained, json_object, load_project, no_links
from _lib_capture.atomic import write_new
from _lib_capture.media import inspect_original
from _lib_capture.sidecar import (
    OPTIONAL, REQUIRED, SidecarSpec, render_sidecar, validate_metadata,
)
from _lib_capture.slug import source_extension


def prepare_transcript(root: Path, metadata: dict) -> tuple[dict, bytes | None]:
    value = metadata.get("transcript")
    if value is None:
        return {}, None
    keys = {"file", "method", "author", "source_locator", "start", "end", "quote"}
    if not isinstance(value, dict) or value.keys() != keys:
        raise ValueError("transcript requires file, method, author, source_locator, start, end and quote")
    for field in ("file", "method", "author", "source_locator", "quote"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError(f"transcript {field} must be nonempty text")
    raw = contained(root, value["file"]).read_bytes()
    text = raw.decode("utf-8")
    start, end = value["start"], value["end"]
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
        raise ValueError("transcript span is outside the unnormalised Unicode text")
    if text[start:end] != value["quote"]:
        raise ValueError("transcript quote does not equal its exact source span")
    return {
        "transcript_sha256": hashlib.sha256(raw).hexdigest(),
        "transcript_method": value["method"], "transcript_author": value["author"],
        "transcript_locator": value["source_locator"],
        "span_start": start, "span_end": end, "quote": value["quote"],
    }, raw


def capture(project: Path, source: Path, metadata_path: Path) -> dict:
    root, _ = load_project(project)
    source, metadata_path = no_links(source), no_links(metadata_path)
    metadata = json_object(metadata_path.read_text(encoding="utf-8"))
    unknown = metadata.keys() - set(REQUIRED) - set(OPTIONAL)
    if unknown:
        raise ValueError("unknown capture fields: " + ", ".join(sorted(unknown)))
    validate_metadata(metadata)
    identity = metadata["evidence_id"]
    for related in metadata["supporting_evidence"] + metadata["opposing_evidence"]:
        if related != identity and not contained(root, f"evidence/captures/{related}/record.md").is_file():
            raise ValueError(f"assessment links to uncaptured evidence {related}")
    suffix = source_extension(source.suffix)
    content = source.read_bytes()
    media_check = inspect_original(content, suffix)
    transcript_fields, transcript_bytes = prepare_transcript(root, metadata)
    record = {key: value for key, value in metadata.items() if key != "transcript"}
    spec = SidecarSpec(record, "source" + suffix, hashlib.sha256(content).hexdigest(),
                       len(content), source.name, media_check, **transcript_fields)
    files = {"source" + suffix: content,
             "record.md": render_sidecar(spec)}
    if transcript_bytes is not None:
        files["transcript.txt"] = transcript_bytes
    destination = contained(root, f"evidence/captures/{identity}")
    if destination.exists():
        existing = {path.name: contained(root, path.relative_to(root))
                    for path in destination.iterdir()}
        if set(existing) == set(files) and all(
                existing[name].is_file() and existing[name].read_bytes() == data
                for name, data in files.items()):
            return {"evidence_id": identity, "sha256": spec.sha256, "unchanged": True}
        raise FileExistsError(f"capture {identity} differs; use a new evidence ID and record the correction")
    destination.mkdir()
    created = []
    try:
        for name, data in files.items():
            output = contained(root, destination.relative_to(root) / name)
            write_new(output, data)
            created.append(output)
    except (OSError, ValueError):
        for path in reversed(created):
            path.unlink()
        if not any(destination.iterdir()):
            destination.rmdir()
        raise
    return {"evidence_id": identity, "sha256": spec.sha256, "unchanged": False}
