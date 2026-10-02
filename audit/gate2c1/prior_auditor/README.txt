Gate 2C independent audit checker artifacts

Included:
- g2c_independent.py
  Chaotic independent checker / machine-order T_bin reconstruction / V2 propagation / cross-bound checks.
- g2c_regular.py
  Regular-orbit independent checker intended for the 100,000-step run. The full run did not complete in the audit session.
- g2c_windows.py
  Independent exact 8-step checks for the six requested windows.
- g2c_independent_results.json
  Saved chaotic-run results, including first_h=13907, first_cross=13663, first_inf_bin=13953, first_inf_lab=13735 and boundary data.

Not available / not created during the audit:
- Full regular-run results JSON
- Saved stdout/stderr logs for the regular run
- Saved stdout logs for the 8-step checker
- cProfile / py-spy / tracemalloc profiling outputs
- Per-function timing/call-count or Fraction operand-bit-length profiling

Therefore these files are sufficient to inspect and rerun the independent checker logic, but not sufficient by themselves to establish the exact runtime cost cause of inverse/Fraction arithmetic.
