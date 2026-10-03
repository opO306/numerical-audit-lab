"""Saved local numerical fixture mutations, explicit repairs and trust modes."""
import argparse
import copy
import json
import shutil
from pathlib import Path

from . import checker
from .schema import BASE, COMPONENTS, completion, component_hashes, load, sha, write

CLASSES = {
    1: 'step2 entry component bit', 2: 'step2 entry dynamic ID',
    3: 'different step1 caller endpoint', 4: 'other acquisition step2',
    5: 'deleted operation', 6: 'duplicated operation', 7: 'reordered operations',
    8: 'ADD input order', 9: 'SUB input order', 10: 'equal bits different dynamic ID',
    11: 'state binding swap', 12: 'boundary handoff', 13: 'mixed case component',
    14: 'semantic Form mutation with repaired completion', 15: 'stale caller evidence',
}


def _repair(capture, derived):
    """Repair all enclosing hashes, but never call a semantic proof successful."""
    before = {f: sha(derived / f) for f in (*COMPONENTS, 'chain.json')}
    seal = load(capture / 'acquisition_seal.json')
    seal['sealed_files'] = {name: sha(capture / name) for name in seal['sealed_file_name_set']}
    write(capture / 'acquisition_seal.json', seal)
    report = load(capture / 'structure_report.json')
    report.update(capture_sha256=sha(capture / 'capture.json'), trace_sha256=sha(capture / 'trace.jsonl'),
                  acquisition_seal_sha256=sha(capture / 'acquisition_seal.json'))
    write(capture / 'structure_report.json', report)
    components = load(derived / 'components.json')
    components['structure'].update({k: report[k] for k in ('capture_sha256', 'trace_sha256', 'acquisition_seal_sha256')})
    write(derived / 'components.json', components)
    chain = load(derived / 'chain.json')
    hashes = component_hashes(derived)
    chain['ordered_component_hashes'] = hashes
    chain['identities'][3].update(hashes[0])
    chain['identities'][4].update(hashes[1])
    chain['completion_sha256'] = completion(chain)
    write(derived / 'chain.json', chain)
    return {'before_repair': before,
        'after_repair': {f: sha(derived / f) for f in (*COMPONENTS, 'chain.json')},
        'raw_sealed_files': seal['sealed_files'],
        'completion_recomputed': True, 'component_hashes_recomputed': True,
        'repair_does_not_assert_semantics': True}


def _mutate(number, capture, derived, fresh, root):
    ir, v2, chain = [load(derived / f) for f in ('numeric_ir.json', 'v2_correspondence.json', 'chain.json')]
    raw = load(capture / 'capture.json')
    if number == 1:
        raw['regions'][2]['start_state']['q'][0] = '0x3f70000000000001'
    elif number == 2:
        chain['intermediate_boundary']['carry'][0]['entry_state_id'] += ':other-occurrence'
    elif number == 3:
        raw['process_local_handoff']['roles']['q']['from_bits'][0] = '0x3f70000000000001'
    elif number == 4:
        ir = load(fresh / 'numeric_ir.json')
        v2 = load(fresh / 'v2_correspondence.json')
    elif number in (5, 6, 7):
        for doc in (ir, v2):
            if number == 5:
                del doc['operations'][3]
            elif number == 6:
                doc['operations'].insert(3, copy.deepcopy(doc['operations'][3]))
            else:
                doc['operations'][3:5] = reversed(doc['operations'][3:5])
            for index, op in enumerate(doc['operations']):
                op['ir_sequence'] = index
                if 'v2_sequence' in op:
                    op['v2_sequence'] = index
    elif number in (8, 9):
        kind = 'ADD_BINARY64' if number == 8 else 'SUB_BINARY64'
        index = next(i for i, op in enumerate(ir['operations']) if op['operation_kind'] == kind)
        for doc in (ir, v2):
            op = doc['operations'][index]
            for suffix in ('value_id', 'raw_bits', 'state_id', 'form'):
                a, b = 'input0_' + suffix, 'input1_' + suffix
                if a in op:
                    op[a], op[b] = op[b], op[a]
    elif number == 10:
        op = ir['operations'][0]
        other = next(v for v in ir['values'] if v['width'] == 8 and v['raw_bits'] == op['input0_raw_bits'] and v['value_id'] != op['input0_value_id'])
        op['input0_value_id'] = other['value_id']
        v2['operations'][0]['input0_value_id'] = other['value_id']
    elif number == 11:
        states = v2['state_bindings']
        states[0]['state_id'], states[1]['state_id'] = states[1]['state_id'], states[0]['state_id']
    elif number == 12:
        chain['intermediate_boundary']['carry'][0]['audited_endpoint']['copy_source_value_id'] = chain['intermediate_boundary']['carry'][1]['audited_endpoint']['copy_source_value_id']
    elif number == 13:
        components = load(derived / 'components.json')
        components['old_caller'] = load(fresh / 'components.json')['old_caller']
        write(derived / 'components.json', components)
    elif number == 14:
        v2['operations'][-1]['output_form']['box'] = '0x0.0p+0'
    elif number == 15:
        stale = 'runtime_trace/caller_transition/artifacts/audited-attempt-05/capture.json'
        raw['antecedent_binding']['antecedent_capture_path'] = stale
        raw['antecedent_binding']['antecedent_capture_sha256'] = sha(root / stale)
    write(capture / 'capture.json', raw)
    write(derived / 'numeric_ir.json', ir)
    write(derived / 'v2_correspondence.json', v2)
    write(derived / 'chain.json', chain)


