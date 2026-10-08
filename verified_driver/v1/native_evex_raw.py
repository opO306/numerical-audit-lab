"""Independent finite N=1 V1 raw bridge; no producer imports.

The profile argument is an externally authenticated VERIFIED authority record,
never a PASS assertion read from a machine row. This module checks actual ELF
bytes, complete native/CALL/PLT effects, all legacy effects, continuous memory,
the inherited checkpoint/source/process/state boundary and terminal contract.
Only exact historical libc memset spans may change topology. Numerical values
are reconstructed from the new trace; historical N=3 bits are never an oracle.
"""
from collections import Counter
from copy import deepcopy
import copy
import hashlib
import json
from pathlib import Path
import re

from verified_driver.v1.model import content_id, digest_bytes, canonical_bytes, DT
from verified_driver.v1.live_chain.protocol import BarrierEvent
from verified_driver.v1.live_chain.checkpoint import verify_checkpoint
from verified_driver.v1.live_chain import raw as inherited
from runtime_trace.regular_nstep import raw_check as r, machine_check as m
from runtime_trace.regular_2step import structure, checker as body
from runtime_trace.regular_2step.schema import load, canonical
from . import native_evex_checker as native_checker
from . import native_evex_graph_checker as native_graph


CALLER_SHA = 'a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc'
CPUID_CODE = '534989d089f889f10fa241890041895804418948084189500c5bc3'
PROFILE_KEYS = {'profile_id', 'libc_sha256', 'libc_build_id', 'entry_elf_pc',
                'caller_module_sha256', 'caller_build_id', 'source_sha256',
                'library_path', 'caller_path'}
OLD_MEMSET = (
    (0x189780, 'f30f1efa'), (0x189784, 'c5f96ec6'), (0x189788, '4889f8'),
    (0x18978B, '4883fa20'), (0x18978F, '0f82cb000000'),
    (0x189860, 'c4e27978c0'), (0x189865, '83fa10'), (0x189868, '7d16'),
    (0x189880, 'c5fa7f07'), (0x189884, 'c5fa7f4417f0'), (0x18988A, 'c3'),
)


def _control_witness(witness):
    keys = {'max_basic_leaf', 'leaf', 'subleaf', 'eax', 'ebx', 'ecx', 'edx', 'acquisition_code_hex'}
    r.require(type(witness) is dict and set(witness) == keys, 'raw CPUID witness exact keys')
    for name in keys - {'acquisition_code_hex'}:
        native_checker._uint(witness[name], 32, 'CPUID ' + name)
    r.require(witness['max_basic_leaf'] >= 7 and witness['leaf'] == 7 and witness['subleaf'] == 0 and
              witness['acquisition_code_hex'] == CPUID_CODE, 'raw CPUID supported leaf/code')
    bits = {8: 'bmi2', 16: 'avx512f', 30: 'avx512bw', 31: 'avx512vl'}
    r.require(all(witness['ebx'] & (1 << bit) for bit in bits), 'raw CPUID required native features')
    r.require(not witness['ecx'] & (1 << 7) and not witness['edx'] & (1 << 20), 'raw CPUID CET absence required')
    return sorted(bits.values())


def _profile(profile, root):
    r.require(type(profile) is dict and set(profile) == PROFILE_KEYS, 'finite externally verified profile keys')
    r.require(type(profile['profile_id']) is str and profile['profile_id'], 'externally verified profile identifier')
    for name in ('libc_sha256', 'caller_module_sha256', 'source_sha256'):
        native_checker._hex(profile[name], 32, 'profile ' + name)
    r.require(profile['caller_module_sha256'] == CALLER_SHA and type(profile['entry_elf_pc']) is int and
              profile['entry_elf_pc'] == 0x1996C0, 'finite Gala source and native entry')
    paths = {}
    for prefix, path_field, hash_field in [('libc', 'library_path', 'libc_sha256'),
                                          ('caller', 'caller_path', 'caller_module_sha256')]:
        r.require(type(profile[path_field]) is str and profile[path_field], 'bound profile file path')
        path = Path(profile[path_field])
        path = path if path.is_absolute() else Path(root) / path
        raw = path.read_bytes()
        r.require(digest_bytes(raw) == profile[hash_field], 'actual profile ELF SHA ' + prefix)
        _, build_id = native_checker._elf(raw)
        r.require(build_id == profile[prefix + '_build_id'], 'actual profile ELF Build ID ' + prefix)
        paths[prefix] = path
    return paths


