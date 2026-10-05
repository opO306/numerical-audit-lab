"""Author evidence only. Never commits, pushes, activates or invokes V2."""
import argparse
import ast
import collections
import dis
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from fractions import Fraction

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'current/c1b1-round-add-fix-2026-10-05'
SOURCE = ROOT / 'independent_checker/c1b1/impulse'
TARGET = 'd5475e23358cbf7f88018abfb67a8bfd192c5410'
W = 2605253326086889986
PROTECTED = ['claim_adapter.py', 'compare.py', 'contracts.py', 'exact_slow.py',
             'exact_fast.py', 'exact_geometry.py', 'semantic_manifest_v1.json',
             'semantic_manifest_v1.sha256']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True) + '\n', encoding='ascii')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def initialize():
    if git('rev-parse', 'HEAD').decode().strip() != TARGET:
        raise ValueError('wrong target')
    OUT.mkdir(exist_ok=False)
    paths = git('ls-files', '-z').decode('utf8').split('\0')[:-1]
    inventory = {p: sha((ROOT / p).read_bytes()) for p in paths}
    save(OUT / 'baseline.json', dict(target=TARGET,
         branch=git('branch', '--show-current').decode().strip(),
         tracked_raw_sha256=inventory,
         git_status=git('status', '--short').decode('utf8')))
    received = OUT / 'received'
    received.mkdir()
    originals = {
        name: Path('D:/감사/REPORT_KO(7)') / name for name in
        ('AUDIT_REPORT_KO.md', 'VERDICT.json', 'COUNTEREXAMPLE_INPUT.json', 'COUNTEREXAMPLE_RESULT.json')
    }
    originals['user-request.txt'] = Path('C:/Users/zun24/.codex/attachments/7b4662ef-2568-4cfb-bbab-489f49eaf739/붙여넣은 텍스트.txt')
    copied = {}
    for name, source in originals.items():
        data = source.read_bytes()
        (received / name).write_bytes(data)
        copied[name] = dict(original=str(source), sha256=sha(data), bytes=len(data))
    save(OUT / 'received-identity.json', copied)
    fixture = ROOT / 'tests/fixtures/impulse_round_add/COUNTEREXAMPLE_INPUT.json'
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_bytes((received / 'COUNTEREXAMPLE_INPUT.json').read_bytes())
    (OUT / 'rounding-before.py').write_bytes((SOURCE / 'rounding.py').read_bytes())
    print('baseline', len(inventory), 'received', len(copied))


def imports():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / 'tests'))


def probe(label):
    imports()
    from independent_checker.c1b1.impulse.resource import ResourceAccount, ResourceLimit
    from independent_checker.c1b1.impulse.rounding import nearest_even
    from independent_checker.c1b1.impulse.producer import evaluate_reference
    from impulse_reference_support import reference_policy, encoded

    class ObservedAccount(ResourceAccount):
        def add(self, a, b):
            event = dict(a=str(a), b=str(b), work_before=self.work, operations_before=self.operations)
            self.events.append(event)
            try:
                result = super().add(a, b)
            except ResourceLimit as err:
                event.update(outcome='REFUSED', kind=err.kind)
                raise
            event.update(outcome='RETURNED', result=str(result))
            return result

    scalar = []
    for q, caps in [(Fraction(7, 4), (73, 74, 75)), (Fraction(-5, 2), (42, 44, 45))]:
        for cap in caps:
            c = ObservedAccount(bit_max=100000, num_bit_max=100000, den_bit_max=100000, work_max=cap)
            c.events = []
            row = dict(q=str(q), work_max=cap, result=None, refusal=None)
            try:
                row['result'] = nearest_even(q, c)
            except ResourceLimit as err:
                row['refusal'] = err.kind
            row.update(charged_work=c.work, operations=c.operations, add_events=c.events)
            scalar.append(row)
    whole = []
    original = (OUT / 'received/COUNTEREXAMPLE_INPUT.json').read_bytes()
    for cap in (W, W + 152):
        obj = json.loads(original)
        obj['budget']['work_unit_max'] = str(cap)
        data = encoded(obj)
        assert cap != W or data == original
        r = evaluate_reference(data, reference_policy(obj))
        row = dict(cap=str(cap), input_sha256=sha(data), layers=r.layers,
                   raw=None if r.raw is None else list(map(str, r.raw)),
                   opposite=None if r.opposite is None else list(map(str, r.opposite)),
                   certificate_present=r.certificate is not None, account=r.account,
                   failure=None if r.failure is None else json.loads(r.failure),
                   input_unchanged=data == encoded(obj))
        whole.append(row)
        if r.failure is not None:
            (OUT / (label + '-whole-' + str(cap) + '-failure.json')).write_bytes(r.failure)
        if r.certificate is not None:
            (OUT / (label + '-whole-' + str(cap) + '-private-certificate.json')).write_bytes(r.certificate)
    save(OUT / (label + '-boundary-results.json'), dict(scope='AUTHOR REGRESSION / PRIVATE REFERENCE ONLY', scalar=scalar, whole_call=whole))
    print(json.dumps(dict(label=label, scalar=scalar, whole_call=whole), indent=2))


