# Caller Transition / Error-Continuity Gate 외부 독립 감사

- 감사일: 2026-10-03
- 전달물: `caller-transition-error-continuity-43f1e9b.zip`
- 전달 ZIP SHA-256 제시값: `0e7d59f7c43d498cf47e9f8b1f9a04bd5f7051ccfe2fc8a445fb7bcfdb5a26e4`
- 감사 대상 HEAD: `43f1e9b21a014520facb5a545846d648eb67b288`
- 선행 Numeric IR → frozen V2 regular 1-step 감사 상태: CLOSED / PASS

## 최종 판정

**PASS**

`Caller Transition / Error-Continuity Gate`는 현재 정의된 좁은 범위에서 외부 독립 감사로 닫을 수 있다.

상태를 다음과 같이 승격할 수 있다.

```text
Caller Transition / Error-Continuity Gate
CLOSED / PASS
```

이 판정은 정확히 다음 구간에 한정된다.

```text
externally audited first c_leapfrog_step endpoint
    -> actual frozen Gala caller / entered helpers
    -> prospective second c_leapfrog_step entry
```

두 번째 `c_leapfrog_step` 본문 산술, 완성된 2-step 결과, 10/100-step, 장기 누적 오차, 실제 물리/관측량 정확성은 이 감사의 PASS에 포함되지 않는다.

---

## 1. 패키지 / Git provenance

독립 재검증 결과:

- ZIP SHA-256: **일치**
  - `0e7d59f7c43d498cf47e9f8b1f9a04bd5f7051ccfe2fc8a445fb7bcfdb5a26e4`
- ZIP path traversal: 없음
- manifest payload: **2,784 / 2,784** 해시·크기 일치
- manifest 중복/누락: 없음
- Git bundle 복원 HEAD:
  - `43f1e9b21a014520facb5a545846d648eb67b288`
- bundle `git fsck --full --strict`: **PASS**
- snapshot tracked files: **1,488 / 1,488** HEAD Git blob과 byte-identical
- 선행 `34e062d`의 기존 tracked file: 807개
  - 변경: `.gitattributes`, `current/STATUS.md` 두 개
  - 그 외 **805개 불변**
- 복원 worktree: clean

`push/fetch/merge를 하지 않았다`는 과거의 행위 자체는 오프라인 ZIP만으로 독립 증명할 수 없다. 다만 전달 bundle/snapshot의 provenance와 현재 commit ancestry는 일관된다. 이 한계는 Gate correctness blocker로 보지 않았다.

---

## 2. 실제 caller 경로와 범위

두 authoritative acquisition을 확인했다.

- `audited-attempt-05-readproof-01`
- `fresh-closure-fresh-01-readproof-01`

각 캡처는 서로 다른 inferior process이며 같은 machine/boot 환경이다. cross-system 또는 ASLR 다양성 증거로 해석하지 않았다.

두 캡처 모두:

- raw instruction record: **728**
- sequence: `0..727` dense
- sequence 0: 첫 `c_leapfrog_step`의 실제 `ret`
- sequence 727: 두 번째 `c_leapfrog_step`으로 들어가는 실제 `call`
- second-step body recorded instruction: **0**
- controlled stop은 두 번째 함수 entry에서 발생

GDB 로그에서도 첫 호출은 `t=0.015625`, 두 번째 entry는 `t=0.03125`, `dt=0.015625`로 확인되며 q/full_v/latent/gradient pointer가 첫 호출과 두 번째 entry에서 동일하다.

---

## 3. raw instruction과 frozen ELF 독립 결합

프로젝트 checker의 decoder/write-effect 코드를 사용하지 않고 별도 감사 스크립트를 작성했다.

각 raw row에 대해:

1. `module_sha256`에 해당하는 frozen ELF를 직접 해시했다.
2. `file_offset`에서 `instruction_bytes`를 직접 읽어 비교했다.
3. `pc == load_base + elf_address`를 재검산했다.
4. GNU objdump로 frozen ELF를 별도 disassemble하여 trace의 관련 instruction 주소를 다시 decode했다.

결과:

- module hash mismatch: **0**
- raw instruction bytes ↔ ELF mismatch: **0**
- PC/load-base/ELF-address mismatch: **0**
- unique decoded instruction address: **464 / 464** 일치
- decoded primary mnemonic mismatch: **0**

두 캡처의 executed instruction byte sequence는 서로 동일하고 런타임 주소/데이터만 서로 다르다.

---

## 4. complete write-set 독립 재구성

가장 중요한 부분은 implementation의 `possible_memory_writes`를 그대로 믿지 않은 것이다.

별도 감사 스크립트에서:

- frozen ELF를 GNU objdump로 다시 decode
- 각 instruction의 실제 mnemonic/operand를 기준으로 memory-write 가능 여부를 분류
- raw PRE GPR/FS/GS 값을 이용해 effective address를 별도 계산
- write width를 opcode/register width에서 다시 계산

