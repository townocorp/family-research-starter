"""Fully decode the explicitly declared image files before rendering."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _lib_capture.media import inspect_image
from project import no_links


def main() -> int:
    try:
        paths = json.load(sys.stdin)
        if not isinstance(paths, list) or any(not isinstance(value, str) for value in paths):
            raise ValueError("expected a list of declared local image paths")
        result = []
        for value in paths:
            image = inspect_image(no_links(Path(value)).read_bytes())
            result.append({"sha256": image.sha256, "width": image.width, "height": image.height})
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, ImportError) as exc:
        print(f"ERROR: full image decode incomplete: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