def review():
    imports()
    from independent_checker.c1b1.impulse.producer import evaluate_reference
    from independent_checker.c1b1.impulse.resource import ResourceAccount
    from impulse_reference_support import encoded, reference_policy
    # Actual opcode occurrences, not a static call graph presented as execution.
    counts = collections.Counter()
    functions = collections.Counter()
    opcodes = {}
    file_names = {}
    direct = []
    for path in sorted(SOURCE.glob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf8'))
        for node in ast.walk(tree):
            if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.AugAssign, ast.Compare)):
                direct.append(dict(file=path.name, line=node.lineno, syntax=ast.unparse(node), node=type(node).__name__))

    def trace(frame, event, arg):
        filename = frame.f_code.co_filename
        if filename not in file_names:
            path = Path(filename)
            file_names[filename] = path.name if path.parent == SOURCE else None
        name = file_names[filename]
        if name is None:
            return None
        if event == 'call':
            functions[(name, frame.f_code.co_name)] += 1
            frame.f_trace_opcodes = True
        elif event == 'opcode':
            if frame.f_code not in opcodes:
                opcodes[frame.f_code] = {i.offset: i for i in dis.get_instructions(frame.f_code)}
            instruction = opcodes[frame.f_code].get(frame.f_lasti)
            if instruction and instruction.opname in ('BINARY_OP', 'UNARY_NEGATIVE', 'COMPARE_OP', 'CALL'):
                counts[(name, frame.f_code.co_name, frame.f_lineno,
                        instruction.opname, instruction.argrepr)] += 1
        return trace

    obj = json.loads((OUT / 'received/COUNTEREXAMPLE_INPUT.json').read_bytes())
    obj['budget']['work_unit_max'] = str(W + 152)
    # Python 3.12.7 enables opcode tracing at settrace time only when a
    # current frame already requests opcodes. Preserve/restore that flag.
    caller = sys._getframe()
    previous_opcode_flag = caller.f_trace_opcodes
    caller.f_trace_opcodes = True
    sys.settrace(trace)
    try:
        result = evaluate_reference(encoded(obj), reference_policy(obj))
    finally:
        sys.settrace(None)
        caller.f_trace_opcodes = previous_opcode_flag
    if result.raw is None:
        raise ValueError('review fixture failed')
    if not counts:
        raise ValueError('opcode acquisition unavailable; cannot claim dynamic opcode evidence')
    # Exact separate accounting probe: the directly executed *sign has cost 4.
    c = ResourceAccount(bit_max=100000, num_bit_max=100000, den_bit_max=100000, work_max=40)
    qdiv_result = c.qdiv(Fraction(1), Fraction(1))
    save(OUT / 'resource-path-review.json', dict(
        scope='AUTHOR STATIC AND DYNAMIC PATH REVIEW; NOT INDEPENDENT RESOURCE PASS',
        fixture='canonical q=(5,3,-2), cap=W+152', result_layers=result.layers,
        static_operations=direct,
        actual_function_calls=[dict(file=f, function=n, count=v) for (f, n), v in sorted(functions.items())],
        actual_opcodes=[dict(file=f, function=n, line=l, opcode=o, argument=a, count=v)
                        for (f, n, l, o, a), v in sorted(counts.items())],
        additional_finding=dict(id='F-RESOURCE-QDIV-SIGN', status='AUTHOR CONFIRMED / OPEN / NOT FIXED',
            source='resource.py:ResourceAccount.qdiv', expression='self.multiply(a.numerator, b.denominator)*sign',
            scalar=dict(a='1', b='1', work_max=40, result=str(qdiv_result), charged_work=c.work,
                        operations=c.operations, omitted_multiply_work=4),
            whole_call_direct_sign_multiply_occurrences=sum(v for (f,n,l,o,a),v in counts.items()
                if f=='resource.py' and n=='qdiv' and o=='BINARY_OP' and a=='*'),
            expected_complete_schedule_work=44,
            limitation='Confirmed author contract counterexample; independent review pending. Outside the requested minimal fix.')))
    print('actual opcode sites', len(counts), 'functions', len(functions), 'qdiv sign probe', str(qdiv_result), c.work, c.operations)


