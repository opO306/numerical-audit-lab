# Finalizer assertion correction; no product change

The first read-only finalizer stopped at its own pinset hash assertion.
It compared the content ID of a reserialized map with the approved SHA of
the original pinset file bytes. V0 gate.py explicitly uses the file bytes
at lines 54-56. Those are different serializations and therefore different
hashes. Windows paths also require slash normalization solely for comparing
the file map.

Diagnostic: current runtime map has exactly 89 files and equals the original
approved JSON map. Original file SHA remains
`c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3`.
The protected 7,232-file inventory and combined 318-case regression had
already passed. No product failure or new source namespace entry was found.

Preserved `red-finalizer-01-source.py` retains the failed metadata checker.
Minimal correction: require exact 89-entry map equality and the original
pinset file-byte SHA, matching the unchanged V0 gate. Re-run the finalizer;
the tested product and attack source bytes are unchanged.
