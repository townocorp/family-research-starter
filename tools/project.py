"""Explicit private-project boundaries and allowlisted fresh-folder creation."""
from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
import re
import stat

from _lib_capture.atomic import write_new

SOURCE_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_FILES = (
    "requirements.txt", "THIRD_PARTY_NOTICES.md",
    "tools/starter.py", "tools/project.py", "tools/capture.py",
    "tools/_lib_capture/__init__.py", "tools/_lib_capture/atomic.py",
    "tools/_lib_capture/slug.py", "tools/_lib_capture/sidecar.py",
    "tools/_lib_capture/media.py", "tools/_lib_capture/rebuild_catalogue.py",
    "tools/report/scripts/markdown_to_data.py", "tools/report/scripts/create_docx.js",
    "tools/report/scripts/create_html.js", "tools/report/scripts/report_contract.js",
    "tools/report/scripts/check_report.py", "tools/report/scripts/media_preflight.py",
    "tools/report/scripts/release_report.py", "tools/report/scripts/package.json",
    "tools/report/scripts/package-lock.json", "tools/report/assets/html-template.html",
    "docs/research-process.md", "docs/tools.md", "docs/provenance.md",
    "docs/reports.md", "docs/privacy-and-sharing.md", "docs/quality.md",
)
SKILLS = ("family-research", "family-report")
FOLDERS = (
    *(f"originals/{name}" for name in
      ("certificates", "scans", "photos", "gedcom", "stories", "interviews", "eulogies")),
    "derived/ocr", "derived/transcripts", "derived/translations",
    "evidence/captures", "research/rounds", "reports/drafts", "reports/releases",
)
TEMPLATES = {
    "AGENTS.md": "AGENTS.md", "CLAUDE.md": "CLAUDE.md",
    "copilot-instructions.md": ".github/copilot-instructions.md",
    "gitignore.txt": ".gitignore",
    "intake.md": "research/intake.md", "people.md": "research/people.md",
    "leads.md": "research/leads.md", "negative-searches.md": "research/negative-searches.md",
    "corrections.md": "research/corrections.md", "round.md": "research/rounds/round-template.md",
    "capture.json": "evidence/capture-template.json", "report.md": "reports/drafts/report-template.md",
}


def no_links(path: Path) -> Path:
    """Check lexical ancestors before resolving, including link/.. traversal."""
    raw = str(path).replace("\\", "/")
    if raw.startswith("//") or raw.casefold().startswith(("/??/", "/device/", "/global??/")) or re.match(r"^[A-Za-z][A-Za-z0-9+.-]+:", raw):
        raise ValueError("network/device namespace paths and URIs are refused; choose a local file")
    windows_path = PureWindowsPath(raw)
    if windows_path.drive and not windows_path.root:
        raise ValueError("drive-relative paths are refused; choose an explicit local path")
    path = path.expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("linked/reparse paths are not supported")
        if stat.S_ISREG(info.st_mode) and getattr(info, "st_nlink", 1) > 1:
            raise ValueError("multiply-linked regular files are not supported")
    return path.resolve()


def contained(root: Path, relative: str | Path) -> Path:
    value = str(relative).replace("\\", "/")
    if not value or Path(value).is_absolute() or PureWindowsPath(value).drive:
        raise ValueError("a project-relative path is required")
    target = no_links(root / value)
    if not target.is_relative_to(root) or target == root:
        raise ValueError("path escapes the private project")
    return target


def json_object(raw: str) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"nonfinite JSON value: {value}")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def load_project(path: Path) -> tuple[Path, dict]:
    root = no_links(path)
    config = json_object(contained(root, "project.json").read_text(encoding="utf-8"))
    if type(config.get("schema")) is not int or config["schema"] != 1 or config.get("kind") != "private-family-research":
        raise ValueError("not an initialised private family project")
    if not isinstance(config.get("owner"), str) or not config["owner"].strip():
        raise ValueError("project owner is required")
    canon = config.get("canon")
    if not isinstance(canon, dict) or canon.get("mode") not in ("markdown", "existing"):
        raise ValueError("explicit canonical-store choice is required")
    if not isinstance(canon.get("location"), str) or not canon["location"].strip():
        raise ValueError("canonical-store location is required")
    if canon["mode"] == "markdown" and canon["location"] != "research/facts.md":
        raise ValueError("Markdown canonical store must be research/facts.md")
    return root, config


def initialise(destination: Path, *, owner: str, canon: str, canon_location: str | None,
               skills: bool, source: Path = SOURCE_ROOT) -> Path:
    if not owner.strip() or canon not in ("markdown", "existing"):
        raise ValueError("owner and an explicit canonical-store choice are required")
    if canon == "existing" and (not canon_location or not canon_location.strip()):
        raise ValueError("existing mode requires --canon-location; it will not be opened")
    if canon == "markdown" and canon_location is not None:
        raise ValueError("--canon-location is only for an existing canonical store")
    target, source = no_links(destination), no_links(source)
    if target == Path(target.anchor) or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError("choose a new private folder outside the starter checkout")
    if target.exists():
        raise FileExistsError("destination already exists; no files changed")
    if not target.parent.is_dir():
        raise ValueError("destination parent must already exist")
    if (source / "project.json").exists():
        raise ValueError("create projects from the shareable starter, not from another family's folder")
    payload = {name: contained(source, name).read_bytes() for name in RUNTIME_FILES}
    templates = dict(TEMPLATES)
    if canon == "markdown":
        templates["facts.md"] = "research/facts.md"
    for name, output in templates.items():
        payload[output] = contained(source, f"templates/family/{name}").read_bytes()
    if skills:
        for name in SKILLS:
            relative = f".claude/skills/{name}/SKILL.md"
            payload[relative] = contained(source, relative).read_bytes()
    config = {"schema": 1, "kind": "private-family-research", "owner": owner,
              "canon": {"mode": canon, "location": canon_location if canon == "existing" else "research/facts.md"},
              "sharing": "private; no upload or publication authorised"}
    payload["project.json"] = (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if any(not data for data in payload.values()):
        raise ValueError("starter payload contains an empty required file")
    created = []
    directories = {target}
    for name in (*FOLDERS, *payload):
        parent = target / name if name in FOLDERS else (target / name).parent
        while parent != target:
            directories.add(parent)
            parent = parent.parent
    made = []
    try:
        target.mkdir()
        made.append(target)
        for directory in sorted(directories - {target}, key=lambda p: (len(p.parts), str(p))):
            directory.mkdir()
            made.append(directory)
        for name, data in payload.items():
            path = contained(target, name)
            write_new(path, data)
            created.append(path)
    except (OSError, ValueError):
        for path in reversed(created):
            path.unlink()
        for directory in reversed(made):
            if not any(directory.iterdir()):
                directory.rmdir()
        raise
    return target
