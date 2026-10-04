"""Reproducible synthetic arithmetic-only benchmark, after correctness gates.

Counter runs instrument separate AST copies of the new Lab modules and stdlib
fractions. Timing runs use the ordinary uninstrumented implementations.
"""
import ast
from collections import Counter
from dataclasses import replace
import hashlib
import inspect
import json
import math
import operator
from pathlib import Path
import platform
import statistics
import sys
import time
import types
import fractions

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from independent_checker.c1b1 import contracts, exact_slow, exact_fast, claim_adapter

PACKAGE = ROOT / "independent_checker/c1b1"
COUNTS = Counter()
OPS = {"multiply": operator.mul, "floor_divide": operator.floordiv,
       "modulo": operator.mod, "true_divide": operator.truediv}


def measured_binary(a, b, kind):
    if type(a) is int and type(b) is int:
        COUNTS["integer_" + kind] += 1
    return OPS[kind](a, b)


def measured_divmod(a, b):
    if type(a) is int and type(b) is int:
        COUNTS["integer_divmod"] += 1
    return divmod(a, b)


class Instrument(ast.NodeTransformer):
    kinds = {ast.Mult: "multiply", ast.FloorDiv: "floor_divide", ast.Mod: "modulo", ast.Div: "true_divide"}

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if type(node.op) in self.kinds:
            return ast.copy_location(ast.Call(ast.Name("_audit_count_binop", ast.Load()),
                [node.left, node.right, ast.Constant(self.kinds[type(node.op)])], []), node)
        return node

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        if type(node.op) in self.kinds and isinstance(node.target, ast.Name):
            return ast.copy_location(ast.Assign([node.target], ast.Call(ast.Name("_audit_count_binop", ast.Load()),
                [ast.Name(node.target.id, ast.Load()), node.value, ast.Constant(self.kinds[type(node.op)])], [])), node)
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == "divmod":
            node.func.id = "_audit_count_divmod"
        return node


def instrument_module(name, source, filename, directory):
    tree = ast.fix_missing_locations(Instrument().visit(ast.parse(source, filename)))
    rendered = ast.unparse(tree)
    saved = directory / (name.rsplit(".", 1)[-1] + ".instrumented.txt")
    saved.write_text(rendered + "\n", encoding="utf-8")
    module = types.ModuleType(name)
    module.__file__ = filename
    module.__package__ = name.rpartition(".")[0]
    module._audit_count_binop = measured_binary
    module._audit_count_divmod = measured_divmod
    sys.modules[name] = module
    exec(compile(tree, filename, "exec"), module.__dict__)
    return module


def instrumented_modules(directory):
    directory.mkdir(parents=True, exist_ok=True)
    fraction_source = inspect.getsource(fractions)
    private = instrument_module("_lab_profile_fractions", fraction_source,
                                fractions.__file__, directory)
    name = "_lab_c1b1_profile"
    package = types.ModuleType(name)
    package.__path__ = [str(PACKAGE)]
    sys.modules[name] = package
    modules = {}
    for key in ("contracts", "exact_geometry", "exact_slow", "exact_fast", "compare", "claim_adapter"):
        file = PACKAGE / (key + ".py")
        module = instrument_module(name + "." + key, file.read_text(encoding="utf-8"), str(file), directory)
        if "Fraction" in module.__dict__:
            module.Fraction = private.Fraction
        modules[key] = module
    ctor = private.Fraction.__new__.__code__
    factory = private.Fraction._from_coprime_ints.__func__.__code__
    def profile(frame, event, arg):
        if event == "c_call" and arg is math.gcd:
            COUNTS["gcd_calls"] += 1
        if event == "call":
            if frame.f_code is ctor:
                COUNTS["Fraction_constructor_calls"] += 1
            if frame.f_code is factory:
                COUNTS["Fraction_coprime_factory_calls"] += 1
            if frame.f_code.co_name in ("nearest_even", "nearest_even_ratio"):
                COUNTS["rounding_calls"] += 1
    return modules, profile


