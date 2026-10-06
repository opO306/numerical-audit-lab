# Task 6 replay-to-live transition question

Task 5 namespace compatibility is complete. This document is a proposed Task 6 change, not implemented authority behavior or an acceptance receipt.

The approved design requires a new process to reproduce stored S1..Sk from genesis, without publication, then permits LIVE continuation from a reproduced NEXT_STEP_ENTRY. Existing `ChainStore._link` rejects any change in session/process between successive generations and compares the old process's trace prefix lengths/frontier directly. Existing `validate_edge` also correctly requires the predecessor and new edge to belong to the same fresh session and prefix. Consequently a new process cannot use the historical Sk object directly as its live predecessor, and normal publication of fresh Sk+1 is rejected. Namespace relocation does not solve this separate Task 6 interface conflict.

Proposed resolution: an explicit, persisted replay transition attachment, available only after complete replay verification through the current authoritative Sk.

- Keep every historical state object, acceptance receipt and CURRENT byte unchanged during replay.
- Compare each fresh edge's q/full_v/latent, six Form roles/centers/coefficients/boxes, K=4 no-reseed basis contract, gradient, t/dt, requested scope, barrier kind, step, source binding and stored lineage position. Ignore only fresh process/session/acquisition namespace/prefix identities. Reject nonzero cross-process Form coefficients, consistent with the design's limited zero-coefficient scope.
- Preserve raw verification's strict same-process carry and prefix checks by using the actual fresh replay predecessor for numerical checking. Bind its logical position separately to stored Sk; never pass old process pointers into a fresh process.
- The transition attachment must bind current stored Sk ID, validated replay checkpoints/checker reports for every replayed boundary, exact fresh Sk observation, fresh session/process/source/prefix/frontier, and the strict live token binding. It grants no publication or arbitrary state-injection authority by itself.
- Only the first newly certified Sk+1 after replay may use that attachment. Its receipt must bind historical Sk as predecessor and the verified fresh replay carry. Recovery must revalidate the attachment when checking the new chain link; an absent, partial, substituted, stale or mismatched attachment refuses.
- Normal live links keep the current same-session/process and increasing-prefix rules. LIVE tokens remain single-use and bound to the fresh session/barrier/checkpoint and the current authoritative state; no general cross-session exception.
- FINAL_TERMINAL replay performs verified exit handling only, cannot transition to LIVE and cannot create another generation.

Required evidence before completing this change: replay creates zero store objects/receipts/generations; latent/Form/t/dt/source/step/lineage mismatches refuse; unauthenticated cross-session publication still refuses; valid replay continuation publishes exactly one new generation; substituted/reused transition attachments refuse; terminal replay cannot launch a successor body; full Tasks 1–6 and V0 regression pass. All tests initially use explicit TEST_ONLY marker sessions. Actual Gala replay and controller-death evidence remain Task 8 work under the existing shared budget.

Alternative safe behavior is recovery to verified Sk with STOP/paused state only, leaving replay-to-LIVE continuation unimplemented. That alternative does not complete the currently approved Task 6 specification.
