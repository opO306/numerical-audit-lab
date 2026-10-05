"""Source-wide abstract-operation inventory and actual precharge trace.

Author classification only. OPEN does not mean an automatically confirmed
bug. The approved spec has no blanket small-counter/parity exemption.
"""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from verify import ROOT, OUT, SOURCE, imports, source_hashes, save

imports()
from independent_checker.c1b1.impulse.resource import ResourceAccount
from independent_checker.c1b1.impulse.producer import evaluate_reference
from impulse_reference_support import encoded, reference_policy

SPEC_PATH = ROOT / 'specs/c1b1-independent-impulse-v1-attempt-reason-null/finite-policy.json'
spec_bytes = SPEC_PATH.read_bytes()
schedule = json.loads(spec_bytes)['work_accounting']
WRAPPERS = {'add','multiply','shift','divmod','isqrt','fraction','qadd','qneg','qmul','qdiv','qpower','compare'}


class Inventory(ast.NodeVisitor):
    def __init__(self, file):
        self.file = file
        self.scope = []
        self.rows = []
        self.routes = []

    def visit_ClassDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def record(self, node):
        scope = '.'.join(self.scope) or '<module>'
        text = ast.unparse(node)
        status = 'OPEN / UNRESOLVED'
        basis = 'No automatic exclusion: assign the concrete operation to the approved abstract schedule before claiming closure.'
        primitive = {
            ('ResourceAccount.add','a + b'), ('ResourceAccount.multiply','a * b'),
            ('ResourceAccount.shift','a << n'), ('ResourceAccount.divmod','divmod(a, b)'),
            ('ResourceAccount.isqrt','isqrt(a)'), ('ResourceAccount.fraction','Q(n, d)'),
            ('ResourceAccount.compare','u > v'), ('ResourceAccount.compare','u < v'),
            ('ResourceAccount.compare','(u > v) - (u < v)'),
        }
        if self.file == 'resource.py' and (scope,text) in primitive:
            status = 'ACCOUNTED'
            basis = 'Declared abstract primitive inside its own precharged wrapper; compare result construction belongs to one precharged comparison.'
        elif self.file == 'attempt.py' and scope == 'append_attempt' and text == 'previous + canonical_bytes(obj)':
            status = 'EXPLICITLY OUTSIDE THIS WORK MODEL'
            basis = 'Proof-wire attempt digest specifies bytes32 concatenation, not an integer/rational operation; wire/hash contract applies.'
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and self.file in ('spec.py','certificate.py'):
            status = 'EXPLICITLY OUTSIDE THIS WORK MODEL'
            basis = 'Path object joining for frozen data/source identity, not integer division; actual operands are pathlib Paths.'
        self.rows.append(dict(file=self.file, scope=scope, line=node.lineno,
                              node=type(node).__name__, expression=text, status=status, basis=basis))

    def visit_BinOp(self, node):
        self.record(node)
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        self.record(node)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self.record(node)
        self.generic_visit(node)

    def visit_Compare(self, node):
        self.record(node)
        self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value,ast.Name) and func.value.id in ('c','self') and func.attr in WRAPPERS:
            self.routes.append(dict(file=self.file,scope='.'.join(self.scope),line=node.lineno,
                expression=ast.unparse(node),wrapper=func.attr,status='ACCOUNTED',
                basis='Routes declared arithmetic to ResourceAccount; composite costs are nested, not an extra CPU instruction model.'))
        elif isinstance(func, ast.Name) and func.id in ('Q','divmod','isqrt','abs','sum','pow','max','min','int'):
            self.record(node)
        self.generic_visit(node)


inventories = []
routes = []
sign_line = None
for path in sorted(SOURCE.glob('*.py')):
    tree = ast.parse(path.read_text(encoding='utf8'))
    visitor = Inventory(path.name)
    visitor.visit(tree)
    inventories.extend(visitor.rows)
    routes.extend(visitor.routes)
    if path.name == 'resource.py':
        for node in ast.walk(tree):
            if isinstance(node,ast.Assign) and ast.unparse(node) == 'numerator = self.multiply(numerator, sign)':
                sign_line = node.lineno
