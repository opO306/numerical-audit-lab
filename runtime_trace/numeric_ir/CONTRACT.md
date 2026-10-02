# Runtime Trace Numeric IR regular 1-step v1 contract

## Scope and authority

The serialized schema name is exactly:

```text
runtime-trace-numeric-ir-regular-1step-v1
```

This format is a mechanical representation of the audited frozen Gala regular
init plus one leapfrog step. It is not a general x86 IR, a V2 input, a physical
certificate, or a long-trajectory result. Every `ADD_BINARY64`, `SUB_BINARY64`,
or `MUL_BINARY64` operation corresponds to one dynamic scalar FP instruction
occurrence. There is no fusion, CSE, reordering, constant folding, or algebraic
rewrite.

Translation reads only `trace.jsonl`, its sibling `capture.json`, the packaged
module manifest, and packaged ELF files. It must not read
`audit/gate2c1/machine_mapping.json`, any `T_bin`, or V2 data. The current
translator uses the already-audited raw-only helpers
`verify_linkage`, `disassembly_for_rows`, and `verify_flow` from
`runtime_trace.correspondence`; it never calls `correspondence.check()`.

## APIs

```python
translate(source: Path, root: Path | None = None) -> dict
translate_to_directory(source: Path, out: Path, root: Path | None = None) -> dict
```

`source` may name an artifact directory, `trace.jsonl`, or `capture.json`.
`root` names the repository/package root. When omitted it is discovered by
walking upward to `runtime_trace/frozen_binaries/manifest.json`.

`translate` returns an in-memory document and writes nothing.
`translate_to_directory` translates first, then exclusively creates `out` and
writes `numeric_ir.json` followed by `conversion_report.json`. Existing `out`
raises `FileExistsError`. A refused conversion raises
`ConversionRefused(ValueError)` before `out` is created. Ordinary Python
exceptions during publication trigger best-effort cleanup of the newly reserved
directory.

This is not an OS-level atomic publication guarantee. Abrupt process or system
termination can leave an incomplete directory, including `numeric_ir.json`
without a report. `conversion_report.json` is deliberately published last as
the completion marker. Readers must require both files and accept the directory
as successful only when the report has `verdict: CONVERTED` and its source and
normalized hashes agree with `numeric_ir.json`.

The module CLI is:

```text
python -m runtime_trace.numeric_ir.translator \
  --source PATH --out NEW_DIRECTORY [--root ROOT]
```

A refusal exits 2 and prints one JSON object with `verdict: REFUSED` and an
explicit `reason` to stderr.

## Top-level document

The top-level object has exactly these keys:

| key | type | meaning |
|---|---|---|
| `schema` | string | Exact schema name above. |
| `source` | object | Raw-source integrity and conversion metadata. |
| `operations` | array | Dynamic arithmetic occurrences in trace order. |
| `values` | array | Producer-occurrence values and byte provenance. |

`source` has exactly:

| key | type | meaning |
|---|---|---|
| `capture_schema` | string | Must be `gala-regular-1step-runtime-trace-v1`. |
| `trace_sha256` | string | SHA-256 of the exact `trace.jsonl` bytes. |
| `final_chain` | string | Verified terminal raw-record hash-chain value. |
| `record_count` | integer | Full machine-record count. |
| `scalar_fp_count` | integer | Count derived from scalar ADD/SUB/MUL records. |
| `module_sha256s` | array[string] | Sorted packaged module identities used by the capture. |
| `regions` | array[object] | `phase`, `start_seq`, `end_seq`, `start_state`, `end_state`, and `mxcsr` for init then step. Runtime pointers are omitted. |
| `normalized_numeric_sha256` | string | SHA-256 of `canonical_json(normalized_document(document))`. |
| `diagnostic` | object | `source_path` and `runtime_addresses_excluded_from_normalization: true`. Excluded from normalized comparison. |

## Arithmetic operations

Every operation object has exactly these 16 keys:

```text
ir_sequence
trace_sequence
module_sha256
elf_address
instruction_bytes
opcode
operation_kind
input0_value_id
input1_value_id
output_value_id
input0_raw_bits
input1_raw_bits
output_raw_bits
mxcsr
phase
step
```

`ir_sequence` is dense from zero over arithmetic occurrences only.
`trace_sequence` is the unique full-trace record sequence. `module_sha256`,
`elf_address`, `instruction_bytes`, and `opcode` bind the operation to the
packaged ELF occurrence. `operation_kind` is one of `ADD_BINARY64`,
`SUB_BINARY64`, or `MUL_BINARY64`.

AT&T trace operands are `source,destination`. Numeric IR uses:

```text
input0 = destination pre-value
input1 = source value
output = observed destination post-value
```