했다.

두 캡처 모두 결과:

| 항목 | 결과 |
|---|---:|
| objdump에서 독립 파생한 write | 111 |
| 저장된 write | 111 |
| write sequence set mismatch | 0 |
| write effective-address mismatch | 0 |
| write width mismatch | 0 |
| same-value write | 21 |
| q/full_v/latent 영역과 write overlap | **0** |

특히 `%fs:` 상대 store 3개도 실제 FS base를 사용해 주소를 재계산했고 누락되지 않았다.

따라서 “같은 endpoint bits를 우연히 다시 관측했다”가 아니라, 취득된 전체 corridor의 실제 write-set 안에서 carried 48 bytes가 수정되지 않았다는 주장이 성립한다.

---

## 5. q / full_v / latent continuity

각 캡처에서:

- q: 2 × 8 bytes
- full_v: 2 × 8 bytes
- latent: 2 × 8 bytes

총 6 lane을 확인했다.

모든 lane에서:

1. first-step entry pointer == second-step entry pointer
2. first-step return bits == second-step entry bits
3. 독립 파생한 111개 write와 lane overlap == 0
4. first-step return bits == 선행 audited Numeric IR endpoint center bits
5. transition이 가리키는 terminal dynamic ID / COPY source가 실제 Numeric IR graph와 일치
6. Form source state / center / exact serialized Form이 선행 audited correspondence와 일치

했다.

선행 correspondence hash도 앞선 외부 독립 감사에서 CLOSED/PASS된 정확한 두 artifact와 일치한다.

- attempt-05 correspondence:
  - `3edd42937e58c7655dc951d3683802ffddd5ae7cbfda27c5793d6cb42c7d35f3`
- closure-fresh-01 correspondence:
  - `a692db2f6f3b5b9a45de71cf8516fef4c8d2cdc8b173c6cdb20259c5812c572f`

따라서 Form carry는 **native Gala가 Form 객체를 실행했다는 주장이 아니라**, 감사된 endpoint의 수학적 의미를 변경되지 않은 동일 center/state에 조건부로 이어 붙이는 계약으로 해석할 때 타당하다.

### 비차단 coverage 한계

이번 regular case의 6개 carried Form은 symbolic coefficient 4개가 모두 0이고 `box`만 nonzero다. 따라서 shared basis namespace 보존 구조는 확인했지만, 실제 nonzero symbolic correlation을 가진 carried Form 사례를 이 Gate 하나가 실험적으로 행사한 것은 아니다. 현재 좁은 regular-case PASS에는 blocker가 아니며, 일반화 주장에 사용해서는 안 된다.

---

## 6. gradient fresh exact-zero root

raw trace에서 실제 경로는 다음과 같다.

- seq 704: `memset` call
- seq 707: `vmovd %esi,%xmm0`
- seq 714: `vmovdqu %xmm0,(%rdi)`
- seq 715: `vmovdqu %xmm0,-0x10(%rdi,%rdx,1)`

독립 재검산 결과:

- seq 714/715 직전 XMM0: 128-bit all zero
- 두 store의 독립 계산 effective address: gradient buffer 시작주소
- width: 16 bytes
- 두 번째 store는 동일 16 bytes에 대한 same-value zero store
- second entry gradient bits: `+0.0, +0.0`

따라서 이전 step의 gradient Form을 carry하지 않고 새 `FRESH_EXACT_ZERO`로 시작한다는 계약은 타당하다.

---

## 7. t / dt fresh roots와 실제 ABI entry

### t

seq 718:

```text
movsd 0x0(%r13), %xmm0
```

별도 EA 계산과 PRE memory observation을 대조했다.

- bits: `0x3fa0000000000000` = 0.03125
- post XMM0 lower64와 일치
- second entry `t_bits`와 일치

### dt

seq 723:

```text
movsd 0x108(%rsp), %xmm1
```

- bits: `0x3f90000000000000` = 0.015625
- post XMM1 lower64와 일치
- second entry `dt_bits`와 일치

둘 다 이번 harness에서 정확히 표현 가능한 dyadic 값이므로 zero-error fresh root 처리와 충돌하지 않는다.

### 최종 두 번째 call

seq 727 직전 ABI를 raw register에서 직접 확인했다.

- `rcx` = q pointer
- `r8` = full_v pointer
- `r9` = latent pointer
- stack argument = gradient pointer
- `xmm0` = t
- `xmm1` = dt
- `next_pc` = second `c_leapfrog_step` entry

그리고 trace에는 해당 entry 이후 body instruction이 없다.

---

## 8. checker 독립성 / 재실행

`runtime_trace/caller_transition/checker.py`의 import graph를 정적 검사했다.

import는 standard library만 사용한다.