assert sign_line is not None

# No rewriting of production functions. Observe real primitive pre() calls.
precharges = []
sign_charges = []
call_sites = Counter()
pending = {}
first_sqrt = []
resource_file = str(SOURCE / 'resource.py')
sqrt_file = str(SOURCE / 'sqrt_enclosure.py')


def profile(frame, event, arg):
    code = frame.f_code
    if event == 'call' and code.co_filename == sqrt_file and code.co_name == 'sqrt_enclosure' and not first_sqrt:
        c = frame.f_locals['c']
        r2 = frame.f_locals['r2']
        first_sqrt.append(dict(work_before=c.work, operations_before=c.operations,
                              r2_numerator=str(r2.numerator), r2_denominator=str(r2.denominator)))
    if code.co_filename != resource_file:
        return
    name = code.co_name
    caller = frame.f_back
    if event == 'call' and name in WRAPPERS | {'pre'}:
        c = frame.f_locals['self']
        if not isinstance(c,ResourceAccount):
            return
        call_sites[(Path(caller.f_code.co_filename).name,caller.f_code.co_name,caller.f_lineno,name)] += 1
        if name == 'pre':
            pending[id(frame)] = ('pre',dict(bits=frame.f_locals['bits'],declared_work=frame.f_locals['work'],
                work_before=c.work,operations_before=c.operations,
                abstract_primitive=caller.f_code.co_name,wrapper_line=caller.f_lineno))
        elif name == 'multiply' and caller.f_code.co_name == 'qdiv' and caller.f_lineno == sign_line:
            a,b = frame.f_locals['a'],frame.f_locals['b']
            pending[id(frame)] = ('sign',dict(A=abs(a).bit_length(),B=abs(b).bit_length(),sign=b,
                declared_work=(abs(a).bit_length()+1)*(abs(b).bit_length()+1),work_before=c.work))
    elif event == 'return' and id(frame) in pending:
        kind, row = pending.pop(id(frame))
        row['work_after'] = frame.f_locals['self'].work
        row['charged_work'] = row['work_after']-row['work_before']
        assert row['charged_work'] == row['declared_work']
        (precharges if kind=='pre' else sign_charges).append(row)


obj = json.loads((OUT/'canonical-input.json').read_bytes())
obj['budget']['work_unit_max'] = str(10**40)
before = source_hashes()
previous_profile = sys.getprofile()
sys.setprofile(profile)
try:
    result = evaluate_reference(encoded(obj),reference_policy(obj))
finally:
    sys.setprofile(previous_profile)
after = source_hashes()
assert before == after and result.raw is not None
assert sum(x['declared_work'] for x in precharges) == result.account['mathematical_work']
assert len(precharges) == result.account['operations']
before_boundaries = json.loads((OUT/'before-boundaries.json').read_text())
delta = result.account['mathematical_work']-int(before_boundaries['observed_work'])
assert sum(x['charged_work'] for x in sign_charges) == delta

