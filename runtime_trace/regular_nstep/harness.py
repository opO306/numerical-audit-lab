"""Execute the existing original API harness with parameter-only source changes."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime_trace.regular_nstep.acquire import harness_source, validate_n
from runtime_trace.regular_nstep.resources import reserve_writer

validate_n(int(os.environ['RTN_STEPS']))
# The unchanged old harness writes a small environment/result receipt directly.
# Allocate its complete 1 MiB ceiling before it runs (normal receipt <4 KiB).
reserve_writer(1048576)
source, proof = harness_source(ROOT)
exec(compile(source, str(ROOT / 'runtime_trace/harness.py'), 'exec'),
     {'__file__': str(ROOT / 'runtime_trace/harness.py'), '__name__': '__main__'})