- `argparse`
- `copy`
- `dataclasses`
- `hashlib`
- `json`
- `pathlib`
- `re`
- `struct`
- `subprocess`
- `sys`
- `typing`

acquisition / producer / adapter / Form evaluator proof core import는 발견되지 않았다.

현재 checker를 두 authoritative 정상 case에 직접 다시 실행했다.

둘 다:

```text
CHECKER_PASS
```

을 재현했다.

이 재실행 자체를 독립 증명의 전부로 사용하지는 않았으며, 위 write-set/ELF/endpoint 검사는 별도 코드로 수행했다.

---

## 9. mutation / fail-closed

저장된 최종 mutation set은 41종이다.

주요 범위:

- center bits 변경
- 같은 bits / 잘못된 dynamic ID
- component swap / omission / duplication
- stale endpoint
- Form-only 변경
- pointer rebinding
- time / dt provenance 변조
- write 변경 / same-value write 삭제
- gradient zero coverage 축소
- indirect / return source byte 변조
- TLS address 변조
- sequence deletion/reordering
- receipt까지 수리한 deletion/reordering
- MOVSD upper64 semantics
- same-bits wrong ABI origin role
- public coherent repin

최종 generator를 새 exclusive directory에서 다시 실행했다.

- 생성 파일: **367**
- committed evidence 파일: **367**
- file-name set: 동일
- **367 / 367 byte-for-byte 동일**
- 41 cases: 모두 `REFUSED`

전용 101-test suite도 현재 checker source에서 다시 실행하여 PASS를 확인했다.

---

## 10. 테스트 재현

감사 환경에서 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`로 재실행했다.

- Caller 전용: **101 passed**
- `tests`: **250 passed**
- `runtime_trace/tests`: **66 passed**
- `runtime_trace/numeric_ir/tests`: **94 passed**
- `runtime_trace/numeric_ir/v2/tests`: **69 passed**

합계:

```text
580 / 580 passed
```

참고로 처음 한 번에 580개를 실행한 명령은 감사 환경의 실행 제한에 걸려 중간 종료됐다. 이 실행은 PASS로 세지 않았다. 이후 동일 constituent suites를 분리하여 모두 정상 종료시켰다.

---

## 11. 판정 항목

| 항목 | 판정 |
|---|---|
| ZIP / manifest integrity | PASS |
| Git bundle / ancestry / snapshot | PASS |
| 선행 endpoint 연결 | PASS |
| actual caller path 확인 | PASS |
| second-body exclusion | PASS |
| raw instruction ↔ frozen ELF | PASS |
| complete write-set | PASS |
| q/full_v/latent no-write continuity | PASS |
| endpoint bits / dynamic ID / Form binding | PASS |
| gradient fresh exact-zero | PASS |
| t fresh schedule load | PASS |
| dt actual call argument | PASS |
| second-entry ABI | PASS |
| checker structural independence | PASS |
| semantic mutation refusal | PASS |
| dedicated tests | PASS |
| prior suites regression | PASS |

### 열린 finding

- Critical: **0**
- Important: **0**
- Minor: **0**
- Technical UNRESOLVED within claimed scope: **0**

---

## 12. 감사 한계

이 PASS로 다음을 주장하면 안 된다.

1. 두 번째 `c_leapfrog_step` 산술이 Numeric IR/V2로 검증됐다는 주장
2. 완성된 2-step 궤적이 검증됐다는 주장
3. 이 한 번의 caller corridor가 모든 미래 step/모든 스케줄에서 그대로 반복된다는 주장
4. 10/100-step 정확성
5. global accumulated-error bound
6. physical trajectory accuracy
7. observable accuracy
8. cross-system/ASLR diversity
9. package만으로 과거 `push/fetch/merge 없음`을 증명했다는 주장

또한 외부 감사자는 새 native acquisition 자체를 다시 수행하지 않았다. 대신 전달된 두 acquisition의 sealed raw bytes, GDB 로그, frozen ELF, exact source receipts를 독립 재해석했다. 현재 Gate는 두 concrete acquisition에 한정되어 있으므로 이 방식으로 claim을 검증하기에 충분하다고 판정했다.

---

# 결론

현재 evidence는 다음 연결을 닫기에 충분하다.

```text
Audited first-step endpoint
        ↓
actual Gala caller corridor
        ↓
unchanged q/full_v/latent state + preserved audited Form meaning
fresh exact-zero gradient
authenticated new t / dt
        ↓
actual second-step entry
```

따라서:

```text
Caller Transition / Error-Continuity Gate
CLOSED / PASS
```

로 기록할 수 있다.

다음 논리적 단계는 10/100-step이 아니라 **두 번째 `c_leapfrog_step` 자체의 Runtime Trace → Numeric IR → frozen V2 arithmetic을 닫아서 완성된 2-step chain을 최초로 만드는 것**이다.
