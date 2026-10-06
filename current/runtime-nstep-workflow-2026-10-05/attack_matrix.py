"""Public-checker attacks with complete outer digest repairs, kept as separate evidence."""
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime_trace.regular_nstep import checker
from runtime_trace.regular_nstep.resources import reserve_writer
from runtime_trace.regular_2step.schema import canonical, digest, load, sha

BASE = ROOT / 'runtime_trace/regular_nstep/artifacts/connected10-final2'
OUT = ROOT / 'runtime_trace/regular_nstep/artifacts/attack-matrix-01'
OUT.mkdir(exist_ok=False)


def put(path, value):
    data = canonical(value) + b'\n'
    reserve_writer(len(data))
    path.write_bytes(data)


def copy_inputs(case):
    size = sum(p.stat().st_size for folder in ('capture', 'derived') for p in (BASE / folder).rglob('*') if p.is_file())
    reserve_writer(size)
    for folder in ('capture', 'derived'):
        shutil.copytree(BASE / folder, case / folder)


def repin_derived(case):
    complete = load(case / 'derived/completion.json')
    complete['ordered_component_hashes'] = [{'path': name, 'sha256': sha(case / 'derived' / name)}
        for name in ('blocks.json', 'native_report.json')]
    complete['completion_sha256'] = digest({k: v for k, v in complete.items() if k != 'completion_sha256'})
    put(case / 'derived/completion.json', complete)


def resign_raw(case, cap, rows):
    # Reindex every span, occurrence and local chain; hashes cannot be the
    # semantic rejection reason. Keep the original caller/body role identities.
    local_chains, counts, global_chain = {}, Counter(), '0' * 64
    for i, row in enumerate(rows):
        row['seq'] = i
        if 'sequence' in row:
            occurrence = row['occurrence']
            row['sequence'] = counts[occurrence]
            counts[occurrence] += 1
            row['previous_chain'] = local_chains.get(occurrence, '0' * 64)
            unsigned = {k: v for k, v in row.items() if k not in ('chain', 'record_chain', 'seq', 'pid', 'ptid', 'occurrence')}
            local_chains[occurrence] = hashlib.sha256(canonical(unsigned)).hexdigest()
            row['record_chain'] = local_chains[occurrence]
        global_chain = hashlib.sha256(bytes.fromhex(global_chain) + canonical({k: v for k, v in row.items() if k != 'chain'})).hexdigest()
        row['chain'] = global_chain
    reserve_writer(sum(len(canonical(r)) + 1 for r in rows))
    with (case / 'capture/trace.jsonl').open('wb') as stream:
        for row in rows:
            stream.write(canonical(row) + b'\n')
    cap['record_count'], cap['final_chain'] = len(rows), global_chain
    cap['trace_sha256'] = sha(case / 'capture/trace.jsonl')
    cap['scalar_fp_count'] = sum(r.get('kind') in ('ADD', 'SUB', 'MUL') for r in rows)
    cap['opcode_histogram'] = dict(Counter(r['opcode'] if 'opcode' in r else r['assembly'].split()[0] for r in rows))
    spans = cap['regions'] + cap['caller_corridors'] + [cap['terminal_corridor']]
    for span in spans:
        positions = [i for i, row in enumerate(rows) if row['occurrence'] == span['occurrence']]
        span['start_seq'], span['end_seq'] = min(positions), max(positions) + 1
        if 'local_final_chain' in span:
            span['local_final_chain'] = local_chains[span['occurrence']]
        if 'local_record_count' in span:
            span['local_record_count'] = len(positions)
        if 'rows' in span:
            span['rows'] = len(positions)
    pins = load(case / 'capture/source_pinset.json')
    cap['source_pinset_sha256'] = sha(case / 'capture/source_pinset.json')
    cap['acquisition_id'] = hashlib.sha256(json.dumps({'process': cap['process_identity'],
        'trace': cap['trace_sha256'], 'source': pins, 'requested_steps': cap['requested_steps']}, sort_keys=True).encode()).hexdigest()
    put(case / 'capture/capture.json', cap)
    put(case / 'capture/capture.pending.json', cap)
    seal = load(case / 'capture/acquisition_seal.json')
    seal['acquisition_id'] = cap['acquisition_id']
    seal['files'] = {name: sha(case / 'capture' / name) for name in seal['files']}
    put(case / 'capture/acquisition_seal.json', seal)


names = ('missing-dense', 'duplicate-dense', 'reorder-dense', 'wrong-result', 'body-write-omission',
    'body-read-omission', 'body-callee-saved', 'terminal-save-pointer', 'cross-process', 'all-stop-off',
    'wrong-gradient', 'unsupported-opcode', 'reset-error', 'wrong-error-link', 'other-execution-id',
    'IR-order', 'false-completion', 'missing-final-block', 'missing-normal-exit', 'hash-control', 'trust-control')
