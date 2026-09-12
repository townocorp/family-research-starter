"""Generic candidate checks. No private search list or neighbouring project lookup."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

IGNORED = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
ROOT_FILES = {"README.md", "AGENTS.md", "CLAUDE.md", ".gitignore", ".gitattributes", "requirements.txt", "LICENSE", "THIRD_PARTY_NOTICES.md"}
ROOT_DIRS = {".github", ".claude", "docs", "templates", "tools", "tests"}
SUFFIXES = {".md", ".py", ".js", ".cjs", ".json", ".html", ".txt", ".yml"}
PATTERNS = (
    ("private-key material", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("personal absolute path", re.compile(r"(?i)[A-Z]:\\+(?:Users|home)\\+[A-Za-z0-9_.-]+|/(?:Users|home)/[A-Za-z0-9_.-]+")),
)


def candidate_files(root: Path) -> tuple[list[Path], list[str]]:
    files, errors = [], []
    def fail(error):
        raise error
    for current, dirs, names in os.walk(root, followlinks=False, onerror=fail):
        folder = Path(current)
        for name in list(dirs):
            path = folder / name
            if name in IGNORED:
                dirs.remove(name)
                continue
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                errors.append(f"linked candidate directory: {path.relative_to(root)}")
                dirs.remove(name)
            elif folder == root and name not in ROOT_DIRS:
                errors.append(f"unexpected candidate directory: {name}")
                dirs.remove(name)
        for name in names:
            if name in IGNORED:
                continue
            path = folder / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                errors.append(f"linked candidate file: {path.relative_to(root)}")
            elif (folder == root and name not in ROOT_FILES) or (folder != root and path.suffix not in SUFFIXES):
                errors.append(f"unexpected candidate file: {path.relative_to(root)}")
            else:
                files.append(path)
    return sorted(files), errors


def local_link_findings(path: Path, root: Path) -> list[str]:
    if path.suffix != ".md" or "templates" in path.relative_to(root).parts:
        return []
    raw = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
    findings = []
    for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", raw):
        target = link.split("#", 1)[0]
        if not target or re.match(r"https?://", target):
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            findings.append(f"broken/noncontained local link in {path.relative_to(root)}")
    return findings


def review(root: Path, *, extra_markers: tuple[str, ...] = ()) -> list[str]:
    files, errors = candidate_files(root)
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"non-UTF-8 candidate: {path.relative_to(root)}")
            continue
        for label, pattern in PATTERNS:
            if pattern.search(text):
                errors.append(f"{label}: {path.relative_to(root)}")
        if any(marker in text for marker in extra_markers):
            errors.append(f"external review marker matched: {path.relative_to(root)}")
        errors.extend(local_link_findings(path, root))
    for skill in ("family-research", "family-report"):
        path = root / ".claude" / "skills" / skill / "SKILL.md"
        if not path.is_file():
            errors.append(f"missing skill: {skill}")
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith(f"---\nname: {skill}\ndescription: ") or "\n---\n" not in text[4:]:
            errors.append(f"invalid skill frontmatter: {skill}")
        if re.search(r"(?m)^allowed-tools:|^!\x60", text):
            errors.append(f"unexpected tool preapproval/dynamic invocation: {skill}")
    return errors


def history_findings(root: Path) -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True)
    errors = []
    for name in result.stdout.decode("utf-8").split("\0"):
        if name and set(Path(name).parts) & IGNORED:
            errors.append("generated/private dependency directory appears in tracked files")
    result = subprocess.run(["git", "--no-pager", "log", "HEAD", "--format=%ae%n%ce"],
                            cwd=root, capture_output=True, text=True, check=True)
    if any(not email.endswith("@users.noreply.github.com") and email not in {"noreply@github.com", "copilot@github.com"}
           for email in result.stdout.splitlines()):
        errors.append("branch author/committer email needs explicit privacy review")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    try:
        root = Path(__file__).resolve().parent.parent
        errors = review(root)
        if args.history:
            errors.extend(history_findings(root))
        for error in errors:
            print(f"FINDING: {error}")
        print("Generic checks only; complete manual and independent privacy review remains necessary.")
        return 1 if errors else 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: candidate review incomplete: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