def preserve():
    baseline = json.loads((OUT / 'baseline.json').read_text())
    old = baseline['tracked_raw_sha256']
    changed, missing = [], []
    for path, digest in old.items():
        if not (ROOT / path).is_file():
            missing.append(path)
        elif sha((ROOT / path).read_bytes()) != digest:
            changed.append(path)
    protected = {}
    for name in PROTECTED:
        path = 'independent_checker/c1b1/' + name
        data = (ROOT / path).read_bytes()
        protected[path] = dict(sha256=sha(data), equal_target=sha(data) == old[path],
                              equal_65d8=data == git('show', '65d8fd29ae255529afead70289098d36b825b3b4:' + path))
    historical = [p for p in old if p.startswith(('specs/', 'docs/', 'audit/', 'current/'))]
    files = {p.name: sha(p.read_bytes()) for p in sorted(SOURCE.glob('*.py'))}
    bundle = sha((json.dumps(files, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii'))
    report = dict(target=TARGET, current_head=git('rev-parse', 'HEAD').decode().strip(),
                  base_tracked=len(old), changed=changed, missing=missing,
                  unchanged=len(old) - len(changed) - len(missing),
                  historical_count=len(historical), historical_byte_identical=all(p not in changed + missing for p in historical),
                  protected=protected, approved_spec_byte_identical=all(p not in changed + missing for p in old if p.startswith('specs/')))
    save(OUT / 'preservation.json', report)
    save(OUT / 'source-identity.json', dict(files=files, source_bundle_sha256=bundle,
         git_commit_created=False, source_identity_kind='UNCOMMITTED WORKING SOURCE SHA-256'))
    (OUT / 'rounding-after.py').write_bytes((SOURCE / 'rounding.py').read_bytes())
    (OUT / 'rounding.diff').write_bytes(git('diff', '--', 'independent_checker/c1b1/impulse/rounding.py'))
    print(json.dumps(dict(source_bundle_sha256=bundle, preservation=report), indent=2))
    if missing or changed != ['independent_checker/c1b1/impulse/rounding.py']:
        raise ValueError('unexpected historical mutation')
    if not all(v['equal_target'] and v['equal_65d8'] for v in protected.values()):
        raise ValueError('protected arithmetic mutation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('init', 'probe-before', 'probe-after', 'review', 'preserve'))
    action = parser.parse_args().action
    if action == 'init':
        initialize()
    elif action.startswith('probe-'):
        probe(action.removeprefix('probe-'))
    elif action == 'review':
        review()
    else:
        preserve()
