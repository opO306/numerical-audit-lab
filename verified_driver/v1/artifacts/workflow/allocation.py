"""Read-only numerical allowance planning; never creates/resets a ledger."""
from pathlib import Path
import json, subprocess, sys
ROOT=Path(__file__).resolve().parents[4]
ledger=ROOT/'runtime_trace/regular_nstep/artifacts/budget.json'
d=json.loads(ledger.read_bytes()); marker=json.loads(ledger.with_suffix('.running.json').read_bytes())
assert marker['state']=='FINISHED'
jobs={'necessary_saved_N3_fixture':30,'ordinary_N3_control':10,'live_N3_positive':55,
 'live_N4_negative':60,'controller_death_paused':15,'controller_death_active':15,
 'post_CURRENT_interruption':25,'nonterminal_replay':45,'terminal_replay':55}
required=sum(jobs.values())+180
result={'existing_ledger':str(ledger),'used_seconds':d['used_seconds'],'remaining_seconds':3600-d['used_seconds'],
 'guard_caps_seconds':jobs,'fixture_unit_regression_reserved_seconds':180,'required_total_upper_seconds':required,
 'fits_existing_allowance':required<=3600-d['used_seconds'],'interpretation':'hard stop caps, not predicted durations; no promise of completion within caps',
 'additional_fixture_reason':'No saved completed N3 found; Task4 final S2->S3 needs actual terminal evidence; original batch capture only, never V1 authority evidence',
 'paid_resources':False,'new_ledger':False}
out=ROOT/'verified_driver/v1/artifacts/execution-allocation.json'
with out.open('x') as f: json.dump(result,f,sort_keys=True,indent=2)
print(json.dumps(result))
if not result['fits_existing_allowance']: raise SystemExit(2)
