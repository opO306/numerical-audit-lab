# Frozen Gala native caller source path

This gate is limited to the frozen regular case and the actual native path
observed by the two new `n_steps=2` processes.  It stops at the second
`c_leapfrog_step` entry, before that function executes an instruction.

## Pinned sources and binaries

- Harness antecedent:
  `runtime_trace/harness.py`, SHA-256
  `4928f88e4c6255cfbc3f68798648b543146fb5b13327490d331814f778a9fc26`.
- New harness:
  `runtime_trace/harness_nsteps2.py`, SHA-256
  `a9125c7199a73e11dde7780ab833e44d444122b3c7c49e297ea1ea2155777c99`.
  Its bytes equal the antecedent after exactly one replacement,
  `n_steps=1` to `n_steps=2`, in the `integrate_orbit` call.  The old
  completion metadata still says `n_steps: 1`; it cannot execute because the
  debugger terminates the inferior at the second native entry.
- Frozen wheel:
  `audit/gate2c1/vendor/gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl`,
  SHA-256 `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0`.
- Audited Cython source:
  `audit/gate2c1/vendor/gala/integrate/cyintegrators/leapfrog.pyx`,
  SHA-256 `001e8ebf19a55c8a52690e905cbe9c2d62bf3418d844551dc85a6294d6206e17`.
- Actual loaded native caller:
  `gala/integrate/cyintegrators/leapfrog.cpython-312-x86_64-linux-gnu.so`,
  SHA-256 `a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc`.
- Actual nested helpers: packaged Python 3.12 executable ELF
  `e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f`
  and frozen libc
  `3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf`.
  `frozen_modules/manifest.json` resolves these hashes without reopening a
  captured absolute path.

The wheel member `gala/potential/hamiltonian/chamiltonian.pyx` lines 315–328
select the Cython route when `c_enabled` and `cython_if_possible` are true and
call `leapfrog_integrate_hamiltonian(self, arr_w0, t,
save_all=save_all)`.  In the audited `leapfrog.pyx`, that function computes
`dt = t[1]-t[0]`, allocates `grad_v` and `v_jm1_2`, copies `w0` to `tmp_w`,
calls `c_init_velocity`, and enters `for j in range(1, ntimes, 1)`.

For each loop iteration the source order is:

1. `grad_v[:] = 0.`
2. `c_leapfrog_step(cp, n, half_ndim, t[j], dt, q, full_v, latent, gradient)`
3. if `save_all`, copy each `tmp_w[k, i]` to `all_w[k, j, i]`
4. increment/branch the loop and repeat.

The acquired native route is therefore:

```text
Hamiltonian.integrate_orbit
  -> leapfrog_integrate_hamiltonian
  -> c_init_velocity
  -> c_leapfrog_step(j=1)
  -> actual RET
  -> Cython caller plus entered Python/libc helpers
  -> save_all copies
  -> gradient zeroing
  -> t[2] load and dt load
  -> c_leapfrog_step(j=2) entry (controlled stop)
```

Each capture has 728 executed records.  Sequence 0 is the actual first-step
`ret`; sequences 1–726 cover the caller and all entered helpers; sequence 727
is the actual call instruction whose next PC is the second-step entry.  The
full instruction addresses, ASLR load bases, ELF virtual/file offsets, bytes,
AT&T decode, pre/post GPR/XMM/MXCSR/EFLAGS, flow, and possible memory-write
effects are in `caller_trace.jsonl`.  Maps and the entry ABI are in
`capture.json`.

The old `runtime_trace/artifacts/attempt-05` and `closure-fresh-01` captures
end after one native step and contain no such continuation.  They are endpoint
antecedents only.  The two caller captures are new processes linked to those
antecedents; they are not historical continuation records.
