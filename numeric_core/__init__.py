"""A-Numeric VM: the reference meaning of A's arithmetic.

docs/current/A_NUMERIC_EXECUTION_STACK_V1.md. Not an executor of worlds --
executors (C++, CUDA, ...) are judged against it.
"""
from .profiles import Binary64Finite, Exact, FixedPoint, VMHalt, VMRejected
from .vm import (ANVM_VERSION, IMPLEMENTATION_DIGEST, OPCODES, SPEC, SPEC_HASH, Branch, Instr, RunResult,
                 program_digest, run, validate)

__all__ = ["Binary64Finite", "Exact", "FixedPoint", "VMHalt", "VMRejected", "ANVM_VERSION", "IMPLEMENTATION_DIGEST",
           "OPCODES", "SPEC", "SPEC_HASH", "Branch", "Instr", "RunResult", "program_digest", "run", "validate"]
