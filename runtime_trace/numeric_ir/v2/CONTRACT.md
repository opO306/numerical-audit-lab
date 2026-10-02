# Numeric IR to frozen V2 regular init plus one-step adapter contract

## Status and scope

The serialized schema name is exactly:

```text
numeric-ir-frozen-v2-regular-1step-v1
```

This adapter covers only the two byte-pinned, independently audited Numeric IR
documents for frozen Gala 1.12.0 regular init plus one step. It maps each IR
`ADD_BINARY64`, `SUB_BINARY64`, or `MUL_BINARY64` occurrence, in original IR
order, to one actual call of the unchanged frozen `lab.v2_bound.step_forms`
operator. It does not cover another IR byte identity, another operation kind,
ten or more steps, a chaotic orbit, a V2 horizon, V2.1, or continuous-physics
validation.

The accepted Numeric IR byte SHA-256 values and their common normalized
semantic SHA-256 are data in `audited_inputs.json`. Counts, graph structure,
values, phases, and operation kinds are always derived from the accepted IR;
they are not audit pins or expected graphs. Relocating an unchanged accepted IR
file does not change acceptance. Any byte change is `REFUSED` rather than being
silently treated as a new audit.

The frozen prerequisite is `lab/v2_bound.py` at LF-normalized SHA-256
`48b91d0c45fd7f62dd09df4db28756e6f82c6bd464a040dc60ac1c924ed99780`,
with `K == 4`, `Form`, and callable `step_forms`. Both the actually imported
module bytes and `<root>/lab/v2_bound.py` bytes must have this identity. When
`root` is omitted, the imported module's repository root is used.

## API and publication

```python
adapt(ir_path: Path, root: Path | None = None) -> dict
adapt_to_directory(ir_path: Path, out: Path, root: Path | None = None) -> dict
```

Refusal raises `AdapterRefused(ValueError)`. `adapt` writes nothing.
`adapt_to_directory` completes adaptation before exclusively creating `out`.
It writes canonical `correspondence.json`, then writes
`completion_report.json` last. An existing `out` raises `FileExistsError` and
is not changed. An ordinary Python exception after directory creation triggers
best-effort removal of the newly created directory. This is not a process-kill,
power-loss, or filesystem-atomicity guarantee. Consumers must require both
files and a valid completion report.

The CLI is:

```text
python -m runtime_trace.numeric_ir.v2.adapter \
  --ir FILE --out NEW_DIRECTORY [--root ROOT]
```

An invalid prerequisite prints one JSON `REFUSED` object to stderr and exits
2. A successful run exits 0.

Canonical JSON is UTF-8 JSON with sorted object keys and separators `,` and
`:` and no trailing newline.

## Correspondence top level

The top-level object has exactly these keys:

```text
schema
source
values
boundaries
state_bindings
operations
```

`values` is the full original Numeric IR `values` array, byte-for-byte equal
as JSON data and in its original order. It is not reduced or rewritten.
`operations` remains in original Numeric IR arithmetic order. The added V2
fields do not replace or mutate any original IR operation field.

### Source object

`source` has exactly:

```text
audited_input_label
numeric_ir_sha256
normalized_numeric_sha256
numeric_ir_schema
numeric_ir_source
frozen_v2
```

`numeric_ir_source` is the full original IR `source` object. `frozen_v2` has
exactly:

```text
module = "lab.v2_bound"
operator = "step_forms"
k = 4
lf_sha256
imported_lf_sha256
requested_lf_sha256
```

All three V2 hashes must equal the frozen identity. The source-specific audit
label, byte hash, diagnostic path, trace hashes, and chains must be excluded by
the later normalized old/fresh comparison. The normalized Numeric IR semantic
identity and frozen V2 protocol remain comparison inputs.

## Scalar state bindings

The adapter builds the exact union of:

1. every operation input 8-byte lane and its complete transitive COPY source
   lanes;
2. every operation result 8-byte lane; and
3. every complete 8-byte lane of every declared boundary value and its
   complete transitive COPY source lanes.

No other lane is serialized. An uncovered, partial, mixed-source, overlapping,
or nonfinite scalar lane is refused. Each current arithmetic operand resolves
through COPY provenance to one complete 8-byte lane; different dynamic value
IDs remain different states even when their raw bits are equal.

`state_bindings` is sorted lexicographically by `(value_id, byte_offset)`, using
Unicode/Python string order and integer offset order. This order is independent
of lazy traversal. Every entry has exactly:

```text
state_id
value_id
byte_offset
width
raw_center_bits
form
binding_kind
source_state_id
producer_ir_sequence
phase
trace_sequence
```

`width` is always 8. `state_id` is exactly
`state:<value_id>:byte:<byte_offset>`. `raw_center_bits` is the exact
lowercase 16-hex-digit binary64 lane supplied by IR. `trace_sequence` remains
null for captured boundaries.

