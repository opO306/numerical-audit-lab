# Preserved Task 7 RED and minimal test correction

`task7-attacks-01` ran 54 cases: 51 passed, 3 failed, no errors/skips.
The unchanged product rejected skipped/generation/future tokens in
`ResumeToken.__post_init__` with `token generation/sequence mismatch`.
The new test incorrectly placed `dataclasses.replace` outside its expected
refusal block. The traceback reaches no session resume call in those cases.

The initial exact test source is preserved in `red-01-test-source.py`; the
JUnit, stdout and guarded execution receipt retain all three failures.
Working foreign/checkpoint cases constructed valid token representations and
placed the session refusal inside the block. Comparing those paths and the
strict generation/sequence constructor identifies a test boundary error.

Minimal correction: include malicious construction and resume inside the
refusal block, require the exact constructor error for these three malformed
tokens, record the refusal phase, and still require the forbidden next body
marker to be absent. No product source or contract is changed. The corrected
attack suite must pass before the full combined regression is accepted.