def inputs(c):
    pos, mom = c.Grid(96, 48), c.Grid(96, 80)
    cases = []
    for index in range(8):
        r_i, r_j = (10 << 48, 2 << 48, 0), (-10 << 48, -(2 << 48), 0)
        p_i = ((index + 1) << 76, -(3 << 74), 1 << 75)
        p_j = (-(index + 1) << 75, 2 << 73, -(1 << 74))
        d = c.DriftInput(pos, mom, r_i, r_j, p_i, p_j,
                         c.Ratio(3, 2), c.Ratio(7, 3), c.Ratio(index + 1, 8))
        k = c.KickInput(mom, mom, p_i, p_j, (1 << 72, -(1 << 71), 3 << 70))
        cases.append((d, k, c.Ratio(1, 100)))
    return cases


def paired(module, c, case):
    d, k, threshold = case
    first = module.kick(k)
    middle_input = replace(d, p_i=first.p_i, p_j=first.p_j)
    middle = module.guarded_drift(middle_input, threshold)
    last = module.kick(c.KickInput(k.momentum_grid, k.impulse_grid, first.p_i, first.p_j, k.J_raw))
    return first, middle, last


def functions(module, c):
    return {"drift": lambda case: module.drift(case[0]),
            "kick": lambda case: module.kick(case[1]),
            "paired_arithmetic_transition": lambda case: paired(module, c, case)}


