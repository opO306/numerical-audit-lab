"""One actual init/body/caller/terminal collector; no machine mapping input."""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import gdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime_trace.regular_2step.acquire import definition_only_nodes
from runtime_trace.regular_nstep.acquire import collector_source, validate_n, write
from runtime_trace.regular_nstep.resources import reserve_writer

OUT = Path(os.environ['RT_OUTPUT'])
N = validate_n(int(os.environ['RTN_STEPS']))
guard_proofs = []


def load_definition(path, class_name, module_name):
    original = path.read_text(encoding='utf-8')
    source, proof = collector_source(original, 'body' if class_name == 'Capture' else 'caller')
    guard_proofs.append({**proof, 'path': str(path),
        'original_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    namespace = {'__file__': str(path), '__name__': module_name}
    exec(compile(ast.Module(body=definition_only_nodes(source, class_name), type_ignores=[]),
                 str(path), 'exec'), namespace)
    return namespace


# Execute only the reused wrapper's definition/configuration prefix. Replace its
# loader binding before BASE/CALLER construction, leaving old files unchanged.
old_path = ROOT / 'runtime_trace/regular_2step/gdb_acquire.py'
tree = ast.parse(old_path.read_text())
prefix = []
for node in tree.body:
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == 'gdb':
        break
    if isinstance(node, ast.FunctionDef) and node.name == 'load_definition':
        continue
    prefix.append(node)
base = {'__file__': str(old_path), '__name__': 'runtime_trace.regular_nstep._wrapper_definitions',
        'load_definition': load_definition}
exec(compile(ast.Module(body=prefix, type_ignores=[]), str(old_path), 'exec'), base)
Parent = base['Regular2StepCapture']
Caller = base['CallerAcquisition']
Refused = base['Refused']


class BoundedStream:
    def __init__(self, raw):
        self.raw, self.count = raw, 0
    @property
    def closed(self):
        return self.raw.closed
    def close(self):
        return self.raw.close()
    def flush(self):
        return self.raw.flush()
    def write(self, text):
        size = len(text.encode())
        if self.count + size > 536870912:
            raise Refused('raw trace 512 MiB ceiling')
        self.count += size
        return self.raw.write(text)


class Bridge:
    def __init__(self, capture):
        self.capture = capture
    def flush(self):
        self.capture.stream.raw.flush()
    def write(self, text):
        row = json.loads(text)
        row.update(seq=self.capture.count, pid=self.capture.process_identity['pid'],
                   ptid=row['thread_ptid'], occurrence=self.capture.corridor_label)
        unsigned = {key: value for key, value in row.items() if key != 'chain'}
        row['chain'] = hashlib.sha256(bytes.fromhex(self.capture.augmented_chain) +
            json.dumps(unsigned, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.capture.chain = self.capture.augmented_chain = row['chain']
        self.capture.stream.raw.write(json.dumps(row, separators=(',', ':')) + '\n')
        self.capture.count += 1
        opcode = row['assembly'].split()[0]
        self.capture.histogram[opcode] = self.capture.histogram.get(opcode, 0) + 1
        return len(text)


base['CorridorTraceBridge'] = Bridge


class Capture(Parent):
    def __init__(self):
        # One trace reservation reaches this actual bounded stream. Small
        # receipts spend the remaining shared job allocation individually.
        reserve_writer(536870912)
        super().__init__()
        self.stream.raw = BoundedStream(self.stream.raw)
        self.corridors = []
        self.terminal = None

    def terminal_corridor(self):
        # Same collector semantics as internal corridors; terminal stop is the
        # pinned native loop test after the final actual save_all writes.
        corridor = Caller.__new__(Caller)
        corridor.started = self.started
        corridor.inferior_pid = self.process_identity['pid']
        corridor.owner = self.owner
        corridor.maps, corridor.map_snapshots, corridor.modules = [], [], {}
        corridor.records, corridor.chain = 0, '0' * 64
        corridor.trace = Bridge(self)
        corridor.rows, corridor.opcodes = [], {}
        corridor.pre_memory_observation_count = 0
        corridor.pre_memory_observation_failures = []
        corridor.possible_write_count = corridor.same_value_write_count = 0
        corridor.indirect_control_count = corridor.return_count = 0
        corridor.pop_count = corridor.leave_count = 0
        corridor.process_identity = self.process_identity
        corridor.first_step_entry = corridor.first_step_return = corridor.second_step_entry = None
        corridor.refresh_maps('terminal-start')
        start = self.count
        self.corridor_label = f'terminal{N}'
        while True:
            pc = int(gdb.newest_frame().read_register('rip'))
            module, _ = corridor.module_at(pc)
            # Resolve the same registered Gala leapfrog image from region entry.
            body_module, _ = self.module_at(self.regions[-1]['entry_pc'])
            is_final_test = module['sha256'] == body_module['sha256'] and pc - module['load_base'] == 202348
            corridor.one('caller')
            if is_final_test:
                last = corridor.rows[-1]
                if last['next_pc'] != pc + len(bytes.fromhex(last['instruction_bytes'])):
                    raise Refused('terminal loop branch did not fall through')
                break
        for path, module in corridor.modules.items():
            if path not in self.modules:
                self.modules[path] = {'path': path, 'sha256': module['sha256'],
                    'load_base': module['load_base'], 'segments': module['segments'],
                    'wheel_member': None, '_raw': module['_raw']}
        self.terminal = {'occurrence': self.corridor_label, 'start_seq': start,
            'end_seq': self.count, 'start_pc': corridor.rows[0]['pc'],
            'end_pc': corridor.rows[-1]['next_pc'], 'rows': corridor.records,
            'local_final_chain': corridor.chain,
            'post_frontier': 'UNTRACED native/Python harness tail; original source and observed normal exit prerequisite'}

    def run(self):
        self.started = time.perf_counter()
        init = gdb.Breakpoint(base['INIT_SYMBOL'], internal=True)
        step = gdb.Breakpoint(base['STEP_SYMBOL'], internal=True)
        gdb.execute('run', to_string=True)
        init.enabled = False
        self.region('init', base['INIT_SYMBOL'])
        gdb.execute('continue', to_string=True)
        for k in range(1, N + 1):
            self.region(f'step{k}', base['STEP_SYMBOL'])
            if k < N:
                self.corridor_label = f'caller{k}-{k+1}'
                self.caller_corridor(self.regions[-1]['entry_pc'])
                self.corridor['occurrence'] = self.corridor_label
                self.corridors.append(self.corridor)
        self.terminal_corridor()
        init.delete()
        # Keep the numerical entry breakpoint to detect extra native calls.
        gdb.execute('set scheduler-locking off')
        event = {'observed': False, 'inferior_pid': self.process_identity['pid'], 'exit_code': None}
        def exited(e):
            event.update(observed=True, exit_code=getattr(e, 'exit_code', None))
        gdb.events.exited.connect(exited)
        try:
            gdb.execute('continue', to_string=True)
        finally:
            gdb.events.exited.disconnect(exited)
        event['selected_inferior_pid_after_exit'] = gdb.selected_inferior().pid
        if event['observed'] is not True or event['exit_code'] != 0 or event['selected_inferior_pid_after_exit'] != 0:
            raise Refused('extra step or incomplete/non-normal exit')
        if not (OUT / 'harness_output.json').is_file():
            raise Refused('missing original harness result')
        self.harness_completed_normally = True
        self.gdb_exit_event = event
        step.delete()

    def result(self, verdict, reason=None):
        result = super().result(verdict, reason)
        result.update(schema='gala-regular-nstep-runtime-trace-v1', requested_steps=N,
            caller_corridors=self.corridors, terminal_corridor=self.terminal,
            guard_source_transformations=guard_proofs,
            scope='actual observed regular finite bodies/callers/terminal stores; conditional untraced base and harness tail')
        result.pop('caller_corridor', None)
        return result


for command in ('set pagination off', 'set confirm off', 'set breakpoint pending on',
                'set disassembly-flavor att', 'set print symbol-filename on',
                'set debuginfod enabled off', 'set non-stop off'):
    gdb.execute(command)
capture = None
try:
    capture = Capture()
    capture.run()
    result = capture.result('CAPTURED')
except Exception as exc:
    result = capture.result('REFUSED', f'{type(exc).__name__}: {exc}') if capture else {
        'schema': 'gala-regular-nstep-runtime-trace-v1', 'verdict': 'REFUSED',
        'reason': f'{type(exc).__name__}: {exc}', 'requested_steps': N}
    try:
        if gdb.selected_inferior().pid:
            gdb.execute('kill', to_string=True)
    except Exception:
        pass
write(OUT / 'capture.pending.json', result)