def _effects(row, sidecar):
    native_checker._effect_records(sidecar['reads'], False)
    native_checker._effect_records(sidecar['writes'], True)
    reads = row['pre_memory_observations']
    r.require(type(reads) is list and native_checker._typed_equal(
        [{key: record[key] for key in ('address', 'size', 'bytes_hex')} for record in reads], sidecar['reads']),
        'caller full/raw read binding')
    writes = m.normalized(row)['possible_memory_writes']
    expected = [{'address': record['address'], 'size': record['size'],
                 'after_hex': int(record['after_bits'], 16).to_bytes(record['size'], 'little').hex()} for record in writes]
    r.require(native_checker._typed_equal(expected, sidecar['writes']), 'caller full/raw activated writes binding')


def _caller_pair(rows, start, profile, libc_base):
    r.require(start >= 2 and start + 13 <= len(rows), 'native actual CALL/PLT coverage')
    call, plt, entry = rows[start - 2:start + 1]
    r.require(call['module_sha256'] == plt['module_sha256'] == CALLER_SHA == profile['caller_module_sha256'] and
              call['elf_address'] == 0x35689 and call['bytes'] == 'e8c20cfdff' and
              plt['elf_address'] == 0x6350 and plt['bytes'] == 'ff253aae0300', 'finite actual Gala CALL/PLT code')
    r.require(call['opcode'] == 'call' and plt['opcode'] == 'jmp' and call['kind'] == plt['kind'] == 'CONTROL',
              'actual CALL/PLT opcode and control roles')
    r.require(call['seq'] + 1 == plt['seq'] and plt['seq'] + 1 == entry['seq'] and
              call['ptid'] == plt['ptid'] == entry['ptid'] and call['pid'] == plt['pid'] == entry['pid'],
              'actual CALL/PLT/native process/thread/order')
    base = call['module_load_base']
    r.require(type(base) is int and base == plt['module_load_base'], 'actual Gala load bias')
    full = []
    for row in (call, plt):
        sidecar = row.get('native_evex_caller')
        r.require(type(sidecar) is dict and set(sidecar) == {'before', 'after', 'reads', 'writes'}, 'full CALL/PLT sidecar required')
        native_checker._context(sidecar['before'])
        native_checker._context(sidecar['after'])
        native_graph._projection(row['pre'], sidecar['before'])
        native_graph._projection(row['post'], sidecar['after'])
        r.require(r._pc(row) == (sidecar['before']['registers']['rip'], sidecar['after']['registers']['rip']),
                  'actual CALL/PLT full/projected PCs')
        r.require(sidecar['before']['registers']['eflags'] & (1 << 16) == 0, 'CALL/PLT RF outside supported domain')
        _effects(row, sidecar)
        full.append(sidecar)
    before = full[0]['before']
    regs = before['registers']
    r.require(regs['rip'] == base + 0x35689 and regs['rdx'] == 16 and regs['rsi'] & 255 == 0 and
              regs['rdi'] & 0xFFF <= 0xFE0, 'actual CALL sixteen zero-fill input contract')
    native_checker._address(regs['rdi'], 16)
    r.require(regs['rsp'] >= 8 and native_checker._canonical(regs['rsp'] - 8), 'CALL stack underflow/noncanonical')
    expected_call = deepcopy(before)
    ret = base + 0x3568E
    native_checker._uint(ret, 64, 'actual CALL return')
    target = base + 0x35689 + 5 + int.from_bytes(bytes.fromhex(call['bytes'])[1:], 'little', signed=True)
    r.require(target == base + 0x6350, 'independently decoded CALL→PLT target')
    expected_call['registers'].update(rip=target, rsp=regs['rsp'] - 8)
    r.require(full[0]['after'] == expected_call and full[0]['reads'] == [] and full[0]['writes'] == [
        {'address': regs['rsp'] - 8, 'size': 8, 'after_hex': ret.to_bytes(8, 'little').hex()}], 'complete derived CALL effects')
    r.require(full[1]['before'] == expected_call, 'full CALL→PLT seam')
    got = base + 0x6350 + 6 + int.from_bytes(bytes.fromhex(plt['bytes'])[2:], 'little', signed=True)
    r.require(got == base + 0x41190 and full[1]['reads'] == [
        {'address': got, 'size': 8, 'bytes_hex': (libc_base + 0x1996C0).to_bytes(8, 'little').hex()}] and
        full[1]['writes'] == [], 'independently decoded PLT/GOT target read')
    expected_entry = deepcopy(expected_call)
    expected_entry['registers']['rip'] = libc_base + 0x1996C0
    r.require(full[1]['after'] == expected_entry and entry['native_evex']['before'] == expected_entry,
              'full PLT/GOT→native entry seam')
    r.require(rows[start + 12]['native_evex']['after']['registers']['rip'] == ret and
              rows[start + 12]['native_evex']['after']['registers']['rsp'] == regs['rsp'], 'native return to actual CALL seam')
    return {'caller_load_base': base, 'caller_return_pc': ret, 'destination': regs['rdi']}


