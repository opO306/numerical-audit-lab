"""Audit existing ledger jobs against planned execution and justified reserve."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent.parent
data=json.loads((HERE/'final-inventory.json').read_bytes())
base={'task8-ordinary-01','task8-positive-02','task8-negative-01','task8-nonterminal-01','task8-terminal-01','task8-paused-death-01','task8-active-death-01','task8-interruption-01','task8-final01'}
rows=[]
for j in data['guarded_jobs']:
    name=j['path'].replace('\\','/').rsplit('/',1)[1]
    classification='original_planned_sequence' if name in base else 'necessary_failure_review_validation_or_reacquisition'
    rows.append({'job':name,'classification':classification,'wall_seconds':j['wall_seconds']})
planned=sum(r['wall_seconds'] for r in rows if r['classification']=='original_planned_sequence')
extra=sum(r['wall_seconds'] for r in rows if r['classification']!='original_planned_sequence')
reserve=4200-data['prior_used_seconds']-400
assert len([r for r in rows if r['classification']=='original_planned_sequence'])==9 and planned<=400 and extra<=reserve
assert abs(planned+extra-data['additional_guarded_wall_seconds'])<1e-9
result={'same_existing_ledger':True,'ceiling_increase':600,'planned_caps_seconds':400,'reserve_allowance_seconds':reserve,'planned_sequence_measured_wall_seconds':planned,'necessary_failure_review_wall_seconds':extra,'remaining_review_reserve_seconds':reserve-extra,'unused_planned_cap_seconds':400-planned,'total_remaining_seconds':data['remaining_seconds'],'reasons':'Initial three reviewer defects; failed S0 writer quota attempt; final reviewer complete-subtree defect RED/minimum fix/GREEN; globally bound source change requires all eight actual stages and full regression reacquisition. No unrelated execution. Details in reruns.md and immutable receipts.','jobs':rows}
with (HERE/'execution-accounting.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,sort_keys=True,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('jobs','reasons')}))
