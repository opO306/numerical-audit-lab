# Regular 2-Step Chain 독립 재감사 보고서

날짜: 2026-10-04
대상 브랜치: regular-2step-chain
대상 HEAD: e69119e259b862a7d8462c8d61333782ee2747fd

## 최종 판정

**PASS — 단, 감사 계약의 좁은 Regular 2-Step Chain 범위에 한함.**

외부 판정상 상태:
```
Regular 2-Step Chain

IMPLEMENTED
CHECKER PASS
INDEPENDENT AUDIT PASS
```

커밋 내부 문서/chain.json의 `INDEPENDENT AUDIT PENDING` 문자열은 감사 이전에 봉인된 상태이므로 변경하지 않았다.

## 독립 확인 사항

### 1. 전달 ZIP
- bytes: 355,162,217
- SHA-256: 868558e66f72c3344b4e1145812a2c50f6a6ff32749c5f5d718531e92af599e8
- ZIP CRC: 이상 없음
- ZIP entries: 4,885
- PACKAGE_MANIFEST payload members: 4,884
- 차이 1개는 `PACKAGE_MANIFEST.json` 자기 자신
- 4,884 payload 전부 size/SHA-256 전수 대조: mismatch 0
- duplicate member name: 0

### 2. Git / bundle / 원격
- bundle verify: PASS
- bundle complete history: 확인
- 복구 checkout HEAD: e69119e259b862a7d8462c8d61333782ee2747fd
- 복구 checkout clean
- git fsck --strict --full: exit 0
- baseline 43f1e9b21a014520facb5a545846d648eb67b288 -> final HEAD ancestry: PASS
- live ls-remote regular-2step-chain: e69119e259b862a7d8462c8d61333782ee2747fd
- 원래 구현 checkout 현재 HEAD/branch/upstream/origin tracking 일치
- 원래 구현 checkout 현재 ahead/behind 0/0, clean

### 3. 보호된 기존 자산
Git tree를 baseline과 최종 HEAD에서 직접 비교:
- baseline files: 1,488
- 공통 1,488
- 동일 Git blob: 1,487
- 변경된 기존 파일: `.gitattributes` 1개
- 삭제된 기존 파일: 0
- 새 파일: 420

### 4. 공개 checker 재실행
복구 checkout에서 test trust mode 없이 known/fresh를 각각 재실행:
- known: CHECKER_PASS
- fresh: CHECKER_PASS
- 각 case: operation 22 = ADD 7 / SUB 5 / MUL 10
- value 151
- state binding 107
- carry 6
- test_trust_mode=false

### 5. 독립 raw-chain 재구성
프로젝트 checker를 import하지 않는 별도 stdlib checker로:
- 각 trace 1,428 row
- trace SHA 일치
- seq 0..1427 연속
- 모든 row hash-chain 재계산 일치
- capture final_chain 일치
- init [0,191)
- step1 [191,446), 255 rows
- caller [446,1173), 727 rows
- step2 [1173,1428), 255 rows
- step1/step2 module-relative instruction/byte/opcode/kind sequence 동일
- q/full_v/latent: step1 end -> caller start/end -> handoff -> step2 start bits/pointer 연속
- gradient: step1 end -> caller actual zero write -> step2 exact-zero start
- t/dt: 실제 caller PRE read와 source address/operand/bits 연결
- harness output endpoint == step2 q/full_v endpoint
- known/fresh acquisition/process/trace identity 서로 다름

### 6. caller 동적 메모리 주소 독립 검증
이전 정적 검토에서 남겼던 주소 검증 의문을 별도 stdlib checker로 확인:
- known caller rows: 727
- fresh caller rows: 727
- case당 PRE memory read 218개 주소 재계산: mismatch 0
- case당 write 111개 주소 재계산: mismatch 0
- unsupported operand: 0
- q/full_v/latent protected range write overlap: 0
- gradient 16-byte changed write가 기존 bits -> exact zero
- 이어지는 same-zero write도 확인

따라서 이전의 caller-address UNRESOLVED는 해소됨.

### 7. step2 binary64 산술 독립 검증
프로젝트 수치 checker를 사용하지 않고 Python Fraction + 직접 구현한 IEEE-754 binary64 round-to-nearest-even으로 각 case 22개 연산을 재계산:
- known mismatch: 0
- fresh mismatch: 0
- ADD 7 / SUB 5 / MUL 10 전부 exact/RNE 일치

### 8. 테스트
이번 독립 감사에서 Regular 2-Step 전용 테스트 전체를 두 묶음으로 재실행:
- chain + mutation + delivery + portability: 37/37 PASS
- acquisition + structure: 44/44 PASS
- 합계: 81/81 PASS

기존 최종 JUnit도 XML로 별도 파싱:
- final-new: 63, failure/error/skip 0
- final-caller: 101, failure/error/skip 0
- final-regular: 479, failure/error/skip 0
- covering: 37, failure/error/skip 0

고유 testcase ID 합집합:
- 기존 3개 final run: 643
- covering 37 중 중복: 19
- 신규: 18
- 전체 unique inventory: 661

이번 감사에서 661 전체를 다시 실행한 것은 아니다.

### 9. semantic mutation
재실행한 테스트가 새 tmp 디렉터리에서 mutation generator를 다시 실행함.
- repaired semantic class 1..15: 모두 SEMANTIC / REFUSED
- HASH control: REFUSED
- TRUST control: REFUSED
- 단순 저장된 manifest PASS 문자열을 읽은 것이 아님

### 10. source/test map
최종 HEAD의 실제 bytes/SHA/physical-line count를 map과 전수 대조:
- 17 mapped files mismatch: 0
- production Python: 2,972 physical lines
- tests: 1,033 physical lines

## 유지해야 할 제한

1. init return -> step1 entry 구간은 여전히 UNTRACED이다.
2. native carry 6개의 symbolic coefficients는 모두 0이고 box는 nonzero다.
3. nonzero symbolic Form unit test는 존재하지만 native nonzero-coefficient caller coverage를 증명하지 않는다.
4. known/fresh는 별도 실제 process지만 ASLR diversity 증거는 아니다.
5. harness_output의 n_steps=1은 stale metadata다. 대신 harness source bytes는 정확히 한 토큰 `n_steps=1 -> n_steps=2`만 변경됐고, capture에서 실제 native step call 2개를 확인했다.
6. 이 감사는 frozen V2 자체의 수학을 처음부터 재감사하지 않았다. 기존 V2 독립 감사 자산을 antecedent로 두고 새 step2 correspondence와 실제 binary64 산술을 감사했다.
7. N-step, trajectory correctness, accumulated error, shadowing, final observable error, physical accuracy, cross-machine correctness는 이 PASS에 포함되지 않는다.
8. 3-step으로 자동 일반화할 근거는 없다. template/induction은 별도 설계/증명이 필요하다.
9. workflow 5h50m13s, native acquisition 15/5/10, pytest 누적 2206.37s는 봉인된 비용/실행 영수증과 일치함을 확인했지만 시간을 재현 실행한 것은 아니다.

## 독립 감사 소스

- independent_raw_chain_check.py
- independent_caller_ea_check.py
- independent_binary64_check.py
- independent_source_tree_check.py
- independent_junit_check.py
- independent_inventory_check.py

위 파일들은 이 감사 작업 디렉터리에 보존한다.

## 결론

감사 범위 안에서 미해결 correctness blocker나 재현 가능한 반례를 찾지 못했다.
이전 정적 검토의 caller 동적 주소 우려는 독립 주소 재계산으로 해소됐다.

따라서 **Regular 2-Step Chain의 외부 독립 감사 판정은 PASS**다.