For example, trace sequence 139 is serialized as:

```json
{
  "ir_sequence": 9,
  "trace_sequence": 139,
  "module_sha256": "a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc",
  "elf_address": 88385,
  "instruction_bytes": "f20f590d175a0200",
  "opcode": "mulsd",
  "operation_kind": "MUL_BINARY64",
  "input0_value_id": "v:r139:arithmetic-destination-pre-read",
  "input1_value_id": "v:r139:o0:const",
  "output_value_id": "v:r139:result",
  "input0_raw_bits": "0x3f90000000000000",
  "input1_raw_bits": "0x3fe0000000000000",
  "output_raw_bits": "0x3f80000000000000",
  "mxcsr": 8096,
  "phase": "init",
  "step": 0
}
```

The checker must take the exact identity fields from the source record and
independently decode the packaged ELF bytes. It must not accept the recorded
`kind`, `opcode`, origins, or operation order without reconstruction.

## Values

Every value object has exactly these seven keys:

```text
value_id
producer_kind
raw_bits
width
producer
storage
source_slices
```

`width` is a positive byte count. `raw_bits` has exactly `2 + 2*width`
lowercase hexadecimal characters including `0x`; it is the conventional
integer rendering of the underlying little-endian byte sequence used by the
trace. Bit equality is never value identity.

`producer_kind` is one of:

| kind | meaning |
|---|---|
| `LOAD_BITS` | Explicit captured ABI buffer or XMM boundary source. |
| `CONST_BITS` | A read occurrence whose bytes are verified against a packaged ELF SHA-256 and file offset. |
| `COPY_BITS` | A move, stack transfer, arithmetic input read, or cross-region state copy with byte-slice edges. |
| `ZERO_BITS` | Actual observed zero creation: zero-fill, integer self-XOR, literal zero, GPR zero extension, or XMM zero upper lanes. |
| `ARITHMETIC_RESULT` | The unique output of one arithmetic occurrence. Its input edges are the operation's two value IDs. |

`source_slices` is empty for roots, zeros, constants, and arithmetic results.
For `COPY_BITS`, only destination bytes covered by slices have established
numeric provenance. `raw_bits` still records the full observed copy result;
uncovered bytes do not become numeric roots and cannot satisfy a later scalar
input.

### Producer objects and value IDs

Boundary producers have exactly:

```json
{
  "role": "boundary",
  "phase": "init or step",
  "boundary": "q, full_v, latent, gradient, xmm0, or xmm1",
  "trace_sequence": null,
  "operand_index": null
}
```

Their IDs are `v:boundary:<phase>:<boundary>`.

ELF constant read producers have `role`, `trace_sequence`, `operand_index`,
`phase`, `module_sha256`, and `file_offset`; IDs are
`v:r<seq>:o<operand>:const`.

Record-produced values always have `role`, `trace_sequence`, `operand_index`,
and `phase`. Arithmetic result producers additionally have `operation_kind`.
Record IDs are occurrence-based, including:

```text
v:r<seq>:copy
v:r<seq>:zero
v:r<seq>:integer-zero
v:r<seq>:zero-extend
v:r<seq>:zero-upper
v:r<seq>:o<operand>:literal-zero
v:r<seq>:arithmetic-destination-pre-read
v:r<seq>:arithmetic-source-read
v:r<seq>:result
```

An arithmetic read is its own occurrence identity even when both operands
refer to the same prior value or have equal bits. An ELF constant read is also
occurrence-specific. Therefore equal zero results at trace sequences 104 and
105 have different output value IDs.

### Storage objects

Every storage object has exactly:

```json
{
  "space": "...",
  "name": "...",
  "byte_offset": 0,
  "width": 8
}
```

Supported spaces are:

| space | normalized `name` and offset |
|---|---|
| `buffer` | `q`, `full_v`, `latent`, or `gradient`; byte offset from captured ABI buffer base. |
| `register` | Canonical `vN` vector or full GPR name; byte offset within canonical register. |
| `stack` | Phase name; signed byte offset from that phase's captured entry RSP. |
| `elf` | Module SHA-256; ELF file byte offset. |
| `memory-occurrence` | `<phase>:r<seq>:o<operand>` anchor for non-buffer, non-stack process memory; no process address is serialized. |
| `instruction` | `r<seq>:o<operand>` for an immediate literal. |
| `control` | `r<seq>:o<operand>` for a code-address operand. |

Runtime PCs, load bases, PIDs, process memory addresses, module paths, and
absolute stack addresses are never serialized into operations or values.

The four 16-byte buffer ranges must be pairwise disjoint in each region. A
memory operand that intersects a buffer range must fit completely inside
exactly one buffer. Multiple intersections or a partial intersection are an
ambiguous boundary alias and refuse conversion.