classes = [
    ('add / compare','add_compare',['add','compare','qadd'],
     'rounding increment, interval endpoints/extrema/refinements; direct input/control comparisons remain OPEN',
     'Wrappers ACCOUNTED; source-wide closure OPEN'),
    ('multiply','multiply',['multiply','qmul','qdiv','qneg','qpower'],
     'QDIV sign now routed; producer r2 direct rational products remain OPEN candidate',
     'QDIV FIX APPLIED; wrapper composition ACCOUNTED; source-wide closure OPEN'),
    ('shift','shift',['shift'],
     'sqrt/widen/certificate shift routed; parameter schedule/control right shifts and doubling scope OPEN',
     'Wrappers ACCOUNTED; parameter scope OPEN'),
    ('divmod','divmod',['divmod'],
     'sqrt/widen/nearest_even/certificate division routed; modulo/parity and control // scope OPEN',
     'Wrappers ACCOUNTED; unassigned control operations OPEN'),
    ('isqrt','isqrt',['isqrt'],
     'sqrt_enclosure calls ResourceAccount.isqrt; result scaling uses checked shift/divmod',
     'ACCOUNTED'),
    ('rational normalization / gcd','gcd',['fraction','qadd','qmul','qdiv','qneg','qpower'],
     'Fraction(n,d) prepaid by fraction; direct Q constructions/producer R2 and input conversion scope OPEN',
     'Core normalization ACCOUNTED; source-wide closure OPEN'),
]
closure = []
for operation,key,wrappers,bypass,status in classes:
    closure.append(dict(operation_class=operation, declared_work_formula=schedule[key],
        implementation_wrappers=wrappers, actual_call_sites=[r for r in routes if r['wrapper'] in wrappers],
        direct_bypass_found_or_scope_gap=bypass,status=status))

save(OUT/'resource-accounting-review.json',dict(
    scope='RESOURCE ACCOUNTING CLOSURE AUTHOR REVIEW COMPLETE; GLOBAL CLOSURE OPEN; NOT INDEPENDENT APPROVAL',
    finite_policy_sha256=hashlib.sha256(spec_bytes).hexdigest(),declared_schedule=schedule,
    source_files=before, source_unchanged=before==after,
    closure_table=closure, direct_operation_inventory=inventories, wrapper_routes=routes,
    direct_operation_categories=dict(Counter(row['status'] for row in inventories)),
    actual_wrapper_call_sites=[dict(file=f,function=n,line=l,wrapper=w,count=v) for (f,n,l,w),v in sorted(call_sites.items())],
    actual_precharges=precharges, actual_sign_charges=sign_charges,
    measured_W2=str(result.account['mathematical_work']), actual_precharge_count=len(precharges),
    actual_sign_charge_count=len(sign_charges),sign_charge_work_delta=str(delta),
    first_sqrt_entry=first_sqrt,
    remaining_open=[
        dict(id='O-R2-TRUTH-PATH',status='OPEN / UNRESOLVED',finding_candidate=True,
             expression='producer.evaluate_reference: r2=sum(x*x for x in parsed.q)',
             basis='Declared rational work includes products/normalization, but this direct expression executes after account creation with ledger zero. No approved exclusion established; keep unresolved and do not label W2 globally fully-accounted.'),
        dict(id='O-CONTROL-PARAMETERS',status='OPEN / UNRESOLVED',finding_candidate=False,
             expression='loop/precision/order arithmetic, parity, abs, unary signs, range/control comparisons',
             basis='Direct syntax alone is not a confirmed defect. The spec has no blanket small/cheap exemption; exact assignment to an abstract operation remains unresolved.'),
        dict(id='O-DIRECT-FRACTION-CONSTRUCTION',status='OPEN / UNRESOLVED',finding_candidate=False,
             expression='point(q), Q(n+1), literal/input/constants Fraction construction outside fraction()',
             basis='Do not model every Fraction CPU instruction. Establish whether each construction is a charged abstract normalization, pinned data or validation before closure.'),
        dict(id='O-ALLOCATION-AND-WORKER',status='OPEN / UNRESOLVED',finding_candidate=False,
             expression='allocator-specific majorant, V2 whole-call preflight, hard OS worker, approved instance',
             basis='Separate activation gates explicitly retained by finite policy.'),
    ],
    global_resource_accounting_pass=False, runtime_activation_allowed=False))
print('REVIEW COMPLETE',len(inventories),'static sites',len(routes),'wrapper routes')
print('ACTUAL PRECHARGES',len(precharges),'W2',result.account['mathematical_work'])
print('QDIV SIGN',len(sign_charges),'charges; exact added work',delta)
print('CATEGORIES',dict(Counter(row['status'] for row in inventories)))
print('GLOBAL ACCOUNTING CLOSURE OPEN; no independent approval')
