# Task 7 attack and compatibility submission

Task 7 is complete in unit / real marker-process / saved TEST_ONLY evidence scope. Actual fresh Gala V1 N=3/N=4, replay and Gala controller-death remain unexecuted Task 8 work. No external audit or formal certification is claimed.

Combined final regression: **318 PASS / 0 FAIL / 0 ERROR / 0 SKIP**. Standalone attack rerun: **54 PASS**. New controls: {'PASS': 2, 'STOP': 32, 'REFUSED': 20}. Every expected attack was detected; STOP preserves the exact durable generation and the specified marker boundary.

The initial 51 PASS / 3 FAIL run is preserved. All three failures came from the new test failing to capture strict malformed-token constructor refusal, before resume. See red-01-root-cause.md and red-01-test-source.py. No product bytes/contracts changed and no new architecture conflict was found.

Protected baseline: 7,232 unchanged. Pre-Task7 V1 historical evidence: 287 unchanged. Pre-compatibility history: 152 unchanged. V0 approved 89-file pinset unchanged: `c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3`. Task 4 fixture remains historical TEST_ONLY.

Final V1 source pinset: 40 files, SHA256 `1b8c9d97907b2308b079aefdb6b40c6263b741c3b8c6d4cd136c6b0451e160c5`; all 11 relocated live-chain files plus supervisor, replay and containment are included. The 19 V1 implementation files and the entire 40-file pinset match Task 6 byte-for-byte. The tested combined mirror matches 187 source files.

Additional shared guarded wall: **119.499047652s**. Ledger: **3472.7506255470207/3600s**. Task 8 remainder: **127.24937445297928s**. Same ledger and ceiling; all RED/GREEN/final jobs charged.

Task 8 proposed hard-cap allowance: **400s**, shortfall **272.7506255470207s**. No Task 8 execution. Caps are allocation ceilings, not measured Gala durations. Review/fix/retry reserve is additional and not included. See task8-allowance.json.

## Per-attack results

| Attack/control | Actual verdict | Scope | CURRENT / markers |
|---|---|---|---|
| positive_and_transaction_retry | PASS | TEST_ONLY_CONTROLLER | S3 / [1, 2, 3] |
| post_check_q | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| post_check_full_v | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| post_check_latent | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| post_check_coefficient | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| post_check_box | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| post_check_form_reset | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| post_check_t | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| post_check_source | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| post_check_gradient | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| receipt_reuse | STOP | TEST_ONLY_CONTROLLER | S1 / [1, 2] |
| resume_before_check | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| resume_before_current | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| certified_prefix | STOP | TEST_ONLY_CONTROLLER | S1 / [1, 2] |
| source_change | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| wrong_parent | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| foreign_session | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| skipped_barrier | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| duplicate_barrier | STOP | TEST_ONLY_CONTROLLER | S1 / [1, 2] |
| checker crash | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| checker timeout | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| resource refusal | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| before_current_replace | STOP | TEST_ONLY_CONTROLLER | S0 / [1] |
| after_current_replace_before_token | STOP | TEST_ONLY_CONTROLLER | S1 / [1] |
| after_token_before_resume | STOP | TEST_ONLY_CONTROLLER | S1 / [1] |
| token_foreign | REFUSED | REAL_MARKER_PROCESS_ONLY | forbidden body 2 absent |
| token_checkpoint | REFUSED | REAL_MARKER_PROCESS_ONLY | forbidden body 2 absent |
| token_skipped | REFUSED | REAL_MARKER_PROCESS_ONLY | forbidden body 2 absent |
| token_generation | REFUSED | REAL_MARKER_PROCESS_ONLY | forbidden body 2 absent |
| token_future | REFUSED | REAL_MARKER_PROCESS_ONLY | forbidden body 2 absent |
| token_duplicate | REFUSED | REAL_MARKER_PROCESS_ONLY | forbidden body 3 absent |
| token_unbound | REFUSED | REAL_MARKER_PROCESS_ONLY | forbidden body 2 absent |
| saved_q | REFUSED | TEST_ONLY_SAVED_NUMERICAL_EDGE | SEMANTIC |
| saved_full_v | REFUSED | TEST_ONLY_SAVED_NUMERICAL_EDGE | SEMANTIC |
| saved_latent | REFUSED | TEST_ONLY_SAVED_NUMERICAL_EDGE | SEMANTIC |
| saved_coefficient | REFUSED | TEST_ONLY_SAVED_NUMERICAL_EDGE | SEMANTIC |
| saved_box_reset | REFUSED | TEST_ONLY_SAVED_NUMERICAL_EDGE | SEMANTIC |
| saved_box_increase | REFUSED | TEST_ONLY_SAVED_NUMERICAL_EDGE | SEMANTIC |
| saved_form_reset | REFUSED | TEST_ONLY_SAVED_NUMERICAL_EDGE | SEMANTIC |
| saved_early_body | REFUSED | TEST_ONLY_SAVED_NUMERICAL_EDGE | SEMANTIC |
| saved_tdt_swap | REFUSED | TEST_ONLY_SAVED_NUMERICAL_EDGE | SEMANTIC |
| saved_gradient_omit | REFUSED | TEST_ONLY_SAVED_NUMERICAL_EDGE | SEMANTIC |
| saved_terminal_successor | REFUSED | TEST_ONLY_SAVED_NUMERICAL_EDGE | SEMANTIC |
| replay_latent | STOP | TEST_ONLY_CONTROLLER | S2 / [1] |
| replay_coefficient | STOP | TEST_ONLY_CONTROLLER | S2 / [1] |
| replay_box | STOP | TEST_ONLY_CONTROLLER | S2 / [1] |
| replay_t | STOP | TEST_ONLY_CONTROLLER | S2 / [1] |
| replay_dt | STOP | TEST_ONLY_CONTROLLER | S2 / [1] |
| replay_source | STOP | TEST_ONLY_CONTROLLER | S2 / [1] |
| replay_step | STOP | TEST_ONLY_CONTROLLER | S2 / [1] |
| replay_only_publication_trap | PASS | TEST_ONLY_REPLAY | S2 / [1, 2] |
| replay_acceptance_claim | STOP | TEST_ONLY_CONTROLLER | S2 / [1] |
| altered_stored_certificate | REFUSED | TEST_ONLY_STORE | pointer unchanged; no fresh launch |
| cross_process_without_transition | REFUSED | TEST_ONLY_STORE | S2 / [1, 2, 3] |

