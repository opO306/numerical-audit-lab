import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN_SEAL = 'ddc6c9822fe5f7af4ff8f2d9e72c8ef7a6be0c3a91b478f5644d45ffbdfe31e8'


def test_gate2c_plan_and_gate2b_inputs_unchanged():
    p = ROOT / 'audit/gate2c/plan_seal.json'
    assert hashlib.sha256(p.read_bytes()).hexdigest() == PLAN_SEAL
    plan = json.loads(p.read_text(encoding='utf-8'))
    assert not any(plan['implementation_files_present_at_seal'].values())
    for seal in (plan, json.loads((ROOT / 'audit/gate2b/closure_seal.json').read_text(encoding='utf-8'))):
        for path, expected in seal['files'].items():
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path


def test_saved_home_and_cloud_digests_match():
    expected = '6ccf3d5dd6f2d274c393c4f266bd740ebe9755fd589e4e335507ba7568b2928d'
    for folder in ('home-pc-2026-10-01', 'cloud-container-2026-10-01'):
        d = json.loads((ROOT / 'reports' / folder / 'gate2b_report.json').read_text(encoding='utf-8'))
        assert d['deterministic_digest'] == expected
        assert hashlib.sha256(json.dumps(d['deterministic'], sort_keys=True, ensure_ascii=False).encode()).hexdigest() == expected
