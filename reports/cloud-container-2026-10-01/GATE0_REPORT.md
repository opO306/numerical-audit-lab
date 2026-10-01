# Gate 0 결과 보고서

- 전체 판정: **INCOMPLETE (open items below)**
- deterministic_digest: `2d05505d3c499f0c3ac94970b35dfd7258f1fc2913c3b9ecbbb871f36158aa98`
- 실행 환경: {'system': 'Linux', 'release': '6.18.44-fc-v50', 'machine': 'x86_64', 'python': '3.11.15', 'mpmath': '1.3.0', 'cpu_count': 4}
- 총 시간: 19.5초

## 합격 조건

| 조건 | 결과 |
|---|---|
| G0-1 | PASS |
| G0-2 | PASS |
| G0-3 | PASS |
| G0-4 | PASS |
| G0-5 | PASS |
| G0-6 | NOT_JUDGED_HERE (designer's home-PC run decides; compare deterministic_digest) |
| G0-7 | RECORDED (not a pass/fail criterion) |

벤치마크 3: gendot_n50_c1e25_v1: frozen fixture generated once by the published GenDot algorithm (Ogita-Rump-Oishi 2005, Alg. 6.1), designer-approved 2026-10-01

남은 일:

- G0-6: designer's home-PC run with matching deterministic_digest
- GenDot generator is the implementer's reconstruction (paper unreachable from the build environment); designer to diff against Algorithm 6.1. Affects the fixture's name only, not its oracle or verdicts

봉인 이후 변경(감사 기록):

- docs/AUDIT_POST_SEAL_ORACLE_TOLERANCE.md: oracle cross-check tolerance rule replaced after a REFUSED on Muller; Rump restored to the original rule; regression tests in tests/test_post_seal_audit.py

## rump

oracle = `-54767/66192` ≈ -0.82739605994682137

oracle을 정한 서로 다른 방법:

- literature: `-54767/66192`
- direct_rational: `-54767/66192`
- mpmath_200_digits: `-0.8273960599468213681411651`

### rump / sequential (알려진 함정)

| 프로필 | 기준 대상 | 값 | 멈춤 | 판정 | 단계 감사(거부/전체) |
|---|---|---|---|---|---|
| binary64 | 예 | -1.1805916207174113e+21 | None | INVALID | 0/26 |
| exact | 예 | -0.82739605994682137 | None | VALID | 0/26 |
| FX(64,32) | 참고 | None | [3, 'overflow'] | REFUSED | 0/3 |
| FX(128,96) | 참고 | None | [3, 'overflow'] | REFUSED | 0/3 |
| FX(256,64) | 참고 | -0.82739605994682137 | None | VALID | 0/26 |
| FX(256,192) | 참고 | None | [4, 'overflow'] | REFUSED | 0/4 |

일부러 넣은 오답·불일치:

| 주입 | 기대 | 결과 | OK |
|---|---|---|---|
| host and calculator round the oracle to the same binary64 | True | True | ✔ |
| claim: correctly rounded oracle | VALID | VALID | ✔ |
| claim: oracle + 1 ulp | INVALID | INVALID | ✔ |
| claim: oracle - 1 ulp | INVALID | INVALID | ✔ |
| claim: exact oracle | VALID | VALID | ✔ |
| claim: exact oracle + 1e-40 | INVALID | INVALID | ✔ |
| claim: halted run (no value) | REFUSED | REFUSED | ✔ |
| oracle: 'literature' shifted by 1e-40 | REFUSED | REFUSED | ✔ |
| oracle: high-precision angle shifted by 1e-100 relative | REFUSED | REFUSED | ✔ |
| oracle: only one exact derivation | REFUSED | REFUSED | ✔ |
| binary64 steps: every step nudged +-1 unit is rejected (52/52) | True | True | ✔ |
| exact steps: every step nudged +-1 unit is rejected (52/52) | True | True | ✔ |

참고 정보:

```
{
  "mpmath_precision_sweep (same evaluation order)": {
    "24_bits": "-6.338253001141147e+29",
    "53_bits": "-1.1805916207174113e+21",
    "64_bits": "5.7646075230342349e+17",
    "113_bits": "1.1726039400531786",
    "128_bits": "-0.82739605994682137"
  }
}
```

### rump / sum (알려진 함정)

| 프로필 | 기준 대상 | 값 | 멈춤 | 판정 | 단계 감사(거부/전체) |
|---|---|---|---|---|---|
| binary64 | 예 | -1.3906120635277419e+21 | None | INVALID | 0/24 |
| exact | 예 | -0.82739605994682137 | None | VALID | 0/24 |
| FX(64,32) | 참고 | None | [3, 'overflow'] | REFUSED | 0/3 |
| FX(128,96) | 참고 | None | [3, 'overflow'] | REFUSED | 0/3 |
| FX(256,64) | 참고 | -0.82739605994682137 | None | VALID | 0/24 |
| FX(256,192) | 참고 | None | [4, 'overflow'] | REFUSED | 0/4 |

일부러 넣은 오답·불일치:

| 주입 | 기대 | 결과 | OK |
|---|---|---|---|
| host and calculator round the oracle to the same binary64 | True | True | ✔ |
| claim: correctly rounded oracle | VALID | VALID | ✔ |
| claim: oracle + 1 ulp | INVALID | INVALID | ✔ |
| claim: oracle - 1 ulp | INVALID | INVALID | ✔ |
| claim: exact oracle | VALID | VALID | ✔ |
| claim: exact oracle + 1e-40 | INVALID | INVALID | ✔ |
| claim: halted run (no value) | REFUSED | REFUSED | ✔ |
| oracle: 'literature' shifted by 1e-40 | REFUSED | REFUSED | ✔ |
| oracle: high-precision angle shifted by 1e-100 relative | REFUSED | REFUSED | ✔ |
| oracle: only one exact derivation | REFUSED | REFUSED | ✔ |
| binary64 steps: every step nudged +-1 unit is rejected (48/48) | True | True | ✔ |
| exact steps: every step nudged +-1 unit is rejected (48/48) | True | True | ✔ |

참고 정보:

```
{
  "mpmath_precision_sweep (same evaluation order)": {
    "24_bits": "-6.338253001141147e+29",
    "53_bits": "-1.1805916207174113e+21",
    "64_bits": "5.7646075230342349e+17",
    "113_bits": "1.1726039400531786",
    "128_bits": "-0.82739605994682137"
  }
}
```
## muller

oracle = `2328306745375394431036/465661390253305305137` ≈ 4.9999995578522583

oracle을 정한 서로 다른 방법:

- closed_form: `2328306745375394431036/465661390253305305137`
- direct_rational: `2328306745375394431036/465661390253305305137`
- mpmath_400_digits: `4.999999557852258305867636`

### muller / recurrence (알려진 함정)

| 프로필 | 기준 대상 | 값 | 멈춤 | 판정 | 단계 감사(거부/전체) |
|---|---|---|---|---|---|
| binary64 | 예 | 100.0 | None | INVALID | 0/121 |
| exact | 예 | 4.9999995578522583 | None | VALID | 0/121 |
| FX(64,32) | 참고 | 100.0 | None | INVALID | 0/121 |
| FX(128,96) | 참고 | 100.00039026246617 | None | INVALID | 0/121 |
| FX(256,64) | 참고 | 100.00000000000009 | None | INVALID | 0/121 |
| FX(256,192) | 참고 | 4.9999995578522583 | None | INVALID | 0/121 |

일부러 넣은 오답·불일치:

| 주입 | 기대 | 결과 | OK |
|---|---|---|---|
| host and calculator round the oracle to the same binary64 | True | True | ✔ |
| claim: correctly rounded oracle | VALID | VALID | ✔ |
| claim: oracle + 1 ulp | INVALID | INVALID | ✔ |
| claim: oracle - 1 ulp | INVALID | INVALID | ✔ |
| claim: exact oracle | VALID | VALID | ✔ |
| claim: exact oracle + 1e-40 | INVALID | INVALID | ✔ |
| claim: halted run (no value) | REFUSED | REFUSED | ✔ |
| oracle: 'closed_form' shifted by 1e-40 | REFUSED | REFUSED | ✔ |
| oracle: high-precision angle shifted by 1e-100 relative | REFUSED | REFUSED | ✔ |
| oracle: only one exact derivation | REFUSED | REFUSED | ✔ |
| binary64 steps: every step nudged +-1 unit is rejected (242/242) | True | True | ✔ |
| exact steps: every step nudged +-1 unit is rejected (242/242) | True | True | ✔ |

참고 정보:

```
{
  "exact run equals closed form at every n <= 30": true,
  "binary64 first n with |error| > 1e-3": 11,
  "binary64 x_n at n = 10, 15, 20, 25, 30": {
    "10": "4.9879092327957864",
    "15": "168.93916767106458",
    "20": "100.00001247862016",
    "25": "100.00000000000389",
    "30": "100.0"
  },
  "mpmath x_30 by precision": {
    "53_bits": "100.0",
    "113_bits": "98.241698648006385",
    "200_bits": "4.9999995578522583",
    "300_bits": "4.9999995578522583"
  }
}
```
## gendot

oracle = `1797396946548930006824725877263/20282409603651670423947251286016` ≈ 0.088618511393504469

oracle을 정한 서로 다른 방법:

- exact_fraction: `1797396946548930006824725877263/20282409603651670423947251286016`
- exact_integer: `1797396946548930006824725877263/20282409603651670423947251286016`
- mpmath_fdot_300_digits: `0.08861851139350446851023229`

### gendot / naive (알려진 함정)

| 프로필 | 기준 대상 | 값 | 멈춤 | 판정 | 단계 감사(거부/전체) |
|---|---|---|---|---|---|
| binary64 | 예 | -1834782720.0 | None | INVALID | 0/199 |
| exact | 예 | 0.088618511393504469 | None | VALID | 0/199 |
| FX(64,32) | 참고 | None | [3, 'overflow'] | REFUSED | 0/3 |
| FX(128,96) | 참고 | None | [3, 'overflow'] | REFUSED | 0/3 |
| FX(256,64) | 참고 | 0.088618511393504469 | None | INVALID | 0/199 |
| FX(256,192) | 참고 | None | [105, 'overflow'] | REFUSED | 0/105 |

일부러 넣은 오답·불일치:

| 주입 | 기대 | 결과 | OK |
|---|---|---|---|
| host and calculator round the oracle to the same binary64 | True | True | ✔ |
| claim: correctly rounded oracle | VALID | VALID | ✔ |
| claim: oracle + 1 ulp | INVALID | INVALID | ✔ |
| claim: oracle - 1 ulp | INVALID | INVALID | ✔ |
| claim: exact oracle | VALID | VALID | ✔ |
| claim: exact oracle + 1e-40 | INVALID | INVALID | ✔ |
| claim: halted run (no value) | REFUSED | REFUSED | ✔ |
| oracle: 'exact_fraction' shifted by 1e-40 | REFUSED | REFUSED | ✔ |
| oracle: high-precision angle shifted by 1e-100 relative | REFUSED | REFUSED | ✔ |
| oracle: only one exact derivation | REFUSED | REFUSED | ✔ |
| binary64 steps: every step nudged +-1 unit is rejected (398/398) | True | True | ✔ |
| exact steps: every step nudged +-1 unit is rejected (398/398) | True | True | ✔ |

참고 정보:

```
{
  "fixture_sha256": "b9c971502f5d96a3afb043a0748de34e82ac899d0b999569815b057a0bce5582",
  "exact condition number C = 2*sum|x_i*y_i| / |x.y|": "3.61004e+26",
  "generator-reported condition number": "3.610040e+26",
  "generator d judged against the Lab's exact oracle": "VALID",
  "host float64 naive loop bit-identical to calculator binary64 naive": true,
  "product exponent span (bits)": 189
}
```

### gendot / vm_dot (명세상 정답이어야 함)

| 프로필 | 기준 대상 | 값 | 멈춤 | 판정 | 단계 감사(거부/전체) |
|---|---|---|---|---|---|
| binary64 | 예 | 0.088618511393504462 | None | VALID | 0/101 |
| exact | 예 | 0.088618511393504469 | None | VALID | 0/101 |
| FX(64,32) | 참고 | None | [3, 'overflow'] | REFUSED | 0/3 |
| FX(128,96) | 참고 | None | [3, 'overflow'] | REFUSED | 0/3 |
| FX(256,64) | 참고 | 0.088618511393504469 | None | VALID | 0/101 |
| FX(256,192) | 참고 | 0.088618511393504469 | None | VALID | 0/101 |

일부러 넣은 오답·불일치:

| 주입 | 기대 | 결과 | OK |
|---|---|---|---|
| host and calculator round the oracle to the same binary64 | True | True | ✔ |
| claim: correctly rounded oracle | VALID | VALID | ✔ |
| claim: oracle + 1 ulp | INVALID | INVALID | ✔ |
| claim: oracle - 1 ulp | INVALID | INVALID | ✔ |
| claim: exact oracle | VALID | VALID | ✔ |
| claim: exact oracle + 1e-40 | INVALID | INVALID | ✔ |
| claim: halted run (no value) | REFUSED | REFUSED | ✔ |
| oracle: 'exact_fraction' shifted by 1e-40 | REFUSED | REFUSED | ✔ |
| oracle: high-precision angle shifted by 1e-100 relative | REFUSED | REFUSED | ✔ |
| oracle: only one exact derivation | REFUSED | REFUSED | ✔ |
| binary64 steps: every step nudged +-1 unit is rejected (202/202) | True | True | ✔ |
| exact steps: every step nudged +-1 unit is rejected (202/202) | True | True | ✔ |

참고 정보:

```
{
  "fixture_sha256": "b9c971502f5d96a3afb043a0748de34e82ac899d0b999569815b057a0bce5582",
  "exact condition number C = 2*sum|x_i*y_i| / |x.y|": "3.61004e+26",
  "generator-reported condition number": "3.610040e+26",
  "generator d judged against the Lab's exact oracle": "VALID",
  "host float64 naive loop bit-identical to calculator binary64 naive": true,
  "product exponent span (bits)": 189
}
```

## A에서 옮겨 온 hard-case·mutant 시험

`{'command': '-m pytest -q -p no:cacheprovider tests/test_ported_hard_cases.py', 'returncode': 0, 'counts': {'passed': 21}}`

## 독립성

`{'static_violations': [], 'A_modules_loaded_at_runtime': []}`

## 비용 (기록만, 합격 기준 아님)

| 벤치마크 | 프로그램 | 프로필 | 시간(초) | Python 힙 peak(바이트) | 연산 수 |
|---|---|---|---|---|---|
| rump | sequential | binary64 | 0.0012 | 15047 | 26 |
| rump | sequential | exact | 0.0009 | 11703 | 26 |
| rump | sequential | FX(64,32) | 0.0007 | 11817 | 4 |
| rump | sequential | FX(128,96) | 0.0006 | 11850 | 4 |
| rump | sequential | FX(256,64) | 0.0010 | 11858 | 26 |
| rump | sequential | FX(256,192) | 0.0005 | 11787 | 5 |
| rump | sum | binary64 | 0.0010 | 11063 | 24 |
| rump | sum | exact | 0.0007 | 11047 | 24 |
| rump | sum | FX(64,32) | 0.0005 | 11137 | 4 |
| rump | sum | FX(128,96) | 0.0004 | 11178 | 4 |
| rump | sum | FX(256,64) | 0.0007 | 11202 | 24 |
| rump | sum | FX(256,192) | 0.0005 | 11139 | 5 |
| rump | (oracle 확정) | — | 0.0003 | — | — |
| muller | recurrence | binary64 | 0.0043 | 61639 | 121 |
| muller | recurrence | exact | 0.0028 | 60479 | 121 |
| muller | recurrence | FX(64,32) | 0.0021 | 60553 | 121 |
| muller | recurrence | FX(128,96) | 0.0022 | 60562 | 121 |
| muller | recurrence | FX(256,64) | 0.0024 | 60586 | 121 |
| muller | recurrence | FX(256,192) | 0.0021 | 60579 | 121 |
| muller | (oracle 확정) | — | 0.0009 | — | — |
| gendot | naive | binary64 | 0.0091 | 98034 | 199 |
| gendot | naive | exact | 0.0074 | 98002 | 199 |
| gendot | naive | FX(64,32) | 0.0042 | 98052 | 4 |
| gendot | naive | FX(128,96) | 0.0044 | 98109 | 4 |
| gendot | naive | FX(256,64) | 0.0076 | 98133 | 199 |
| gendot | naive | FX(256,192) | 0.0062 | 98070 | 106 |
| gendot | vm_dot | binary64 | 0.0062 | 55538 | 101 |
| gendot | vm_dot | exact | 0.0064 | 55530 | 101 |
| gendot | vm_dot | FX(64,32) | 0.0032 | 55548 | 4 |
| gendot | vm_dot | FX(128,96) | 0.0044 | 55557 | 4 |
| gendot | vm_dot | FX(256,64) | 0.0054 | 55581 | 101 |
| gendot | vm_dot | FX(256,192) | 0.0058 | 55574 | 101 |
| gendot | (oracle 확정) | — | 0.0013 | — | — |

Python 힙 peak는 tracemalloc 값이다. 프로세스 전체 메모리(RSS)가 아니다.
