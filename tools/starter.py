"""Project-local family research commands. No network or account discovery."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from project import contained, initialise, load_project


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", allow_abbrev=False)
    init.add_argument("destination", type=Path)
    init.add_argument("--owner", required=True)
    init.add_argument("--canon", required=True, choices=("markdown", "existing"))
    init.add_argument("--canon-location")
    init.add_argument("--skills", action="store_true")
    for name in ("capture", "catalogue", "check", "report"):
        command = commands.add_parser(name, allow_abbrev=False)
        command.add_argument("--project", type=Path, required=True)
        if name == "capture":
            command.add_argument("--file", type=Path, required=True)
            command.add_argument("--metadata", type=Path, required=True)
        elif name == "report":
            command.add_argument("--draft", required=True)
            command.add_argument("--output", required=True)
            command.add_argument("--print", action="store_true", dest="print_mode")
            command.add_argument("--min-dpi", type=float, default=300)
            command.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = initialise(args.destination, owner=args.owner, canon=args.canon,
                                canon_location=args.canon_location, skills=args.skills)
            print(f"Created private scaffold: {result}")
            print("No research imported, packages installed, Git created or files uploaded.")
            print("Open docs/tools.md for project-local prerequisites; start with research/intake.md.")
            return 0
        root, _ = load_project(args.project)
        from _lib_capture.rebuild_catalogue import rebuild, records
        if args.command == "capture":
            from capture import capture
            result = capture(root, args.file, args.metadata)
            try:
                rebuild(root)
            except (OSError, ValueError) as exc:
                raise ValueError(f"capture retained but catalogue incomplete: {exc}") from exc
            print(json.dumps(result))
        elif args.command == "catalogue":
            print(f"Generated catalogue from {rebuild(root)} checked captures; canonical facts unchanged.")
        elif args.command == "check":
            found = records(root)
            if not found:
                raise ValueError("no captures: evidence completeness has not been established")
            print(f"Checked {len(found)} captures and their provenance; historical truth is not certified.")
        else:
            script = Path(__file__).parent / "report" / "scripts" / "release_report.py"
            command = [sys.executable, str(script), "--project", str(root),
                       "--draft", str(contained(root, args.draft)), "--output", args.output,
                       "--min-dpi", str(args.min_dpi)]
            if args.print_mode:
                command.append("--print")
            if args.overwrite:
                command.append("--overwrite")
            return subprocess.run(command, check=False).returncode
        return 0
    except (OSError, ValueError, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
