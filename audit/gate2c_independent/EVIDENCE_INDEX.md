# Gate 2C independent audit evidence index

현재 상태: **PROVISIONAL PASS / LONG_REGULAR_PREFIX**, independent audit **PENDING**.
먼저 `docs/GATE2C_AUDIT_CHARTER.md`와 charter seal을 읽는다.

## 포함 자료

- frozen Gate 2B fixture 8개 gzip + manifest; compressed/raw SHA-256은 원 manifest에 있다.
- specific gala 1.12.0 wheel과 PyPI JSON: package vendor/ 아래. wheel hash를 직접 다시 확인한다.
  설치·실행하지 않고 확보했다. 서명 체인 검증 PASS를 주장하지 않는다.
- 기존 disassembly.txt와 생성 도구, machine-order 진단 코드/보고서.
- frozen T_bin, BinBound/판정 adapter, runner, 회귀시험, pre-review snapshots.
- 기존 V2는 accepted dependency이며 재감사 대상이 아니다.
- payload/traces/: init 2개 + step_1 2개의 operation trace와 실제 V2 입력.
- payload/exact/: **n0=0 두 개**의 8-step Exact VM producer fixture.
- payload/anchors/: 두 궤도 × n0=0,50000,99992의 **full-state anchor 6개**.
- payload/logs/: 기존 보고서에서 추출한 horizon/cross summary와 saved marks.
- Gate 2C plan/result/report, 기존 plan/closure/result seal, 현재 provisional 상태.
- 복구 Git history bundle 및 복구의 한계를 설명한 provenance 기록.
- package manifest: 각 파일의 raw SHA-256. ZIP과 Git bundle은 외부 delivery metadata에서 추가 확인한다.

## 제공되지 않은 것

- 준비자가 만든 independent checker: **작성하지 않음**. 감사관이 별도 구현한다.
- 신규 감사 verdict: **미수행**. A1–A11을 대신 PASS 처리하지 않는다.
- 전 step V2 forms/bounds/operation log: 원 실행 때 저장되지 않았다.
- 13906 및 13662의 경계 직전 전체 propagation checkpoint: 미보존.
- n0=50000/99992의 실제 historical latent v-half seed 4개: 미보존.
- 따라서 그 네 구간의 historical exact fixture를 임의의 full-state init으로 대체 생성하지 않았다.

감사관은 보존된 initial state/trace contract/frozen fixture에서 별도 구현으로 재구성하거나
해당 증명 의무를 UNRESOLVED로 남긴다. 이 공백을 기존 summary의 주장으로 덮지 않는다.
표본 producer fixture가 맞아도 global horizon 또는 모든 A 의무가 입증되는 것은 아니다.

## 준비 단계의 실행 범위

exporter는 궤도마다 binary init+첫 step, exact 8 step만 실행한다.
fixture 전체 bytes를 읽어 hash/anchor를 추출하지만 100000-step dynamics를 재실행하지 않는다.
기존 보고서를 복사/추출하며 새로운 horizon이나 cross 판정을 계산하지 않는다.
adapter/T_bin/V2 수정과 새 campaign, Gate 2D, V2.1, push는 수행하지 않는다.

exporter 출처: `tools/prepare_gate2c_audit_evidence.py`.
이 파일은 preparation producer이며 독립 decision path가 아니다.
