"""Strict flat YAML metadata with JSON scalar syntax and no replacement writes."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .atomic import write_new
from .slug import evidence_id

CONFIDENCE = ("Unassessed", "Supported", "Tentative", "Disputed")
REQUIRED = ("evidence_id", "source_type", "source_date", "captured", "source_locator",
            "custody", "rights", "consent", "claim", "basis", "confidence", "rationale",
            "people", "round", "supporting_evidence", "opposing_evidence", "summary")
OPTIONAL = ("url", "transcript")


def valid_date(value: str, *, unknown: bool = False) -> bool:
    if not isinstance(value, str):
        return False
    if unknown and (value == "unknown" or re.fullmatch(r"[1-9]\d{3}", value)):
        return True
    try:
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)) and date.fromisoformat(value) is not None
    except ValueError:
        return False


def validate_metadata(fields: dict) -> None:
    missing = set(REQUIRED) - fields.keys()
    if missing:
        raise ValueError("missing capture fields: " + ", ".join(sorted(missing)))
    evidence_id(fields["evidence_id"])
    for key in REQUIRED:
        if key not in ("people", "round", "supporting_evidence", "opposing_evidence"):
            if not isinstance(fields[key], str) or not fields[key].strip() or "REPLACE_" in fields[key]:
                raise ValueError(f"{key} must be nonempty text")
    if not valid_date(fields["captured"]) or not valid_date(fields["source_date"], unknown=True):
        raise ValueError("use a real ISO captured date and source date, year or 'unknown'")
    if fields["confidence"] not in CONFIDENCE:
        raise ValueError("confidence must be Unassessed, Supported, Tentative or Disputed")
    if fields["basis"] not in ("first-hand", "source", "inference"):
        raise ValueError("basis must distinguish first-hand, source or inference")
    if fields["source_type"] not in ("local", "archive", "web", "oral-history", "gedcom"):
        raise ValueError("unsupported source_type")
    if type(fields["round"]) is not int or fields["round"] < 0:
        raise ValueError("round must be a nonnegative integer")
    for key in ("people", "supporting_evidence", "opposing_evidence"):
        values = fields[key]
        pattern = r"P[0-9]{3,}" if key == "people" else r"E[0-9]{3,}"
        if not isinstance(values, list) or any(
                not isinstance(item, str) or not re.fullmatch(pattern, item) for item in values):
            raise ValueError(f"{key} must be a list of stable IDs")
        if len(values) != len(set(values)):
            raise ValueError(f"{key} contains duplicate IDs")
    if fields["confidence"] == "Supported" and not fields["supporting_evidence"]:
        raise ValueError("Supported requires evidence for the stated claim")
    if set(fields["supporting_evidence"]) & set(fields["opposing_evidence"]):
        raise ValueError("split distinct claims before assigning the same evidence opposing roles")
    url = fields.get("url", "")
    if not isinstance(url, str):
        raise ValueError("url must be text")
    if url:
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("source URL must be HTTP(S), without embedded credentials")


@dataclass(frozen=True)
class SidecarSpec:
    metadata: dict
    local_artefact: str
    sha256: str
    byte_size: int
    original_name: str
    media_check: str
    transcript_sha256: str = ""
    transcript_method: str = ""
    transcript_author: str = ""
    transcript_locator: str = ""
    span_start: int | None = None
    span_end: int | None = None
    quote: str = ""

    def fields(self) -> dict:
        validate_metadata(self.metadata)
        extra = asdict(self)
        extra.pop("metadata")
        return {"schema": 1, **self.metadata, **extra}


def render_frontmatter(spec: SidecarSpec) -> str:
    fields = spec.fields()
    return "---\n" + "\n".join(
        f"{key}: {json.dumps(value, ensure_ascii=True, allow_nan=False)}"
        for key, value in fields.items()) + "\n---\n"


def render_body(spec: SidecarSpec) -> str:
    fields = spec.metadata
    return (f"\n# {fields['evidence_id']}\n\n{fields['summary']}\n\n"
            f"## Stated claim\n\n{fields['claim']}\n\n"
            f"Assessment: {fields['confidence']} ({fields['basis']}).\n\n"
            f"Rationale: {fields['rationale']}\n\n"
            "This assessment applies to the stated claim, not an entire person or source.\n")


def write_sidecar(spec: SidecarSpec, path: Path) -> None:
    content = render_sidecar(spec)
    if path.exists() and path.read_bytes() == content:
        return
    write_new(path, content)


def parse_frontmatter(text: str) -> dict:
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0] != "---":
        raise ValueError("missing sidecar frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("unclosed sidecar frontmatter") from exc
    fields = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(": ")
        if not separator or not re.fullmatch(r"[a-z][a-z0-9_]*", key) or key in fields:
            raise ValueError("malformed or duplicate sidecar field")
        fields[key] = json.loads(value)
    validate_metadata(fields)
    required = set(REQUIRED) | (set(SidecarSpec.__dataclass_fields__) - {"metadata"}) | {"schema"}
    if fields.keys() - required - {"url"} or required - fields.keys():
        raise ValueError("unsupported or missing stored sidecar fields")
    if type(fields.get("schema")) is not int or fields["schema"] != 1:
        raise ValueError("unsupported sidecar schema")
    if not isinstance(fields["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", fields["sha256"]):
        raise ValueError("invalid original SHA-256")
    if type(fields["byte_size"]) is not int or fields["byte_size"] <= 0:
        raise ValueError("original byte_size must be a positive integer")
    for key in ("original_name", "media_check", "local_artefact"):
        if not isinstance(fields[key], str) or not fields[key].strip():
            raise ValueError(f"stored {key} must be nonempty text")
    if re.search(r"[/\\]", fields["original_name"]):
        raise ValueError("original_name must not contain a path")
    if fields["transcript_sha256"]:
        if not isinstance(fields["transcript_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", fields["transcript_sha256"]):
            raise ValueError("invalid transcript SHA-256")
    elif any(fields[key] != "" for key in ("transcript_method", "transcript_author", "transcript_locator", "quote")) or any(
            fields[key] is not None for key in ("span_start", "span_end")):
        raise ValueError("transcript metadata requires an actual hashed transcript")
    return fields


def render_sidecar(spec: SidecarSpec) -> bytes:
    content = (render_frontmatter(spec) + render_body(spec)).encode("utf-8")
    if parse_frontmatter(content.decode("utf-8")) != spec.fields():
        raise ValueError("generated sidecar does not round-trip; capture was not written")
    return content
