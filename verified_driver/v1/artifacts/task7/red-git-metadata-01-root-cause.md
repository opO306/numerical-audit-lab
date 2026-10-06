# Read-only Git metadata exit-code correction

The metadata helper initially assumed no-index diff --check returns 0 for
an entirely new file against NUL. The actual read-only call returns 1 for
differences present, with zero diagnostic bytes. The normal tracked
git diff --check returns 0. There are no whitespace diagnostics.

Preserved red-git-metadata-01-source.py records the wrong helper assertion.
Only the helper expectation/report is corrected to record actual exit 1
and zero diagnostics for no-index mode. Existing output files are retained
byte-for-byte and re-read for equality; no index, source, ledger or product
change is performed. The 318-case regression remains on unchanged bytes.