def generate(root: Path, out: Path) -> dict:
    """All private fixture copies and repairs are kept, including failures."""
    root, out = Path(root).resolve(), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = root / BASE / 'artifacts'
    # Reuse normal fixtures if published; temporary test runs build their own.
    known, fresh = source / 'derived/known', source / 'derived/fresh'
    if not known.is_dir() or not fresh.is_dir():
        from .producer import build
        for label in ('known', 'fresh'):
            build(source / (label + '-03'), out / ('baseline-' + label), root)
        known, fresh = out / 'baseline-known', out / 'baseline-fresh'
    results = []
    for number in range(1, 18):
        folder = out / f'{number:02d}'
        folder.mkdir()
        capture, derived = folder / 'capture', folder / 'derived'
        shutil.copytree(source / 'known-03', capture)
        shutil.copytree(known, derived)
        before = {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}
        if number <= 15:
            _mutate(number, capture, derived, fresh, root)
            repair = _repair(capture, derived)
            mode = 'REPAIRED_SEMANTIC'
        elif number == 16:
            chain = load(derived / 'chain.json')
            chain['case'] = 'changed-without-repair'
            write(derived / 'chain.json', chain)
            repair, mode = {'completion_recomputed': False}, 'HASH_CONTROL'
        else:
            repair, mode = {'public_trust_path_must_refuse_copy': True}, 'TRUST_CONTROL'
        pins = {'mode': 'TEST_ONLY_REPIN', 'capture_directory': str(capture),
                'seal': sha(capture / 'acquisition_seal.json'), 'structure': sha(capture / 'structure_report.json')}
        result = checker.check(capture, derived, root) if number == 17 else checker._TEST_ONLY_REPIN_check(capture, derived, root, pins)
        write(folder / 'repair.json', {**repair, 'original_inputs': before, 'test_pins': pins,
              'mode': mode, 'saved_input_hashes': {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}})
        write(folder / 'result.json', result)
        results.append({'class': number, 'name': CLASSES.get(number, mode), 'mode': mode,
                        'directory': folder.name, 'result': result})
    manifest = {'schema': 'regular-2step-numerical-negative-tests-v1', 'results': results,
                'claim': 'private copied numerical fixtures; no production trust override',
                'baseline_known_completion': load(known / 'chain.json')['completion_sha256'],
                'baseline_fresh_completion': load(fresh / 'chain.json')['completion_sha256']}
    write(out / 'manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = generate(args.root, args.out)
    print(json.dumps(result, sort_keys=True))
    return 0 if all(r['result']['verdict'] == 'REFUSED' for r in result['results']) else 2


if __name__ == '__main__':
    raise SystemExit(main())
