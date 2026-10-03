"""Saved, repaired local numerical fixtures exercise semantic composition."""
from pathlib import Path


def test_all_fifteen_saved_semantic_refusals(tmp_path):
    from runtime_trace.regular_2step.mutations import generate
    root = Path(__file__).resolve().parents[3]
    manifest = generate(root, tmp_path / 'mutations')
    semantic = [r for r in manifest['results'] if r['mode'] == 'REPAIRED_SEMANTIC']
    assert len(semantic) == 15
    assert {r['class'] for r in semantic} == set(range(1, 16))
    assert all(r['result']['verdict'] == 'REFUSED' for r in semantic)
    assert all(r['result']['stage'] == 'SEMANTIC' for r in semantic)
    assert all((tmp_path / 'mutations' / r['directory'] / 'repair.json').is_file() for r in semantic)
    controls = [r for r in manifest['results'] if r['mode'] != 'REPAIRED_SEMANTIC']
    assert {r['result']['stage'] for r in controls} == {'HASH', 'TRUST'}
