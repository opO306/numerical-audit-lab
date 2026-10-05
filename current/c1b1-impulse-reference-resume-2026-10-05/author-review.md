# Fresh author-side final review

Reviewer: final_reference_review, read-only; no implementation changes and no second review. This is NOT an independent implementation audit.

Important 1: direct Fraction comparisons in Interval validation, even-power extrema, refinement and rounding bypassed checked cross-products. Small reproduction at bit_max=20 returned 490/59989 .. 474/56153 and reported peak17 while comparison allocated 25-bit products. Fix: context-bearing interval construction, accounted exact comparisons/negations/rounding/refinement. Regression test_constructor_cross_products_precharged stops BIT before the product.

Important 2: later Acquisition/Budget/Atom closed keys and decimal lexemes were checked after earlier conversions. The acquisition.extra probe saw12 conversions before refusal. Fix: all closed shapes and decimal syntax/digit bounds checked in a complete first pass; input and independent adapter conversion only in second pass. Conversion-call spies now see0 for late malformed fields.

Minor deferred: adapter cap-checks V2 exp order but does not recompute its exact deterministic n_R(t) schedule. PREPARED_ONLY and blocked invoke prevent a false recheck/publication claim. This limitation is disclosed in the author report.

Read by reviewer: request/progress in full, all impulse Python source, impulse test/support sources, mutant runner, pinned semantic/package/policy/wire/domain/identity/lineage/status docs; all91 constant key/role/exact-rational records. External publication provenance not freshly checked. Only small reviewer probes were newly executed; full suite/mutants/preservation receipts belong to the root author run.

Declined to judge, ruled outside current stage: production platform allocator/OS enforcement; V2 nonlinear ACCEPTED soundness; acquisition authenticity/executor comparison; physical accuracy/J verification/certification; all-input finite-budget success/convergence; drift/KDK/trajectory/replay/Arithmetic integration. Root independently verifies final test logs and protected/history bytes, neither attributed to reviewer.

Status of review: both Important findings fixed via recorded RED->GREEN regressions; Minor deferred. No independent review PASS is claimed.