def _native_spans(capture, rows, regions, profile, paths):
    _control_witness(capture['native_evex_control_witness'])
    native, spans, receipts, callers = {}, [], [], set()
    allowed_indices = {i for region in regions for i in range(region['start_seq'], region['end_seq'])}
    index = 0
    while index < len(rows):
        row = rows[index]
        if row['module_sha256'] != profile['libc_sha256'] or row['elf_address'] != 0x1996C0:
            index += 1
            continue
        r.require(set(range(index, index + 13)) <= allowed_indices and any(
            region['start_seq'] <= index and index + 13 <= region['end_seq'] for region in regions), 'native span must remain inside body region')
        block = rows[index:index + 13]
        r.require(len(block) == 13, 'complete native thirteen rows')
        base = row['module_load_base']
        caller = _caller_pair(rows, index, profile, base)
        containing = [region for region in regions if region['start_seq'] <= index and index + 13 <= region['end_seq']]
        r.require(len(containing) == 1 and caller['destination'] == containing[0]['pointers']['gradient'],
                  'actual native destination must be the fixed gradient component')
        domain = {'provenance_kind': 'ACTUAL_GALA_CALL', 'source_sha256': profile['source_sha256'],
            'caller_module_sha256': CALLER_SHA, 'caller_elf_pc': 0x35689,
            'caller_instruction_bytes': 'e8c20cfdff', 'caller_return_pc': caller['caller_return_pc'],
            'caller_load_base': caller['caller_load_base'], 'caller_path': profile['caller_path'],
            'caller_build_id': profile['caller_build_id'], 'destination': caller['destination'],
            'length': 16, 'fill': 0, 'libc_sha256': profile['libc_sha256'], 'libc_build_id': profile['libc_build_id']}
        steps = []
        opcodes = ('endbr64', 'vpbroadcastb', 'mov', 'cmp', 'jb', 'and', 'cmp', 'ja', 'mov',
                   'bzhi', 'kmovd', 'vmovdqu8', 'ret')
        kinds = ('ROUTING', 'ZERO_FILL', None, 'ROUTING', 'CONTROL', 'ROUTING', 'ROUTING',
                 'CONTROL', None, 'ROUTING', 'ROUTING', 'MOVE', 'CONTROL')
        for offset, (native_row, (pc, code)) in enumerate(zip(block, native_checker.PATH)):
            r.require(native_row['seq'] == index + offset and native_row['module_sha256'] == profile['libc_sha256'] and
                      native_row['module_load_base'] == base and native_row['elf_address'] == pc and native_row['bytes'] == code,
                      'exact finite native library byte path')
            r.require(native_row['opcode'] == opcodes[offset] and
                      (native_row['kind'] in {'MOVE', 'ROUTING'} if kinds[offset] is None else native_row['kind'] == kinds[offset]),
                      'native actual opcode/kind labels')
            r.require(native_row['pid'] == row['pid'] and native_row['ptid'] == row['ptid'], 'native whole-span process/thread')
            sidecar = native_row.get('native_evex')
            r.require(type(sidecar) is dict and set(sidecar) == {'before', 'after', 'reads', 'writes'}, 'native full sidecar')
            _effects(native_row, sidecar)
            steps.append({'elf_pc': pc, 'instruction_bytes': code, **deepcopy(sidecar)})
            native[native_row['seq']] = sidecar
        document = {'schema': 'native-evex-trace-v1', 'library': {'sha256': profile['libc_sha256'], 'build_id': profile['libc_build_id']},
            'load_base': base, 'domain': domain, 'entry': steps[0]['before'], 'exit': steps[-1]['after'], 'steps': steps}
        result = native_checker.verify_trace(document, paths['libc'], domain)
        span = {'start_seq': index, 'end_seq': index + 13}
        spans.append(span)
        callers.update((index - 2, index - 1))
        receipts.append({**span, 'raw_span_sha256': digest_bytes(canonical_bytes(block)),
                         'instruction_count': result['instruction_count'], 'read_count': result['read_count'], 'write_count': result['write_count']})
        index += 13
    r.require(spans and {row['seq'] for row in rows if row.get('native_evex') is not None} == set(native),
              'native markers exactly cover observed supported paths')
    r.require({row['seq'] for row in rows if row.get('native_evex_caller') is not None} == callers,
              'caller full markers exactly cover observed CALL/PLT pairs')
    # Bind all spans together to the projected rows and raw lane records;
    # authority alone cannot certify full sidecars or unmarked extra paths.
    native_graph._native_spans(rows, regions, spans)
    return native, spans, receipts


