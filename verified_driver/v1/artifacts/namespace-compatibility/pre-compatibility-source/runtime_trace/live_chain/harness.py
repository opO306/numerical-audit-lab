"""Parameter-only execution of the unchanged pinned original Gala harness."""
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from verified_driver.v1.model import HARNESS_SHA, digest_bytes
from runtime_trace.regular_nstep.acquire import harness_source, validate_n
from runtime_trace.regular_nstep.resources import reserve_writer
if __name__=='__main__':
    validate_n(int(os.environ['RTN_STEPS']))
    if digest_bytes((ROOT/'runtime_trace/harness.py').read_bytes())!=HARNESS_SHA: raise ValueError('original harness changed')
    source,proof=harness_source(ROOT)
    reserve_writer(1048576)
    exec(compile(source,str(ROOT/'runtime_trace/harness.py'),'exec'),
      {'__file__':str(ROOT/'runtime_trace/harness.py'),'__name__':'__main__'})
