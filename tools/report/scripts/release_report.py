"""Stage, check and deliver a local report pair. Never publish or upload it."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from check_report import CheckError, check_report, load_manifest
from markdown_to_data import convert
from project import contained, load_project, no_links
from _lib_capture.atomic import write_new
from _lib_capture.rebuild_catalogue import records

HERE = Path(__file__).resolve().parent


class RecoveryRequired(CheckError):
    pass


def _deliver(stages: list[Path], targets: list[Path], previous: dict[Path, bytes | None], *,
             audited: dict[Path, bytes]) -> None:
    for target, old in previous.items():
        if (target.read_bytes() if target.exists() else None) != old:
            raise CheckError("an output changed during staging; no release replacement attempted")
    backups, delivered = {}, []
    delivery_files = []
    for index, (stage, target) in enumerate(zip(stages, targets)):
        if stage.read_bytes() != audited[target]:
            raise CheckError("audited output changed before delivery")
        delivery = stage.parent / f"delivery-{index}.bin"
        write_new(delivery, audited[target])
        delivery_files.append(delivery)
    for index, target in enumerate(targets):
        if previous[target] is not None:
            backup = stages[0].parent / f"previous-{index}.backup"
            write_new(backup, previous[target])
            backups[target] = backup
    try:
        for stage, target in zip(delivery_files, targets):
            if previous[target] is None:
                os.link(stage, target)
            else:
                os.replace(stage, target)
            delivered.append(target)
    except OSError as exc:
        failures = []
        for target in reversed(delivered):
            try:
                if target.read_bytes() != audited[target]:
                    failures.append(target.name)
                elif target in backups:
                    os.replace(backups[target], target)
                else:
                    target.unlink()
            except OSError:
                failures.append(target.name)
        if failures:
            raise RecoveryRequired(f"delivery/rollback incomplete; recovery files retained at {stages[0].parent}") from exc
        raise CheckError("pair delivery failed; prior outputs restored") from exc


def release_report(project: Path, draft_path: Path, output: str, *,
                   print_mode: bool = False, min_dpi: float = 300, overwrite: bool = False) -> dict:
    root, _ = load_project(project)
    if not math.isfinite(min_dpi) or min_dpi <= 0:
        raise CheckError("minimum DPI must be positive and finite")
    draft_path = no_links(draft_path)
    if not draft_path.is_relative_to(root) or draft_path.suffix.lower() != ".md":
        raise CheckError("draft must be project-local Markdown")
    base = contained(root, output)
    releases = contained(root, "reports/releases")
    if not base.is_relative_to(releases) or base == releases:
        raise CheckError("report outputs must be under reports/releases")
    if not base.parent.is_dir():
        raise CheckError("output parent must already exist")
    targets = [contained(root, str(base.relative_to(root)) + suffix) for suffix in (".docx", ".html")]
    previous = {target: target.read_bytes() if target.exists() else None for target in targets}
    if not overwrite and any(value is not None for value in previous.values()):
        raise FileExistsError("report output already exists; choose a new name or explicitly --overwrite")
    found = records(root)
    sources = [draft_path, contained(root, "project.json"), HERE.parent / "assets" / "html-template.html"]
    for identity, record in found.items():
        sources.extend([contained(root, f"evidence/captures/{identity}/record.md"),
                        contained(root, f"evidence/captures/{identity}/{record['local_artefact']}")])
        if record.get("transcript_sha256"):
            sources.append(contained(root, f"evidence/captures/{identity}/transcript.txt"))
    for target in targets:
        if any(target == source or (target.exists() and target.samefile(source)) for source in sources):
            raise CheckError("release target aliases a source")
    snapshot = {source: hashlib.sha256(source.read_bytes()).hexdigest() for source in sources}
    lock = contained(root, str(base.parent.relative_to(root) / ".report-release.lock"))
    write_new(lock, b"Single-writer report release in progress.\n")
    stage = None
    retain = False
    try:
        stage = Path(tempfile.mkdtemp(prefix=".report-stage-", dir=base.parent)).resolve()
        data_path = stage / "data.json"
        write_new(data_path, (json.dumps(convert(draft_path, root), ensure_ascii=False,
                                         allow_nan=False, indent=2) + "\n").encode("utf-8"))
        input_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()
        snapshot[data_path] = input_hash
        load_manifest(data_path, root, expected_data_hash=input_hash)
        outputs = [stage / "report.docx", stage / "report.html"]
        env = dict(os.environ, FAMILY_RESEARCH_PYTHON=sys.executable, PYTHONUTF8="1")
        for script, target in zip(("create_docx.js", "create_html.js"), outputs):
            result = subprocess.run(["node", str(HERE / script), str(data_path), str(target),
                                     "--project", str(root), "--input-sha256", input_hash], capture_output=True, text=True,
                                    encoding="utf-8", timeout=180, env=env)
            if result.returncode:
                raise CheckError(f"{script} failed before delivery: {result.stderr.strip()}")
        expected_outputs = {key: hashlib.sha256(path.read_bytes()).hexdigest()
                            for key, path in zip(("docx", "html"), outputs)}
        result = check_report(data_path, outputs[0], outputs[1], root, print_mode=print_mode,
                              min_dpi=min_dpi, expected_data_hash=input_hash, expected_outputs=expected_outputs)
        if result["errors"]:
            raise CheckError("paired output check failed: " + "; ".join(result["errors"]))
        for source, expected in snapshot.items():
            if hashlib.sha256(no_links(source).read_bytes()).hexdigest() != expected:
                raise CheckError("a source changed during staging; no release delivered")
        audited = {}
        for key, path, target in zip(("docx", "html"), outputs, targets):
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != result["audited_outputs"][key]:
                raise CheckError("audited output changed after checking; no release delivered")
            audited[target] = content
        try:
            _deliver(outputs, targets, previous, audited=audited)
        except RecoveryRequired:
            retain = True
            raise
        return {"delivered": True, "docx": str(targets[0]), "html": str(targets[1]), "check": result}
    finally:
        if stage is not None and not retain:
            for name in ("data.json", "report.docx", "report.html", "previous-0.backup", "previous-1.backup",
                         "delivery-0.bin", "delivery-1.bin"):
                (stage / name).unlink(missing_ok=True)
            stage.rmdir()
        lock.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--print", action="store_true", dest="print_mode")
    parser.add_argument("--min-dpi", type=float, default=300)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        result = release_report(args.project, args.draft, args.output, print_mode=args.print_mode,
                                min_dpi=args.min_dpi, overwrite=args.overwrite)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, ImportError, subprocess.SubprocessError, zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
        print(f"ERROR: release incomplete: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
