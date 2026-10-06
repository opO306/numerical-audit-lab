"""Capture an exclusive metadata job's stdout/traceback inside its bounded child."""
from pathlib import Path
import runpy
import sys
import traceback

script, log, *args = sys.argv[1:]
sys.argv = [script, *args]
with Path(log).open('x', encoding='utf-8') as stream:
    sys.stdout = sys.stderr = stream
    try:
        runpy.run_path(script, run_name='__main__')
    except BaseException:
        traceback.print_exc()
        raise