`binding_kind` is `LOAD`, `CONST`, `ZERO`, `COPY`, or
`ARITHMETIC_RESULT`. `LOAD`, `CONST`, and `ZERO` seed `Form([0.0] * K,
0.0)`: CONST is an exact represented-bit prerequisite, not a decimal literal
inferred by this adapter. COPY has exactly one `source_state_id` and carries
that source Form unchanged. An arithmetic result has
`producer_ir_sequence` equal to its IR operation and a null
`source_state_id`.

`form` has exactly `coef` and `box`. `coef` has exactly four strings. Every
coefficient and box is a finite Python `float.hex()` string whose round trip
through `float.fromhex()` returns the same canonical string. Input and output
Forms are therefore serialized by exact binary64 bit value, not decimal
approximation.

## Boundary classification

Every declared Numeric IR producer with role `boundary` has one `boundaries`
entry, in original IR value order, with exactly:

```text
value_id
phase
boundary
producer_kind
classification
trace_sequence
state_ids
```

LOAD boundaries are `CAPTURED_INPUT_ROOT`. Step-phase COPY boundaries are
`CAPTURED_STATE_HANDOFF`; their `trace_sequence` and every boundary slice trace
and operand identity remain null. `state_ids` lists all complete lanes in
ascending byte offset.

The boundary COPY means only that the audited IR declares equality between
captured init endpoint bytes and captured step start bytes and supplies an
abstract state handoff. Carrying a Form across that declared link does not
prove an observed caller copy instruction, the untraced caller's exact
arithmetic, its rounding behavior, or whole-caller error continuity.

Boundary COPY never creates an operation record and is never passed to V2 as
ADD, SUB, MUL, CONST, or another synthetic arithmetic operation.

## Operation record and actual V2 call

Each operation record contains all 16 original IR fields:

```text
ir_sequence trace_sequence module_sha256 elf_address instruction_bytes opcode
operation_kind input0_value_id input1_value_id output_value_id
input0_raw_bits input1_raw_bits output_raw_bits mxcsr phase step
```

and exactly these eight adapter fields:

```text
v2_sequence
v2_operation_kind
input0_state_id
input1_state_id
output_state_id
input0_form
input1_form
output_form
```

`v2_sequence` is dense from zero and equals original `ir_sequence`.
`v2_operation_kind` is the fixed map `ADD_BINARY64 -> ADD`,
`SUB_BINARY64 -> SUB`, `MUL_BINARY64 -> MUL`. No fusion, split, reorder,
CSE, constant folding, algebraic replacement, or extra call is allowed.

For every operation, the actual unchanged V2 call is exactly:

```python
step_forms(
    [(v2_operation_kind,
      output_state_id,
      [input0_state_id, input1_state_id],
      None)],
    {
        input0_state_id: int(input0_raw_bits, 16),
        input1_state_id: int(input1_raw_bits, 16),
        output_state_id: int(output_raw_bits, 16),
    },
    {
        input0_state_id: input0_Form,
        input1_state_id: input1_Form,
    },
)
```

The destination pre-value remains `input0`; the source remains `input1`.
These are occurrence-specific states, not bit-keyed aliases. The operation
record is the V2 call record; there is no separate synthetic call list.

The three integer `regs` values are represented centers supplied by Numeric
IR. Frozen V2 uses them to propagate an affine error Form and local rounding
residual. The adapter does not independently recompute a binary64 output center
and a matching center is not a new certificate of the machine trace or V2
mathematics.

## Validation and refusal

Parsing rejects duplicate JSON object keys. All booleans, integers, strings,
nulls, arrays, and objects are checked by exact JSON/Python type; Python's
`bool`/`int` equality and integral floats are never accepted as integer fields.
The adapter validates exact IR object keys, raw widths, finite binary64 lanes,
dense and increasing occurrence order, unique value and trace identities,
operation/result coverage, producer roles, operation/input/output occurrence
identity, raw-bit agreement, complete slice bounds, no destination-slice
overlap, slice byte equality, no dangling or temporal-forward edge, boundary
null traces, and normalized semantic hash integrity before execution.

Unknown operations, unsupported producer kinds, duplicate IDs, malformed
types, missing values, reordered operations, wrong producers, root resets,
mixed scalar lanes, raw mismatch, nonfinite state, altered frozen V2, absent V2
output, or invalid V2 Form are `REFUSED`. Refusal occurs before publication.

## Completion report

`completion_report.json` is written last and has exactly:

```text
schema = "numeric-ir-frozen-v2-adapter-report-v1"
verdict = "ADAPTED"
correspondence_sha256
source_numeric_ir_sha256
source_normalized_numeric_sha256
operation_count
state_binding_count
boundary_count
```

All counts are derived from the completed output. `ADAPTED` means this adapter
ran the unchanged frozen operator and published the correspondence. It does not
mean independent checker PASS, independent audit closure, long-trajectory
soundness, or physical certification.
