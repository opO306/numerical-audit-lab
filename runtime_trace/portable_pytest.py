"""Run the actual suite while denying recorded capture-time module file paths.

Only file access is guarded; original traces and binaries stay unchanged.
This is an access-constraint regression run, not a fresh GDB capture.
"""
import json
from pathlib import Path
import sys

import pytest


def main():
    root = Path(__file__).resolve().parents[1]
    capture = json.loads((root / "runtime_trace/artifacts/attempt-05/capture.json").read_text())
    forbidden = set(capture["modules"])
    original_open = Path.open
    blocked = []

    def guarded_open(path, *args, **kwargs):
        if str(path) in forbidden:
            blocked.append(str(path))
            raise FileNotFoundError(f"recorded runtime path unavailable: {path}")
        return original_open(path, *args, **kwargs)

    Path.open = guarded_open
    try:
        result = pytest.main([str(root / "runtime_trace/tests"), "-q"])
    finally:
        Path.open = original_open
    print(json.dumps(dict(forbidden_recorded_paths=sorted(forbidden), blocked_read_attempts=blocked, pytest_exit_code=int(result))))
    return int(result)


if __name__ == "__main__":
    sys.exit(main())
