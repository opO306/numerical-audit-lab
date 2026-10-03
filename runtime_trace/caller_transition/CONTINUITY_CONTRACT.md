# Caller Transition / Error-Continuity contract

## Claim boundary

The contract connects an externally audited regular first-step endpoint to
the prospective input visible at the actual second native step entry.  It is
conditional on the externally audited endpoint Form semantics.  It does not
execute the second step body, import or run a second V2 block, certify a
two-step result, or make trajectory, accumulated-error, physical-accuracy, or
observable-accuracy claims.

Native Gala has no V2 `Form` objects.  The native evidence establishes memory,
control-flow, argument, and write-set facts.  `producer.py` then binds the
already audited offline endpoint dynamic IDs and exact serialized Forms to
the prospective next input.  This binding does not manufacture native Form
execution.

The frozen Form meaning is `computed - true = sum(coef[j] * xi_j) +
[-box, box]` for `K=4` and `xi_j in [-1,1]`.  All six carried lanes preserve
the same externally audited basis namespace and correlation.  They are not
reseeded as independent noise variables.  Coefficient and box strings are
copied exactly from the byte-pinned audited correspondence.

## A–H transformation classification

| Class | Observed status | Components and evidence |
|---|---|---|
| A. pure copy | Used | `q[0:2]`, `full_v[0:2]`, and `latent[0:2]` remain in the same six 8-byte memory lanes. Their first-return and second-entry bits agree and the complete acquired write set has zero overlapping writes. The caller also performs four `save_all` copies to separate output storage; those do not feed the second input. |
| B. rename / rebinding only | Used for ABI naming | The same q/full_v/latent addresses are rebound to the second call's `rcx/r8/r9` argument roles. This does not create a new mathematical state. |
| C. serialization / deserialization | Absent | No carried component is serialized, parsed, packed, or unpacked in this corridor. |
| D. arithmetic transformation | Absent for the six carries | Caller integer loop/address arithmetic exists, but no arithmetic instruction writes any carried byte. |
| E. quantization / rounding | Absent for the six carries | No floating conversion or rounded operation produces a carried lane in the corridor. |
| F. reconstruction | Absent | No carried lane is reconstructed from another representation. |
| G. conditional modification | Absent for the six carries | Branches control `save_all`, loop progression, GIL helpers, and memset paths. The exhaustive executed write set proves none conditionally modifies the six carried lanes in these cases. |
| H. other | Used for non-carries | `gradient` is explicitly zeroed and becomes a fresh exact-zero root; `t` is freshly loaded from schedule index 2; `dt` is freshly loaded as the actual call argument; XMM entry states are fresh captured roots and inherit no prior-step Form identity. |

## Six endpoint bindings

The producer derives the last actual Numeric IR memory writes rather than the
last value merely labelled with a buffer.  The terminal IDs are:

```text
q[0]       v:r227:copy  -> Form-bearing state:v:r227:copy:byte:0
q[1]       v:r251:copy  -> Form-bearing state:v:r251:copy:byte:0
full_v[0]  v:r398:copy  -> v:r396:result -> state:v:r396:result:byte:0
full_v[1]  v:r426:copy  -> v:r424:result -> state:v:r424:result:byte:0
latent[0]  v:r403:copy  -> v:r402:result -> state:v:r402:result:byte:0
latent[1]  v:r431:copy  -> v:r430:result -> state:v:r430:result:byte:0
```

The terminal `full_v` and `latent` COPY IDs are intentionally absent from the
old `state_bindings`; their sources have the audited Forms.  The new evidence
preserves both the memory dynamic ID and this explicit COPY chain.  It does not
invent direct old bindings.

For each lane, acceptance requires all of the following:

- the freshly observed first-step endpoint center equals the selected audited
  terminal memory value;
- the address and center bits at second entry equal the first-return address
  and bits;
- every executed instruction between those boundaries is present, ordered,
  and byte-bound to a pinned ELF;
- every possible write, including stack/call/string/helper writes and
  same-value stores, is recorded with before/after bytes;
- no possible write overlaps the lane;
- the endpoint dynamic ID, explicit COPY source state, exact Form coefficients,
  exact box, and shared basis namespace remain unchanged.

Same center bits alone do not satisfy this contract.

## Fresh non-carry roots

`gradient` is not carried from the old step.  The two actual libc AVX stores
cover all 16 bytes; the second store is also recorded even though it writes
zero over zero.  The second entry observes both binary64 lanes as zero.  Its
new Form is exactly four zero coefficients and zero box.

`t` is a new load of `t[2]` (`0x3fa0000000000000`).  `dt` is an actual memory
load into the second call's `xmm1` (`0x3f90000000000000`).  The capture records
the load instruction, effective address, and source bits for each.  Neither
inherits a prior caller-register Form.  Required XMM entry values are fresh
captured roots.

## Raw evidence and failure behavior

`capture.json` has schema `gala-caller-transition-capture-v1` and includes
process/thread identity, maps, modules, first entry, first return, second
entry, argument-source receipts, single-thread/all-stop configuration, and a
controlled-stop receipt.  `caller_trace.jsonl` is a chained sequence of raw
instruction records.  `execution.json` records the real command, process IDs,
environment, source hashes, and that no package was installed.  The harness
diff is independently recorded.

Acquisition refuses an unregistered module, unsupported opcode or addressing
form, absent ELF correspondence, changed instruction byte, thread change,
oversized string effect, missing time/dt source, wrong ABI, wrong argument
bits, timeout, or instruction limit.  Output directories are created
exclusively.  Failed exploratory directories are never overwritten.

`transition.json` is canonical JSON.  Re-running the producer on the same raw
evidence is deterministic.  `summary.json` is a normal concise receipt and
must not be used instead of the raw evidence.  The later independent checker
must decode the pinned module bytes with GNU objdump and derive the write set
and bindings independently; it must not import this producer decoder.

For Task 2, the accepted producer outputs are the two transitions under
`artifacts/producer-fix-round1/`.  Their `pointer_identity` receipts record the
first-step and second-entry addresses for q, full_v, latent, and gradient.
The older transitions stored directly with each acquisition are immutable,
superseded history and are not checker inputs.