def _memory_stream(rows, decoded, native, shadow=None):
    shadow = {} if shadow is None else shadow
    for original in rows:
        row = m.normalized(original)
        sidecar = native.get(row['seq'])
        if sidecar is None:
            r._memory([row], decoded, shadow)
            continue
        _effects(row, sidecar)
        for read in sidecar['reads']:
            for offset, byte in enumerate(bytes.fromhex(read['bytes_hex'])):
                address = read['address'] + offset
                r.require(address not in shadow or shadow[address] == byte, 'native memory read/shadow continuity')
                shadow[address] = byte
        for write in row['possible_memory_writes']:
            before = int(write['before_bits'], 16).to_bytes(write['size'], 'little')
            after = int(write['after_bits'], 16).to_bytes(write['size'], 'little')
            for offset, byte in enumerate(before):
                address = write['address'] + offset
                r.require(address not in shadow or shadow[address] == byte, 'native memory write PRE continuity')
                shadow[address] = after[offset]
    return shadow


def _skeleton(rows, region, modules, libc_sha):
    """Ordered non-libc code/control/storage roles plus positioned helper gaps."""
    filtered, blocks, position, in_helper = [], [], 0, False
    for row in rows:
        if row['module_sha256'] == libc_sha:
            if not in_helper:
                blocks.append(position)
            in_helper = True
        else:
            in_helper = False
            filtered.append(row)
            position += 1
    shape = body.prefix_structure(filtered, region, modules)
    targets = []
    for position, row in enumerate(filtered):
        if row['kind'] != 'CONTROL':
            continue
        pc = r._pc(row)[1]
        matches = [(module['sha256'], pc - module['load_base']) for module in modules.values()
                   if any(segment['flags'] & 1 and module['load_base'] + segment['vaddr'] <= pc <
                          module['load_base'] + segment['vaddr'] + segment['filesz'] for segment in module['segments'])]
        r.require(len(matches) == 1, 'non-libc skeleton actual control target')
        digest, address = matches[0]
        targets.append((position, digest, 'AUTHENTICATED_MEMSET_ENTRY' if digest == libc_sha else address))
    shape['control'] = targets
    arithmetic = [(row['module_sha256'], row['elf_address'], row['bytes'], row['opcode'], row['kind'])
                  for row in filtered if row['kind'] in ('ADD', 'SUB', 'MUL')]
    return {'shape': shape, 'libc_span_positions': blocks, 'numerical_instruction_sequence': arithmetic}


