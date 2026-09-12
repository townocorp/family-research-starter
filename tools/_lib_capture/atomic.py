"""Exclusive creation and atomic replacement of explicitly derived files."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time


def write_new(path: Path, content: bytes) -> None:
    if not content:
        raise ValueError("refusing to create an empty output")
    with path.open("xb") as output:
        try:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        except OSError:
            output.close()
            path.unlink()
            raise


def write_bytes(path: Path, content: bytes) -> None:
    """Replace a derived file; callers must validate ownership and containment."""
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError as exc:
                if getattr(exc, "winerror", None) not in (5, 32) or attempt == 4:
                    raise
                time.sleep(0.02 * 2**attempt)
    finally:
        temporary.unlink(missing_ok=True)
