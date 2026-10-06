# Pre-live fresh internal review: preserved RED and narrow fixes

Fresh reviewer first-pass REQUEST CHANGES: three important implementation
defects, no new numerical contract or architecture proposed. Old controller
and replay source and new RED test source are retained adjacent to this note.

- Prefix revalidation: the immutable checkpoint remains valid but the mutable
  live master prefix was checked only at the next seal. The new RED executed
  body2 after a post-CURRENT mutation. Add existing sealer prefix assertions
  after publication and immediately before LIVE/replay resume.
- Genesis replay-only: the dispatch branch ignored continue_live=False.
  A recording driver demonstrates the unwanted live dispatch. Return the
  already checked pinned genesis without process, object or receipt creation.
- Form source identity: semantic comparison omitted the logical source ID.
  Repaired report hashes hid wrong occurrence/lane/producer/byte coordinates.
  Normalize only the acquisition session prefix in the generated IDs; keep
  state tagging and all logical record/producer/byte coordinates exact.

review-red01: 1 FAIL, 0.5716825540000023s.
review-red02: 9 FAIL / 1 PASS, 1.7228472310000011s.
The same approved ledger records both. Necessary focused GREEN and full
related regression are review-fix validation and use the authorized reserve.
No pre-fix fresh Gala evidence is reused; none had yet been acquired.
V0/Runtime Trace sources/contracts and Tasks1-7 historical evidence remain
unchanged. A final fresh reviewer verdict will follow actual evidence and
exact-final-source regression.