results = []
for name in names:
    began = time.perf_counter()
    case = OUT / name
    copy_inputs(case)
    cap = load(case / 'capture/capture.json')
    raw_names = set(names[:12]) | {'missing-normal-exit', 'trust-control'}
    if name in raw_names:
        rows = [json.loads(line) for line in (case / 'capture/trace.jsonl').read_bytes().splitlines()]
        if name == 'missing-dense':
            del rows[500]
        elif name == 'duplicate-dense':
            rows.insert(500, copy.deepcopy(rows[500]))
        elif name == 'reorder-dense':
            rows[500], rows[501] = rows[501], rows[500]
        elif name == 'wrong-result':
            r = next(r for r in rows if r['occurrence'] == 'step2' and r.get('kind') == 'MUL')
            r['result_bits'] = '0x3ff0000000000000'
        elif name in ('body-write-omission', 'body-read-omission'):
            key = 'possible_memory_writes' if 'write' in name else 'pre_memory_observations'
            next(r for r in rows if r['occurrence'] == 'step2' and r[key])[key] = []
        elif name == 'body-callee-saved':
            r = next(r for r in rows if r['occurrence'] == 'step2' and r.get('kind') == 'MUL')
            changed = f"0x{int(r['post']['gpr']['r13'], 16) + 1:016x}"
            r['post']['gpr']['r13'] = changed
            for s in rows[r['seq'] + 1:]:
                previous = s['pre']['gpr']['r13']
                s['pre']['gpr']['r13'] = changed
                if previous != s['post']['gpr']['r13']:
                    break
                s['post']['gpr']['r13'] = changed
        elif name == 'terminal-save-pointer':
            load_row = next(r for r in rows if r['occurrence'].startswith('terminal') and
                '0x108(%rsp),%rdx' in r.get('assembly', ''))
            pointer = int(load_row['post']['gpr']['rdx'], 16)
            slot = load_row['pre_memory_observations'][0]['address']
            targets = [s['destination_address'] for s in load(case / 'derived/native_report.json')['terminal_output_stores']]
            for r in rows[load_row['seq']:]:
                for state in ('pre', 'post'):
                    if int(r[state]['gpr']['rdx'], 16) == pointer:
                        r[state]['gpr']['rdx'] = f'0x{pointer - 8:016x}'
                for o in r['pre_memory_observations']:
                    if o['address'] == slot:
                        o['bytes_hex'] = (int.from_bytes(bytes.fromhex(o['bytes_hex']), 'little') - 8).to_bytes(o['size'], 'little').hex()
                for w in r['possible_memory_writes']:
                    if w['address'] in targets:
                        w['address'] -= 8
                    if w['address'] == slot:
                        for key in ('before_bits', 'after_bits'):
                            w[key] = f"0x{int(w[key], 16) - 8:016x}"
        elif name == 'cross-process':
            rows[500]['pid'] += 1
        elif name == 'all-stop-off':
            cap['regions'][2]['scheduler_locking'] = 'off'
        elif name == 'wrong-gradient':
            cap['regions'][2]['start_state']['gradient'][0] = '0x3ff0000000000000'
        elif name == 'unsupported-opcode':
            rows[500]['assembly'] = 'divsd %xmm0,%xmm1'
        elif name == 'missing-normal-exit':
            cap['gdb_exit_event']['observed'] = False
        else:
            put(case / 'capture/source_pinset.json', {})
        resign_raw(case, cap, rows)
        del rows
    elif name == 'hash-control':
        (case / 'derived/blocks.json').write_bytes(b'[]\n')
    else:
        blocks = load(case / 'derived/blocks.json')
        if name == 'reset-error':
            blocks[2]['boundary']['carry'][2]['form']['box'] = '0x0.0p+0'
        elif name == 'wrong-error-link':
            blocks[2]['boundary']['carry'][0]['audited_endpoint']['form_source_state_id'] = blocks[0]['endpoint'][0]['state_id']
        elif name == 'other-execution-id':
            blocks[2]['boundary']['carry'][0]['from_acquisition_id'] = '1' * 64
        elif name == 'IR-order':
            ops = blocks[2]['ir']['operations']
            ops[0], ops[1] = ops[1], ops[0]
        elif name == 'missing-final-block':
            blocks.pop()
        else:
            complete = load(case / 'derived/completion.json')
            complete.update(requested_steps=100, checked_steps=100, requested_complete=True)
            put(case / 'derived/completion.json', complete)
        put(case / 'derived/blocks.json', blocks)
        repin_derived(case)
    report = checker.check(case / 'capture', case / 'derived', ROOT)
    if report['verdict'] != 'REFUSED' or report['requested_complete'] is not False:
        raise ValueError('attack wrongly accepted: ' + name)
    result = {'attack': name, 'outer_hashes_repaired': name != 'hash-control',
              'category': 'HASH_CONTROL' if name == 'hash-control' else 'TRUST_CONTROL' if name == 'trust-control' else 'SEMANTIC',
              'wall_seconds': time.perf_counter() - began, 'report': report}
    put(case / 'attack_result.json', result)
    results.append(result)
    print(json.dumps({'attack': name, 'verdict': report['verdict'], 'reason': report['reason']}), flush=True)
put(OUT / 'matrix_report.json', {'verdict': 'ATTACK_MATRIX_PASS', 'attacks': results,
    'semantic_count': sum(r['category'] == 'SEMANTIC' for r in results), 'control_count': 2})