def _topology(capture, rows, regions, root, profile, spans):
    old = load(Path(root) / 'runtime_trace/regular_2step/artifacts/known-03/capture.json')
    oldrows, _ = structure._load_rows(Path(root) / 'runtime_trace/regular_2step/artifacts/known-03/trace.jsonl')
    for fresh, prior in zip(regions, old['regions'][:2]):
        fresh_rows = rows[fresh['start_seq']:fresh['end_seq']]
        prior_rows = oldrows[prior['start_seq']:prior['end_seq']]
        prior_libc = [(row['elf_address'], row['bytes']) for row in prior_rows if row['module_sha256'] == profile['libc_sha256']]
        r.require(tuple(prior_libc) == OLD_MEMSET, 'immutable historical narrow libc path')
        expected = {i for span in spans if fresh['start_seq'] <= span['start_seq'] < fresh['end_seq']
                    for i in range(span['start_seq'], span['end_seq'])}
        r.require({row['seq'] for row in fresh_rows if row['module_sha256'] == profile['libc_sha256']} == expected,
                  'only exact authenticated libc span may change')
        r.require(_skeleton(fresh_rows, fresh, capture['modules'], profile['libc_sha256']) ==
                  _skeleton(prior_rows, prior, old['modules'], profile['libc_sha256']),
                  'ordered non-libc code/control/operand-role topology')
        r.require(set(fresh['pointers']) == {'q', 'full_v', 'latent', 'gradient'} and
                  len(set(fresh['pointers'].values())) == 4, 'fixed four separate binary64 component domains')
        for address in fresh['pointers'].values():
            native_checker._address(address, 16)
        addresses = list(fresh['pointers'].values())
        r.require(all(a + 16 <= b or b + 16 <= a for i, a in enumerate(addresses) for b in addresses[i + 1:]),
                  'component byte domains must be disjoint')
    r.require(regions[0]['pointers'] == regions[1]['pointers'], 'fixed init/step component pointers')
    # Exact new arithmetic and graph provenance are reconstructed here, without
    # comparing the result bits against an execution requesting N=3.
    native_graph.graph(capture, rows, regions, root, spans)


