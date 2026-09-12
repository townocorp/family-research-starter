"""Neutral identifiers and safe descriptive filename segments."""
import re
import unicodedata


def slugify_segment(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    value = re.sub(r"[^A-Za-z0-9]+", "-", normalized).strip("-")
    if not value or value.upper() in {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10)),
    }:
        raise ValueError("a non-reserved filename segment is required")
    return value


def evidence_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"E[0-9]{3,}", value):
        raise ValueError("evidence_id must be E followed by at least three digits")
    return value


def source_extension(value: str) -> str:
    suffix = value.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,11}", suffix):
        raise ValueError("source extension must be 1-11 ASCII letters or digits")
    return suffix