def run(report_path, evidence_directory):
    ordinary = {"contracts": contracts, "exact_slow": exact_slow, "exact_fast": exact_fast, "claim_adapter": claim_adapter}
    cloned, profile = instrumented_modules(evidence_directory)
    ordinary_cases, cloned_cases = inputs(contracts), inputs(cloned["contracts"])
    for operation in ("drift", "kick", "paired_arithmetic_transition"):
        for case in ordinary_cases:
            slow = functions(exact_slow, contracts)[operation](case)
            fast = functions(exact_fast, contracts)[operation](case)
            assert claim_adapter.canonical_data(slow) == claim_adapter.canonical_data(fast), operation
    rows = {}
    for label in ("exact_slow", "exact_fast"):
        vanilla_functions = functions(ordinary[label], contracts)
        count_functions = functions(cloned[label], cloned["contracts"])
        for operation, vanilla in vanilla_functions.items():
            key = label + "." + operation
            # Compare every intermediate, exact endpoint and guard result before counting.
            for original_case, cloned_case in zip(ordinary_cases, cloned_cases):
                expected = claim_adapter.canonical_data(vanilla(original_case))
                observed = cloned["claim_adapter"].canonical_data(count_functions[operation](cloned_case))
                assert expected == observed, key
            COUNTS.clear()
            sys.setprofile(profile)
            try:
                for case in cloned_cases:
                    count_functions[operation](case)
            finally:
                sys.setprofile(None)
            counts = dict(COUNTS)
            counts["Fraction_constructions"] = counts.get("Fraction_constructor_calls", 0) + counts.get("Fraction_coprime_factory_calls", 0)
            for counter in ("gcd_calls", "integer_multiply", "integer_floor_divide", "integer_modulo", "integer_divmod", "integer_true_divide", "rounding_calls"):
                counts.setdefault(counter, 0)
            rows[key] = {"count_input_invocations": len(cloned_cases), "actual_counts": counts,
                         "instrumented_output_matches_ordinary": True, "wall_ns_per_invocation": [], "cpu_ns_per_invocation": []}
    # No instrumentation/profile during wall/CPU measurements; alternate path order.
    for operation in ("drift", "kick", "paired_arithmetic_transition"):
        funcs = {label: functions(ordinary[label], contracts)[operation] for label in ("exact_slow", "exact_fast")}
        for _ in range(20):
            for label in ("exact_slow", "exact_fast"):
                for case in ordinary_cases:
                    funcs[label](case)
        calibration = []
        for label in ("exact_slow", "exact_fast"):
            started = time.perf_counter_ns()
            for _ in range(50):
                for case in ordinary_cases:
                    funcs[label](case)
            calibration.append((time.perf_counter_ns() - started) / 400)
        sweeps = max(200, math.ceil(250000000 / min(calibration) / len(ordinary_cases)))
        invocations = sweeps * len(ordinary_cases)
        for label in ("exact_slow", "exact_fast"):
            rows[label + "." + operation]["timing_invocations_per_repetition"] = invocations
        for repetition in range(9):
            order = ("exact_slow", "exact_fast") if repetition % 2 == 0 else ("exact_fast", "exact_slow")
            for label in order:
                wall0, cpu0 = time.perf_counter_ns(), time.process_time_ns()
                for _ in range(sweeps):
                    for case in ordinary_cases:
                        funcs[label](case)
                cpu, wall = time.process_time_ns() - cpu0, time.perf_counter_ns() - wall0
                row = rows[label + "." + operation]
                row["wall_ns_per_invocation"].append(wall / invocations)
                row["cpu_ns_per_invocation"].append(cpu / invocations)
    ratios = {}
    for operation in ("drift", "kick", "paired_arithmetic_transition"):
        for label in ("exact_slow", "exact_fast"):
            row = rows[label + "." + operation]
            for clock in ("wall", "cpu"):
                values = row[clock + "_ns_per_invocation"]
                row[clock + "_summary_ns"] = {"median": statistics.median(values), "min": min(values), "max": max(values)}
        ratios[operation] = {clock: rows["exact_slow." + operation][clock + "_summary_ns"]["median"] /
                                   rows["exact_fast." + operation][clock + "_summary_ns"]["median"] for clock in ("wall", "cpu")}
    report = {"scope": "ARITHMETIC_ONLY", "j_status": "J_NOT_VERIFIED", "fast_status": contracts.FAST_STATUS,
        "spec_sha256": contracts.SPEC_SHA256, "python": sys.version, "platform": platform.platform(),
        "processor": platform.processor(), "input_panel": "8 synthetic successful 2-atom 3D cases; candidate numeric grids only; synthetic masses/dt/threshold; supplied J reused for both kicks",
        "input_panel_data": [{"drift": claim_adapter.canonical_data(d), "kick": claim_adapter.canonical_data(k), "threshold": claim_adapter.canonical_data(t)} for d, k, t in ordinary_cases],
        "timing": "20 warm-up sweeps, 9 alternating repetitions; common operation-specific batch calibrated to at least 250ms for the faster path; ordinary production modules, no profiler; validation included; paired K-D-K includes exact segment/stored guards, supplied J only",
        "clock_info": {key: vars(time.get_clock_info(key)) for key in ("perf_counter", "process_time")},
        "initial_measurement_limitation": "Initial 1600-invocation batches had zero/quantized GetProcessTimes CPU samples; initial report preserved outside repository; longer common batches used here. CPU granularity remains a measurement limitation.",
        "count_coverage": "Executed AST * / // % and simple-name augmented assignments in six new Lab modules plus local stdlib fractions; divmod calls; actual math.gcd C calls; both Fraction __new__ and _from_coprime_ints allocation routes; nearest-even call events. Native bignum internal operations, power/shift internals, libraries outside these modules and full-machine totals are UNAVAILABLE.",
        "full_C1B1_audit_speedup": "NOT AVAILABLE: no independent impulse or physical binding",
        "original_executor_external_compatibility": "NOT VERIFIED",
        "implementation_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in PACKAGE.glob("*.py")},
        "stdlib_fractions_sha256": hashlib.sha256(Path(fractions.__file__).read_bytes()).hexdigest(),
        "instrumented_source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence_directory.glob("*.txt")},
        "rows": rows, "slow_over_fast_median_ratio": ratios}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path), "ratios": ratios, "counts": {k: v["actual_counts"] for k,v in rows.items()}}, indent=2))


if __name__ == "__main__":
    run(Path(sys.argv[1]), Path(sys.argv[2]))