Saved numerical mutations use scratch derived copies and independently recompute correspondence after edge/completion hash repair. They retain TEST_ONLY status and confer no LIVE authority. Marker gate injection tests authority sequencing only. The full final suite also re-runs cross-session checkpoint splice, single-link replay attachments, immutable attachment substitution/reuse, prefix/frontier refusal, terminal replay, recovery and paused/active marker containment.

Additional attack coverage in the same 318-case final JUnit (all below passed their explicit assertions):

| Existing authority attack/control | Asserted result | Evidence module |
|---|---|---|
| Foreign-session checkpoint splice; wrong parent/latent parent; changed prefix; wrong next-entry t; omitted gradient | REFUSED | test_live_chain_incremental |
| Repaired acquisition counters | REFUSED at RAW | test_live_chain_incremental |
| Structurally valid stale/future token; foreign/checkpoint/unbound/duplicate token | REFUSED; forbidden next body absent | test_live_chain_session |
| GDB barrier wait before next-body instructions; controller EOF | EOF before body2 marker | test_live_chain_session |
| TEST_ONLY checkpoint presented to production V1Gate | REFUSED before workers | test_verified_driver_v1_controller |
| Attachment missing/partial/foreign parent/session/process; prefix/frontier nonincrease | REFUSED; S2 remains authoritative | test_verified_driver_v1_replay_transition |
| Hash-repaired latent/Form/t/dt/source/step attachment mutation | REFUSED | test_verified_driver_v1_replay_transition |
| Attachment second-child reuse and cross-session without attachment | REFUSED | test_verified_driver_v1_replay_transition |
| Attachment from another historical parent/store | REFUSED; store bytes unchanged | test_verified_driver_v1_replay_transition |
| Attachment bytes substituted after publication | Recovery REFUSED | test_verified_driver_v1_replay_transition |
| Valid narrow transition and idempotent retry | Exactly one Sk+1 object; historical parent retained | test_verified_driver_v1_replay_transition |
| Valid replay then normal subsequent LIVE link | First receipt only contains replay_transition_id | test_verified_driver_v1_replay_transition |
| Transition pre-CURRENT / valid post-CURRENT crash | S2 / S3 recovered; substituted attachment then refuses recovery | test_verified_driver_v1_replay_transition |
| FINAL_TERMINAL replay / transition request | No generation/receipt/attachment changes; LIVE transition refused | test_verified_driver_v1_replay_transition |
| Actual paused/active marker-controller SIGKILL | Process group/descendants terminated; no forbidden forward marker | test_verified_driver_v1_containment |

Git submission: `git-status.txt`, `git-verification.json`, `git-submission.md` and `task7-only-review.diff`. HEAD `fbbb90171c43ed5462e9584c2621cb0b86b80bd4`, branch `codex/runtime-trace`, empty index, tracked `git diff --check` exit 0. No staging/commit/push. The untracked attack-file no-index check has exit 1 for differences against NUL and zero whitespace diagnostic bytes.

Two read-only metadata helper failures were also retained, separately from pytest RED: the finalizer initially confused canonical-map content ID with the approved original pinset file-byte SHA, and the Git helper assumed no-index differences return exit 0. Original helper sources and root-cause notes remain under `red-finalizer-01-*` and `red-git-metadata-01-*`. Corrections match the unchanged gate's file-byte hash and record actual Git status semantics. No existing evidence was overwritten and no product/tested source changed after the final regression.

## Task 8 hard caps

| Run | Seconds |
|---|---:|
| controller_death_active | 15 |
| controller_death_paused | 15 |
| live_N3_positive | 55 |
| live_N4_negative | 60 |
| nonterminal_replay | 45 |
| ordinary_N3_control | 10 |
| post_CURRENT_interruption | 25 |
| terminal_replay | 55 |
| final_regression | 120 |