### Source-slice objects

Every source slice has exactly:

```text
value_id
source_offset
destination_offset
width
trace_sequence
source_operand_index
source_storage
destination_storage
```

Offsets and width are byte units. `value_id` names the prior producer.
`source_offset` indexes that producer value. `destination_offset` indexes the
current COPY value. The two storage objects are the exact normalized ranges.
For instruction copies, `trace_sequence` and `source_operand_index` identify
the consuming copy/read occurrence. For an init-to-step boundary edge they are
both null because the edge is the captured phase transition rather than an
instruction.

The 16-byte `movapd` at sequence 348 is represented by two slices: low 8 bytes
from `v:r345:copy` and high 8 bytes from `v:r345:zero-upper`. This preserves the
actual partial-width load plus XMM-zero-upper behavior rather than inventing a
single 16-byte load.

The `vmovd` at sequence 298 produces `v:r298:copy` for its 4 copied bytes and a
separate value:

```json
{
  "value_id": "v:r298:zero-upper",
  "producer_kind": "ZERO_BITS",
  "raw_bits": "0x000000000000000000000000",
  "width": 12,
  "producer": {
    "role": "zero_upper",
    "trace_sequence": 298,
    "operand_index": 1,
    "phase": "step"
  },
  "storage": {
    "space": "register",
    "name": "v0",
    "byte_offset": 4,
    "width": 12
  },
  "source_slices": []
}
```

## Phase-boundary contract

At init entry, `q`, `full_v`, `latent`, `gradient`, `xmm0`, and `xmm1` are
explicit `LOAD_BITS` captured boundaries.

At step entry:

- `q`, `full_v`, and `latent` are `COPY_BITS` values whose slices point to the
  actual init endpoint producers, after exact endpoint/start-bit equality is
  checked. These edges are captured phase-boundary state links. They are not
  observed copy instructions and do not prove that out-of-capture caller code
  performed no same-bit writes.
- `gradient` is a new scratch `LOAD_BITS` boundary even when its bits happen to
  equal the earlier gradient bits.
- `xmm0` and `xmm1` are new declared caller boundary `LOAD_BITS` values.

Caller setup between init and step is outside the capture. No between-region
computation or whole-caller execution provenance is inferred; the distinct
step boundary value IDs preserve the new phase-boundary occurrence identity.

## Normalization

Canonical JSON is UTF-8 JSON with sorted object keys and separators `,` and
`:` with no added whitespace. `normalized_document(document)` returns exactly:

```json
{
  "schema": "runtime-trace-numeric-ir-regular-1step-v1",
  "operations": [],
  "values": []
}
```

with the actual operation/value arrays. The entire `source` object is excluded
because it contains raw-trace hashes, chain endpoints, and a diagnostic path.
Producer identities, operation order, normalized storage, and byte-slice edges
are not erased. The `normalized_numeric_sha256` is SHA-256 over that canonical
byte string.

Translator-produced old/fresh hash equality is a preliminary deterministic
conversion result. It is not the independent checker result; the independent
checker must reconstruct this normalized form and every edge from the two raw
sources separately.

## Refusal requirements

Before emitting IR, translation verifies decoded capture/row/region object
shape and integer ranges, raw trace hash and hash chain, capture completeness,
exact sequence and region linkage, pairwise-disjoint 16-byte boundary ranges,
region-entry `rcx`/`r8`/`r9`/`rsp` and `xmm0`/`xmm1` availability, canonical
pre/post register availability and capacity for every register operand,
the complete canonical GPR set derived from `runtime_trace.semantics.GPRS` in
every pre/post context (alias keys such as `eax` are not required),
pre/post machine state linkage, supported instruction forms, scalar widths,
finite inputs and results, MXCSR controls, packaged module hashes, executable
mapping, ELF instruction bytes and independent decode, effective addresses,
copy/zero results, scalar arithmetic results, origin agreement with
reconstructed byte state, buffer endpoints, and init-to-step state linkage.

Any missing or ambiguous scalar byte producer, unknown opcode/form, raw-bit or
width mismatch, sequence defect, nonfinite scalar, unsupported MXCSR, module
failure, or alias disagreement raises `ConversionRefused` with a reason. An
unknown observed GPR or memory byte is never promoted to a numerical root.

## Conversion report

`conversion_report.json` has exactly:

```text
schema = runtime-trace-numeric-ir-conversion-report-v1
verdict = CONVERTED
source_trace_sha256
normalized_numeric_sha256
operation_count
value_count
```

This report is moved into the output directory after `numeric_ir.json` and is
the completion marker. A directory without both files is incomplete and must
not be treated as a successful conversion.
