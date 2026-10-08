"""Independent native raw bridge tests; fixtures are hand-authored TEST_ONLY."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_v1_evex_graph_checker import graph_fixture, project
from verified_driver.v1 import native_evex_raw as raw


CALLER_SHA = 'a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc'
CALLER_BASE = 0x60000000
LIBC_BASE = 0x70000000


def witness():
    return {'max_basic_leaf': 7, 'leaf': 7, 'subleaf': 0, 'eax': 0,
            'ebx': (1 << 8) | (1 << 16) | (1 << 30) | (1 << 31),
            'ecx': 0, 'edx': 0,
            'acquisition_code_hex': '534989d089f889f10fa241890041895804418948084189500c5bc3'}


def native_fixture(tmp_path, monkeypatch):
    capture, rows, regions, _ = graph_fixture(tmp_path, monkeypatch)
    initial = copy.deepcopy(rows[0]['native_evex']['before'])
    return_pc = CALLER_BASE + 0x3568E
    initial['registers'].update(rip=CALLER_BASE + 0x35689, rsp=0x30000008)
    after_call = copy.deepcopy(initial)
    after_call['registers'].update(rip=CALLER_BASE + 0x6350, rsp=0x30000000)
    after_plt = copy.deepcopy(after_call)
    after_plt['registers']['rip'] = LIBC_BASE + 0x1996C0
    call_side = {'before': initial, 'after': after_call, 'reads': [], 'writes': [
        {'address': 0x30000000, 'size': 8, 'after_hex': return_pc.to_bytes(8, 'little').hex()}]}
    plt_side = {'before': after_call, 'after': after_plt, 'reads': [
        {'address': CALLER_BASE + 0x41190, 'size': 8, 'bytes_hex': (LIBC_BASE + 0x1996C0).to_bytes(8, 'little').hex()}], 'writes': []}
    callers = []
    for seq, pc, code, opcode, side in [(0, 0x35689, 'e8c20cfdff', 'call', call_side),
                                       (1, 0x6350, 'ff253aae0300', 'jmp', plt_side)]:
        callers.append({'seq': seq, 'occurrence': 'init', 'module_sha256': CALLER_SHA,
            'module_load_base': CALLER_BASE, 'module_path': 'gala', 'elf_address': pc, 'bytes': code,
            'runtime_pc': side['before']['registers']['rip'], 'post_pc': side['after']['registers']['rip'],
            'ptid': [1, 1, 0], 'pid': 1, 'kind': 'CONTROL', 'opcode': opcode,
            'operands': [],
            'pre': project(side['before']), 'post': project(side['after']), 'native_evex_caller': copy.deepcopy(side),
            'possible_memory_writes': [{**w, 'before_hex': '00' * 8, 'value_changed': True} for w in side['writes']],
            'pre_memory_observations': copy.deepcopy(side['reads'])})
    for row in rows:
        row['seq'] += 2
        row['pid'] = 1
        row['occurrence'] = 'init'
    rows[-1]['native_evex']['reads'][0]['bytes_hex'] = return_pc.to_bytes(8, 'little').hex()
    rows[-1]['pre_memory_observations'][0]['bytes_hex'] = return_pc.to_bytes(8, 'little').hex()
    rows[-1]['native_evex']['after']['registers']['rip'] = return_pc
    rows[-1]['post'] = project(rows[-1]['native_evex']['after'])
    rows[-1]['post_pc'] = return_pc
    rows[-1]['operands'][0]['raw_bits'] = f'0x{return_pc:016x}'
    rows = callers + rows
    profile = {'profile_id': 'UNIT_ONLY', 'libc_sha256': rows[2]['module_sha256'],
        'libc_build_id': '12345678', 'entry_elf_pc': 0x1996C0,
        'caller_module_sha256': CALLER_SHA, 'caller_build_id': 'deadbeef',
        'source_sha256': '01' * 32, 'library_path': str(tmp_path / 'synthetic-libc.so'),
        'caller_path': str(tmp_path / 'synthetic-gala.so')}
    capture['modules']['gala'] = {'sha256': CALLER_SHA, 'load_base': CALLER_BASE, 'segments': []}
    capture['native_evex_control_witness'] = witness()
    return capture, rows, profile


def test_hand_call_push_and_got_branch_derive(tmp_path, monkeypatch):
    capture, rows, profile = native_fixture(tmp_path, monkeypatch)
    raw._caller_pair(rows, 2, profile, LIBC_BASE)
    assert rows[0]['native_evex_caller']['writes'][0]['after_hex'] == '8e56036000000000'


@pytest.mark.parametrize('attack', ['caller_pc', 'caller_code', 'module', 'stackwrite', 'deletedstackwrite',
    'outsidewrite', 'got', 'gotread', 'plt_code', 'preserved_gpr', 'preserved_vector', 'fpu',
    'missing_full', 'seam', 'thread', 'mask', 'length', 'fill'])
def test_caller_full_proof_mutations_refuse(tmp_path, monkeypatch, attack):
    capture, rows, profile = native_fixture(tmp_path, monkeypatch)
    if attack == 'caller_pc': rows[0]['elf_address'] += 1
    elif attack == 'caller_code': rows[0]['bytes'] = 'e8c10cfdff'
    elif attack == 'module': rows[0]['module_sha256'] = '03' * 32
    elif attack == 'stackwrite': rows[0]['native_evex_caller']['writes'][0]['after_hex'] = '00' * 8
    elif attack == 'deletedstackwrite': rows[0]['possible_memory_writes'] = []
    elif attack == 'outsidewrite': rows[0]['possible_memory_writes'].append({'address': 0x30000008, 'size': 1, 'before_hex': '00', 'after_hex': '00', 'value_changed': False})
    elif attack == 'got': rows[1]['native_evex_caller']['reads'][0]['address'] += 8
    elif attack == 'gotread': rows[1]['native_evex_caller']['reads'][0]['bytes_hex'] = '00' * 8
    elif attack == 'plt_code': rows[1]['bytes'] = 'ff253bae0300'
    elif attack == 'preserved_gpr': rows[0]['native_evex_caller']['after']['registers']['r15'] ^= 1
    elif attack == 'preserved_vector': rows[0]['native_evex_caller']['after']['vectors']['zmm31'] = '00' * 64
    elif attack == 'fpu': rows[0]['native_evex_caller']['after']['fpu']['ftag'] = 0
    elif attack == 'missing_full': rows[0].pop('native_evex_caller')
    elif attack == 'seam': rows[1]['native_evex_caller']['before']['registers']['rax'] ^= 1
    elif attack == 'thread': rows[1]['ptid'] = [1, 2, 0]
    elif attack == 'mask': rows[2]['native_evex']['before']['registers']['rdi'] |= 0xFF0
    elif attack == 'length': rows[0]['native_evex_caller']['before']['registers']['rdx'] = 15
    elif attack == 'fill': rows[0]['native_evex_caller']['before']['registers']['rsi'] = 1
    with pytest.raises(ValueError): raw._caller_pair(rows, 2, profile, LIBC_BASE)


def test_control_witness_bits_are_derived():
    assert raw._control_witness(witness()) == ['avx512bw', 'avx512f', 'avx512vl', 'bmi2']


@pytest.mark.parametrize('attack', ['no_leaf', 'wrong_leaf', 'wrong_subleaf', 'feature', 'ibt', 'shstk', 'bool', 'code', 'extra'])
def test_control_witness_mutations_refuse(attack):
    w = witness()
    if attack == 'no_leaf': w['max_basic_leaf'] = 6
    elif attack == 'wrong_leaf': w['leaf'] = 6
    elif attack == 'wrong_subleaf': w['subleaf'] = 1
    elif attack == 'feature': w['ebx'] &= ~(1 << 30)
    elif attack == 'ibt': w['edx'] |= 1 << 20
    elif attack == 'shstk': w['ecx'] |= 1 << 7
    elif attack == 'bool': w['edx'] = False
    elif attack == 'code': w['acquisition_code_hex'] = '00'
    elif attack == 'extra': w['PASS'] = True
    with pytest.raises(ValueError): raw._control_witness(w)


def test_native_and_legacy_memory_share_one_shadow(tmp_path, monkeypatch):
    capture, rows, profile = native_fixture(tmp_path, monkeypatch)
    native = {row['seq']: row['native_evex'] for row in rows[2:]}
    observed_shadows = []
    def legacy_memory(rs, decoded, shadow):
        observed_shadows.append(id(shadow))
        for row in rs:
            for w in row['possible_memory_writes']:
                for i, b in enumerate(bytes.fromhex(w['after_hex'])): shadow[w['address'] + i] = b
    monkeypatch.setattr(raw.r, '_memory', legacy_memory)
    shadow = raw._memory_stream(rows, {}, native, {})
    assert len(set(observed_shadows)) == 1
    assert bytes(shadow[0x30000000 + i] for i in range(8)) == bytes.fromhex('8e56036000000000')
    rows[-1]['native_evex']['reads'][0]['bytes_hex'] = '00' * 8
    with pytest.raises(ValueError): raw._memory_stream(rows, {}, native, {})


def test_profile_admission_is_finite_n1_before_checkpoint_access(tmp_path):
    from types import SimpleNamespace
    pred = SimpleNamespace(requested_steps=2, generation=0, step_index=0)
    with pytest.raises(ValueError, match='N=1'):
        raw.validate_edge(tmp_path / 'absent', pred, tmp_path, {})


def test_full_native_span_replays_real_literal_elf_and_reports_digest(tmp_path, monkeypatch):
    capture, rows, profile = native_fixture(tmp_path, monkeypatch)
    native, spans, receipts = raw._native_spans(capture, rows, [{'start_seq': 0, 'end_seq': 15, 'pointers': {'gradient': 0x20002040}}],
        profile, {'libc': tmp_path / 'synthetic-libc.so'})
    assert spans == [{'start_seq': 2, 'end_seq': 15}]
    assert set(native) == set(range(2, 15))
    assert receipts == [{'start_seq': 2, 'end_seq': 15,
        'raw_span_sha256': raw.digest_bytes(raw.canonical_bytes(rows[2:15])),
        'instruction_count': 13, 'read_count': 1, 'write_count': 16}]


def test_all_spans_are_verified_together_without_reset_or_omission(tmp_path, monkeypatch):
    capture, rows, profile = native_fixture(tmp_path, monkeypatch)
    second = copy.deepcopy(rows)
    for row in second: row['seq'] += 15
    rows.extend(second)
    native, spans, receipts = raw._native_spans(capture, rows,
        [{'start_seq': 0, 'end_seq': 15, 'pointers': {'gradient': 0x20002040}}, {'start_seq': 15, 'end_seq': 30, 'pointers': {'gradient': 0x20002040}}],
        profile, {'libc': tmp_path / 'synthetic-libc.so'})
    assert spans == [{'start_seq': 2, 'end_seq': 15}, {'start_seq': 17, 'end_seq': 30}]
    assert len(native) == 26 and len(receipts) == 2


@pytest.mark.parametrize('attack', ['read', 'write', 'samevalue', 'entry', 'unknown_marker', 'missing_row', 'outside_body', 'libc_byte',
                                  'opcode', 'arithmetic_kind', 'pid'])
def test_full_span_effect_or_coverage_mutations_refuse(tmp_path, monkeypatch, attack):
    capture, rows, profile = native_fixture(tmp_path, monkeypatch)
    regions = [{'start_seq': 0, 'end_seq': 15, 'pointers': {'gradient': 0x20002040}}]
    if attack == 'read': rows[-1]['pre_memory_observations'] = []
    elif attack == 'write': rows[-2]['possible_memory_writes'].pop()
    elif attack == 'samevalue': rows[-2]['possible_memory_writes'][0]['value_changed'] = True
    elif attack == 'entry': rows[2]['native_evex']['before']['registers']['rip'] += 1
    elif attack == 'unknown_marker': rows[0]['native_evex'] = copy.deepcopy(rows[2]['native_evex'])
    elif attack == 'missing_row': rows.pop(8)
    elif attack == 'outside_body': regions[0]['end_seq'] = 14
    elif attack == 'libc_byte':
        p = tmp_path / 'synthetic-libc.so'
        b = bytearray(p.read_bytes()); b[0x16C0] ^= 1; p.write_bytes(b)
    elif attack == 'opcode': rows[11]['opcode'] = 'nop'
    elif attack == 'arithmetic_kind': rows[4]['kind'] = 'ADD'
    elif attack == 'pid': rows[10]['pid'] = 2
    with pytest.raises(ValueError): raw._native_spans(capture, rows, regions, profile, {'libc': tmp_path / 'synthetic-libc.so'})


def sealed_boundary_fixture(tmp_path, monkeypatch):
    """Exercise real checkpoint/hash/source/process gates around literal effects.

    The decoder and historical topology seam are isolated in this unit fixture;
    production uses the packaged ELF decoder and immutable historical topology.
    All actual caller/legacy/native register, control, write, memory and sidecar
    checks execute here. This is not a captured Gala execution.
    """
    from collections import Counter
    from verified_driver.v1.live_chain.checkpoint import chain_hash
    repo = Path(__file__).resolve().parents[1]
    capture, block, profile = native_fixture(tmp_path, monkeypatch)
    for row in block:
        for observation in row['pre_memory_observations']:
            if row['seq'] == 1:
                observation.update(kind='INDIRECT_CONTROL', operand='*0x3ae3a(%rip)')
            else:
                observation.update(kind='IMPLICIT_RET', operand='(%rsp)')
            observation.update(status='OK', timing='PRE_INSTRUCTION')
        for write in row['possible_memory_writes']:
            write['kind'] = 'CALL_STACK' if row['seq'] == 0 else 'EXPLICIT'
    second = copy.deepcopy(block)
    for row in second:
        row['seq'] += 15
        row['occurrence'] = 'step1'
    rows = block + second
    pre = copy.deepcopy(rows[-1]['post'])
    post = copy.deepcopy(pre)
    post['gpr']['rip'] = f"0x{CALLER_BASE + 0x3568F:016x}"
    rows.append({'seq': 30, 'occurrence': 'terminal1', 'module_sha256': CALLER_SHA,
        'module_load_base': CALLER_BASE, 'module_path': 'gala', 'elf_address': 0x3568E, 'bytes': '90',
        'runtime_pc': CALLER_BASE + 0x3568E, 'post_pc': CALLER_BASE + 0x3568F,
        'pid': 1, 'ptid': [1, 1, 0], 'kind': 'ROUTING', 'opcode': 'nop',
        'pre': pre, 'post': post, 'pre_memory_observations': [], 'possible_memory_writes': [], 'operands': []})
    pointers = {'gradient': 0x20002040, 'q': 0x20002140, 'full_v': 0x20002240, 'latent': 0x20002340}
    zero = ['0x0000000000000000'] * 2
    regions = [{'occurrence': name, 'start_seq': start, 'end_seq': start + 15, 'pointers': pointers,
        'start_state': {name: list(zero) for name in pointers}, 'end_state': {name: list(zero) for name in pointers},
        'entry_pc': CALLER_BASE + 0x35689, 'return_pc': CALLER_BASE + 0x3568E,
        'ptid': [1, 1, 0], 'scheduler_locking': 'Mode for locking scheduler during execution is "on".',
        't_bits': '0x0000000000000000', 'dt_bits': raw.DT} for name, start in [('init', 0), ('step1', 15)]]
    source_names = set(raw.inherited.SOURCE_BASE)
    for folder in ('verified_driver/v1', 'verified_driver/v1/live_chain'):
        source_names.update(path.relative_to(repo).as_posix() for path in (repo / folder).glob('*.py'))
    # Hash source bytes for the inherited binding, without using them as an ISA
    # or expected-result oracle.
    sources = {name: raw.digest_bytes((repo / name).read_bytes()) for name in source_names}
    original = (repo / 'runtime_trace/harness.py').read_bytes()
    changed = original.decode().replace('n_steps=1', 'n_steps=int(os.environ["RTN_STEPS"])').replace('"n_steps": 1', '"n_steps": int(os.environ["RTN_STEPS"])')
    proof = {'original_sha256': raw.inherited.HARNESS_SHA, 'executed_lf_source_sha256': raw.digest_bytes(changed.encode()),
        'calculation_replacement': 'n_steps=1 -> n_steps=int(os.environ["RTN_STEPS"])',
        'metadata_replacement': 'n_steps metadata uses the same requested environment parameter',
        'all_other_source_text_identical': True, 'external_gala_modified': False}
    process = {'pid': 1, 'linux_boot_id': '12345678-1234-1234-1234-123456789abc', 'proc_stat_start_time_ticks': 42}
    capture.update(schema='gala-live-prefix-v1', verdict='PAUSED', requested_steps=1,
        wheel_sha256='cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0',
        machine_mapping_read_by_tracer=False, process_identity=process, acquisition_id='01' * 32,
        regions=regions, caller_corridors=[], terminal_corridor={'occurrence': 'terminal1', 'start_seq': 30, 'end_seq': 31},
        record_count=31, scalar_fp_count=0, opcode_histogram=dict(Counter(row['opcode'] for row in rows)),
        source_pinset_sha256=raw.content_id(sources), harness_source_proof=proof)
    predecessor = SimpleNamespace(requested_steps=1, generation=0, step_index=0,
        content_hash='02' * 32, barrier_kind='GENESIS', q_bits=tuple(zero), full_v_bits=tuple(zero),
        latent_bits=tuple(zero), gradient_bits=tuple(zero))
    snapshot = {'q': zero, 'full_v': zero, 'latent': zero, 'gradient': zero, 't_bits': None,
        'dt_bits': raw.DT, 'next_entry': None, 'paused_pc': CALLER_BASE + 0x3568F, 'body_count': 1, 'frontier': 30}
    chain = '00' * 32
    for row in rows:
        chain = hashlib.sha256(bytes.fromhex(chain) + raw.canonical(row)).hexdigest()
        row['chain'] = chain
    stream = b''.join(raw.canonical(row) + b'\n' for row in rows)
    capture.update(trace_sha256=raw.digest_bytes(stream), final_chain=chain)
    event = {'session_id': '01' * 32, 'barrier_seq': 1, 'completed_step': 1, 'barrier_kind': 'FINAL_TERMINAL',
        'requested_steps': 1, 'process_identity': process, 'trace_prefix_bytes': len(stream),
        'trace_prefix_sha256': raw.digest_bytes(stream), 'trace_chain_hash': chain_hash(stream),
        'predecessor_id': predecessor.content_hash, 'checkpoint_state': snapshot}
    doc = {'schema': 'LIVE_CHECKPOINT_V1', 'event': event,
        'metadata': {'source_snapshot': sources, 'source_binding': raw.content_id(sources), 'capture': capture, 'evidence_role': 'TEST_ONLY'}}
    cp = tmp_path / 'checkpoint'; cp.mkdir()
    (cp / 'trace.jsonl').write_bytes(stream)
    data = raw.canonical_bytes(doc)
    (cp / 'checkpoint.json').write_bytes(data)
    (cp / 'CHECKPOINT').write_bytes((raw.digest_bytes(data) + '\n').encode())
    decoded = {(row['module_sha256'], row['elf_address']): (row['bytes'],
        'call 6350' if row['seq'] in (0, 15) else 'jmp *0x3ae3a(%rip)' if row['seq'] in (1, 16) else row['opcode']) for row in rows}
    monkeypatch.setattr(raw, '_profile', lambda profile, root: {'libc': tmp_path / 'synthetic-libc.so'})
    monkeypatch.setattr(raw.r, '_decoded', lambda rows, root, modules: decoded)
    monkeypatch.setattr(raw, '_topology', lambda *args: None)
    monkeypatch.setattr(raw.r, '_closed_caller_sites', lambda root: set())
    monkeypatch.setattr(raw.r, '_terminal', lambda *args: [])
    return cp, predecessor, repo, profile


def rehash_descriptor(cp, doc):
    data = raw.canonical_bytes(doc)
    (cp / 'checkpoint.json').write_bytes(data)
    (cp / 'CHECKPOINT').write_bytes((raw.digest_bytes(data) + '\n').encode())


def test_sealed_literal_checkpoint_preserves_inherited_guard_path(tmp_path, monkeypatch):
    cp, pred, repo, profile = sealed_boundary_fixture(tmp_path, monkeypatch)
    _, event, capture, rows, report, identity = raw.validate_edge(cp, pred, repo, profile)
    assert event.requested_steps == 1 and report['next_body_executed'] is False
    assert len(rows) == 31 and report['new_record_count'] == 31
    assert [(x['start_seq'], x['end_seq']) for x in report['evex_spans']] == [(2, 15), (17, 30)]
    assert identity == (cp / 'CHECKPOINT').read_text().strip()


@pytest.mark.parametrize('attack', ['process', 'source', 'counter', 'frontier', 'handoff', 'terminal', 'nextentry', 'predecessor', 'tracehash'])
def test_resealed_checkpoint_guard_mutations_refuse(tmp_path, monkeypatch, attack):
    cp, pred, repo, profile = sealed_boundary_fixture(tmp_path, monkeypatch)
    doc = json.loads((cp / 'checkpoint.json').read_bytes())
    capture = doc['metadata']['capture']
    if attack == 'process': capture['process_identity']['pid'] = 2
    elif attack == 'source': doc['metadata']['source_snapshot']['verified_driver/v1/native_evex_raw.py'] = '03' * 32
    elif attack == 'counter': capture['scalar_fp_count'] = 1
    elif attack == 'frontier': doc['event']['checkpoint_state']['frontier'] = 29
    elif attack == 'handoff': capture['regions'][1]['start_state']['latent'][0] = '0x3ff0000000000000'
    elif attack == 'terminal': capture['terminal_corridor']['start_seq'] = 29
    elif attack == 'nextentry': doc['event']['checkpoint_state']['next_entry'] = {}
    elif attack == 'predecessor': doc['event']['predecessor_id'] = '03' * 32
    elif attack == 'tracehash': capture['trace_sha256'] = '03' * 32
    rehash_descriptor(cp, doc)
    with pytest.raises(ValueError): raw.validate_edge(cp, pred, repo, profile)


def test_profile_authenticates_real_packaged_elf_sha_and_build_ids():
    repo = Path(__file__).resolve().parents[1]
    profile = {'profile_id': 'TEST_ONLY_PACKAGED_IDENTITY',
        'libc_sha256': '3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf',
        'libc_build_id': 'a4a7992a8e66555c8141ab2a08a8465ff6e0ea65', 'entry_elf_pc': 0x1996C0,
        'caller_module_sha256': CALLER_SHA, 'caller_build_id': 'ad5a26c3f41fac57364727ec98352fd731b07d80',
        'source_sha256': '01' * 32, 'library_path': 'runtime_trace/frozen_binaries/libc.so.6',
        'caller_path': 'audit/gate2c1/vendor/gala/integrate/cyintegrators/leapfrog.cpython-312-x86_64-linux-gnu.so'}
    assert set(raw._profile(profile, repo)) == {'libc', 'caller'}
    for key, wrong in [('caller_build_id', '00'), ('libc_sha256', '00' * 32), ('entry_elf_pc', 0x189780),
                       ('caller_module_sha256', '00' * 32), ('source_sha256', False)]:
        bad = {**profile, key: wrong}
        with pytest.raises(ValueError): raw._profile(bad, repo)


def topology_fixture(tmp_path, monkeypatch):
    capture, rows, profile = native_fixture(tmp_path, monkeypatch)
    for name, module in capture['modules'].items():
        module['segments'] = [{'flags': 5, 'vaddr': 0, 'filesz': 0x200000, 'memsz': 0x200000, 'file_offset': 0}]
    pointers = {'gradient': 0x20002040, 'q': 0x20002140, 'full_v': 0x20002240, 'latent': 0x20002340}
    regions = [{'start_seq': 0, 'end_seq': 15, 'pointers': pointers},
               {'start_seq': 15, 'end_seq': 30, 'pointers': pointers}]
    second = copy.deepcopy(rows)
    for row in second: row['seq'] += 15
    rows.extend(second)
    oldrows = []
    oldregions = []
    for start in (0, 13):
        pair = copy.deepcopy(rows[:2])
        pair[1]['post_pc'] = LIBC_BASE + 0x189780
        for offset, row in enumerate(pair): row['seq'] = start + offset
        helpers = [{'seq': start + 2 + i, 'module_sha256': profile['libc_sha256'],
                    'elf_address': pc, 'bytes': code} for i, (pc, code) in enumerate(raw.OLD_MEMSET)]
        oldrows.extend(pair + helpers)
        oldregions.append({'start_seq': start, 'end_seq': start + 13, 'pointers': pointers})
    oldcapture = {'regions': oldregions, 'modules': capture['modules']}
    monkeypatch.setattr(raw, 'load', lambda path: oldcapture)
    monkeypatch.setattr(raw.structure, '_load_rows', lambda path: (oldrows, '00' * 32))
    reconstructed = []
    monkeypatch.setattr(raw.native_graph, 'graph', lambda *args: reconstructed.append(args))
    spans = [{'start_seq': 2, 'end_seq': 15}, {'start_seq': 17, 'end_seq': 30}]
    return capture, rows, regions, profile, spans, reconstructed


def test_topology_only_native_helper_changes_and_new_graph_called(tmp_path, monkeypatch):
    capture, rows, regions, profile, spans, reconstructed = topology_fixture(tmp_path, monkeypatch)
    raw._topology(capture, rows, regions, tmp_path, profile, spans)
    assert len(reconstructed) == 1 and reconstructed[0][1] is rows


@pytest.mark.parametrize('attack', ['outside_code', 'outside_opcode', 'outside_kind', 'role', 'helper_position',
    'uncovered_libc', 'pointer_alias', 'pointer_overlap', 'pointer_move'])
def test_topology_structural_mutations_refuse(tmp_path, monkeypatch, attack):
    capture, rows, regions, profile, spans, _ = topology_fixture(tmp_path, monkeypatch)
    if attack == 'outside_code': rows[0]['bytes'] = 'e8c10cfdff'
    elif attack == 'outside_opcode': rows[0]['opcode'] = 'jmp'
    elif attack == 'outside_kind': rows[0]['kind'] = 'ROUTING'
    elif attack == 'role': rows[0]['operands'] = [{'kind': 'register', 'register': 'r15', 'width': 8, 'access': 'read'}]
    elif attack == 'helper_position': rows[0]['module_sha256'] = profile['libc_sha256']
    elif attack == 'uncovered_libc': spans.pop()
    elif attack == 'pointer_alias': regions[0]['pointers'] = {**regions[0]['pointers'], 'q': 0x20002040}
    elif attack == 'pointer_overlap': regions[0]['pointers'] = {**regions[0]['pointers'], 'q': 0x20002048}
    elif attack == 'pointer_move': regions[1]['pointers'] = {**regions[1]['pointers'], 'q': 0x20002440}
    with pytest.raises(ValueError): raw._topology(capture, rows, regions, tmp_path, profile, spans)