# Original checkpoint/source/process/region/terminal boundaries retained.
def validate_edge(checkpoint,pred,root,profile):
    r.require(all(type(value) is int for value in (pred.requested_steps, pred.generation, pred.step_index)) and
              pred.requested_steps == 1 and pred.generation == 0 and pred.step_index == 0,
              'finite EVEX admission supports only fresh N=1; Task 10 unsupported')
    paths = _profile(profile, root)
    checkpoint=Path(checkpoint); root=Path(root)
    doc=verify_checkpoint(checkpoint); event=BarrierEvent(**doc['event']); metadata=doc['metadata']; capture=metadata['capture']
    r.require(event.completed_step==pred.step_index+1 and event.predecessor_id==pred.content_hash and event.requested_steps==pred.requested_steps,'immediate certified predecessor/step')
    r.require(pred.barrier_kind!='FINAL_TERMINAL','terminal predecessor cannot authorize a body')
    snap=event.checkpoint_state; k=event.completed_step
    r.require(capture['schema']=='gala-live-prefix-v1' and capture['verdict']=='PAUSED','live prefix capture required')
    r.require(capture['wheel_sha256']=='cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0' and capture['machine_mapping_read_by_tracer'] is False,'original wheel/acquisition contract')
    r.require(capture['requested_steps']==event.requested_steps and capture['process_identity']==dict(event.process_identity) and capture['acquisition_id']==event.session_id,'strict live process/session binding')
    inherited._sources(metadata,capture,root)
    if pred.generation:
        r.require(pred.live_session_id==event.session_id and pred.process_identity_digest==content_id(event.process_identity) and pred.source_binding==metadata['source_binding'],'foreign live predecessor/session/source')
    raw=(checkpoint/'trace.jsonl').read_bytes()
    r.require(len(raw)<=536870912,'raw prefix ceiling')
    if pred.generation: r.require(digest_bytes(raw[:pred.trace_prefix_bytes])==pred.trace_prefix_sha256,'certified prefix mutation')
    rows=[]; chain='0'*64
    for line in raw.splitlines():
        row=json.loads(line,object_pairs_hook=body._pairs if hasattr(body,'_pairs') else __import__('runtime_trace.regular_2step.schema',fromlist=['_pairs'])._pairs,
          parse_constant=lambda v: (_ for _ in ()).throw(ValueError('nonfinite raw JSON')))
        chain=hashlib.sha256(bytes.fromhex(chain)+canonical({a:b for a,b in row.items() if a!='chain'})).hexdigest()
        r.require(row['chain']==chain,'raw global chain/order'); rows.append(row)
    r.require(chain==capture['final_chain'] and capture['trace_sha256']==event.trace_prefix_sha256,'prefix acquisition identity')
    r._numeric_types(capture); r._numeric_types(rows)
    r.require(len(rows)==capture['record_count'] and [x['seq'] for x in rows]==list(range(len(rows))),'dense unique prefix sequence')
    histogram=Counter(row.get('opcode') or row['assembly'].split()[0] for row in rows)
    r.require(all(type(v) is int and v>0 for v in capture['opcode_histogram'].values()) and dict(histogram)==capture['opcode_histogram'],'exact prefix opcode histogram')
    r.require(capture['scalar_fp_count']==sum(row.get('kind') in ('ADD','SUB','MUL') for row in rows),'exact prefix scalar operation count')
    r.require(snap['frontier']==len(rows)-1 and snap['body_count']==k,'exact checkpoint frontier/body count')
    regions=capture['regions']; corridors=capture['caller_corridors']
    r.require([x['occurrence'] for x in regions]==['init']+[f'step{i}' for i in range(1,k+1)],'no missing/extra/early next body')
    region=regions[-1]; start=0 if k==1 else pred.verified_frontier+1
    r.require(region['start_seq']==(regions[0]['end_seq'] if k==1 else start),'new body exactly at prior frontier')
    r.require(region['start_state']['q']==list(pred.q_bits) and region['start_state']['full_v']==list(pred.full_v_bits) and region['start_state']['latent']==list(pred.latent_bits),'certified q/full_v/latent exact handoff')
    r.require(region['start_state']['gradient']==list(pred.gradient_bits) and region['dt_bits']==DT,'entry gradient/dt contract')
    if k>1: r.require(region['t_bits']==pred.next_t_bits,'certified next t entry')
    if event.barrier_kind=='NEXT_STEP_ENTRY':
        r.require(capture['terminal_corridor'] is None and len(corridors)==k,'nonterminal corridor count')
        corridor=corridors[-1]; following=json.loads(canonical_bytes(snap['next_entry'])); following['occurrence']=f'step{k+1}'
        r.require('end_seq' not in following and 'end_state' not in following,'no executed successor snapshot')
        r.require(corridor['occurrence']==f'caller{k}-{k+1}' and corridor['start_seq']==region['end_seq'] and corridor['end_seq']==len(rows),'body/caller complete prefix coverage')
        r.require(following['entry_pc']==snap['paused_pc']==r._pc(rows[-1])[1] and inherited._context(following['context'])==inherited._context(rows[-1]['post']),'actual stopped entry PC/context')
        for name in ('q','full_v','latent','gradient'): r.require(list(snap[name])==following['start_state'][name],'checkpoint entry component snapshot')
        r.require(snap['t_bits']==following['t_bits'] and snap['dt_bits']==following['dt_bits'],'checkpoint represented t/dt')
        spans=([regions[0]] if k==1 else [])+[region,corridor]
    else:
        terminal=capture['terminal_corridor']
        r.require(snap['next_entry'] is None and snap['t_bits'] is None and len(corridors)==k-1,'terminal forbids successor data')
        r.require(terminal is not None and terminal['occurrence']==f'terminal{k}' and terminal['start_seq']==region['end_seq'] and terminal['end_seq']==len(rows),'complete native terminal corridor')
        r.require(snap['paused_pc']==r._pc(rows[-1])[1],'actual terminal paused frontier')
        for name in ('q','full_v','latent'): r.require(list(snap[name])==region['end_state'][name],'terminal logical lanes')
        r.require(list(snap['gradient'])==region['start_state']['gradient'] and snap['dt_bits']==region['dt_bits'],'terminal retains last observed entry gradient/dt rule')
        spans=([regions[0]] if k==1 else [])+[region,terminal]
    r.require(spans[0]['start_seq']==start and spans[-1]['end_seq']==len(rows),'new edge coverage')
    for span in spans:
        r.require(span['start_seq']<span['end_seq'] and all(x['occurrence']==span['occurrence'] for x in rows[span['start_seq']:span['end_seq']]),'new edge occurrence/order')
    identity=capture['process_identity']; pid=identity['pid']; owner=regions[0]['ptid']
    r.require(set(identity)=={'pid','linux_boot_id','proc_stat_start_time_ticks'} and type(pid) is int and pid>0 and identity['proc_stat_start_time_ticks']>0,'structured live process birth')
    r.require(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',identity['linux_boot_id']) is not None and owner[0]==pid and owner[1]>0 and owner[2]==0,'live birth/thread identity')
    new=rows[start:]
    for row in new:
        r.require(row['pid']==pid and row['ptid']==owner and row.get('thread_ptid',owner)==owner,'cross-process/thread row splice')
        for c in (row['pre'],row['post']):
            r.require(c['mxcsr']&((3<<13)|(1<<15)|(1<<6))==0 and c['mxcsr']&0x1f80==0x1f80,'supported rounding environment')
    for index in range(max(1,start),len(rows)):
        if k==1 and index==regions[1]['start_seq']: continue # retained sole inherited gap
        before,after=rows[index-1],rows[index]
        r.require(r._pc(before)[1]==r._pc(after)[0] and inherited._context(before['post'])==inherited._context(after['pre']),'complete PC/register seam')
    for current in ([regions[0],region] if k==1 else [region]):
        r.require(current['entry_pc']==r._pc(rows[current['start_seq']])[0] and current['return_pc']==r._pc(rows[current['end_seq']-1])[1] and current['ptid']==owner and current['scheduler_locking']=='Mode for locking scheduler during execution is "on".','all-stop actual body entry/return')
    decoded=r._decoded(new,root,capture['modules'])
    native, evex_spans, evex_receipts = _native_spans(capture, rows, regions[:2], profile, paths)
    native_decode={row['seq']:m.effect_assembly(decoded[row['module_sha256'],row['elf_address']][1]) for row in new}
    gap=regions[1]['start_seq']
    _memory_stream(new[:gap],native_decode,native,{})
    _memory_stream(new[gap:],native_decode,native,{})
    bases={module['sha256']:module['load_base'] for module in capture['modules'].values()}
    legacy=[m.normalized(row) for row in new if row['seq'] not in native]
    m.registers(legacy,native_decode); m.controls(legacy,native_decode,bases); m.writes(legacy,native_decode)
    structure._check_observations([row for current in regions[:2] for row in rows[current['start_seq']:current['end_seq']]])
    _topology(capture,rows,regions[:2],root,profile,evex_spans)
    allowed=r._closed_caller_sites(root)
    if event.barrier_kind=='NEXT_STEP_ENTRY':
        joined=r._caller_join(region,following,corridor,rows[corridor['start_seq']:],decoded,capture['modules'],allowed)
        stores=r._output_stores(region,rows[corridor['start_seq']:],decoded,event.requested_steps)
        if k>1: r.require(corridor['argument_sources']['t']['source_memory_address']==corridors[0]['argument_sources']['t']['source_memory_address']+8*(k-1),'contiguous step schedule provenance')
        native_report={'kind':event.barrier_kind,'join':joined,'output_stores':stores,'next_body_executed':False}
    else:
        native_report={'kind':event.barrier_kind,'terminal_output_stores':r._terminal(capture,rows,decoded,allowed),'next_body_executed':False}
    native_report.update(profile_id=profile['profile_id'],evex_spans=evex_receipts,step_index=k,last_verified_trace_seq=len(rows)-1,new_start_seq=start,new_record_count=len(new))
    identity=(checkpoint/'CHECKPOINT').read_text().strip()
    return doc,event,capture,rows,native_report,identity
