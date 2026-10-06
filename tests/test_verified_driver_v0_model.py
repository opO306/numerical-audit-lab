from dataclasses import FrozenInstanceError
import hashlib
from pathlib import Path
import pytest
from verified_driver.v0.model import CertifiedState, canonical_bytes, content_id, regular_genesis

ROOT = Path(__file__).resolve().parents[1]
BITS = ('0x0000000000000000', '0x0000000000000000', '0x3fd0000000000000', '0x3fc0000000000000')

def test_regular_genesis_requires_pinned_harness_bytes(tmp_path):
    (tmp_path/'runtime_trace').mkdir()
    (tmp_path/'runtime_trace/harness.py').write_bytes((ROOT/'runtime_trace/harness.py').read_bytes()+b'\n')
    with pytest.raises(ValueError): regular_genesis(tmp_path)

def test_regular_genesis_has_exact_four_initial_bits():
    state = regular_genesis(ROOT)
    assert state.generation == 0 and state.state_bits == BITS
    assert state.predecessor_id is None and state.acceptance_id is None
    with pytest.raises(FrozenInstanceError): state.generation = 1

def test_state_content_id_is_canonical_and_stable():
    expected = b'{"a":1,"z":[2,3]}'
    assert canonical_bytes({'z':[2,3],'a':1}) == expected
    assert content_id({'z':[2,3],'a':1}) == hashlib.sha256(expected).hexdigest()
    assert canonical_bytes(regular_genesis(ROOT)) == canonical_bytes(regular_genesis(ROOT))

@pytest.mark.parametrize('bad', ['0X0000000000000000','0x000000000000000A','0x0','0x7ff8000000000000','0x7ff0000000000000',1])
def test_noncanonical_bits_are_rejected(bad):
    with pytest.raises(ValueError): CertifiedState(0, (bad,*BITS[1:]), '0'*64)

def test_nonfinite_json_and_boolean_generation_are_rejected():
    with pytest.raises(ValueError): canonical_bytes({'x':float('nan')})
    with pytest.raises(ValueError): CertifiedState(True,BITS,'0'*64)
