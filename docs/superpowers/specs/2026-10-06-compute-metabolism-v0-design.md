# Compute Metabolism V0 — Written Design Spec

작성일: 2026-10-06 (Asia/Seoul)

**Status: DESIGNER APPROVED DESIGN / NOT IMPLEMENTED / NOT BENCHMARKED**

설계자 승인 대상은 대화에서 확정한 설계 1/4~4/4이다. 이 문서는 그 설계를 통합한 written spec이며, **2026-10-06 대화에서 설계자가 이 written spec을 최종 승인했다**. 다음 단계는 implementation plan 작성이며, 그 plan의 설계자 승인 전에 제품 코드, warm-up, benchmark 또는 campaign 실행을 시작하지 않는다.

| 상태 영역 | 현재 상태 |
| --- | --- |
| Conversational design 1/4~4/4 | DESIGNER APPROVED |
| 본 written spec | DESIGNER APPROVED |
| Compute Metabolism wrapper | NOT IMPLEMENTED |
| Compute Metabolism warm-up / benchmark | NOT RUN / NOT BENCHMARKED |
| GCP 준비 단계 | 기존 준비 evidence에서 PASS_ENVIRONMENT_PREPARATION_ONLY |
| GCP에서 640 MiB writer 상한의 충분성 | NOT TESTED |
| Compute Metabolism V0 completion | NOT ESTABLISHED |

## 1. 목적과 비목적

현재 Verified Driver V1의 고정된 Gala N=3 workload를 준비된 GCP VM에서 실행하고, OS CPU envelope만 바꿨을 때의 correctness outcome, CPU 비용, wall, memory, throttle 및 V1 단계별 timing을 측정한다. CPU, wall, memory 등을 하나의 fitness score로 합치지 않는다.

승인된 A안은 동일 V1 소스, 동일 Gala, 동일 checker, 동일 numerical/verification contract, 동일 입력과 N=3을 유지한다. CPU profile별로 계산 전략, worker/checker 구성, verification 강도 또는 timeout을 바꾸지 않는다.

비목적은 N=10/N=100 확장, 성능 최적화, role parallelism, 멀티코어 전략 변경, adaptive strategy, neural network, evolutionary search, 새 fitness 함수, V1 계약 변경이다. 기존 replay 또는 controller-death 실험을 이 campaign에 추가하지 않는다. 실제 전력/Joule 효율을 측정하는 실험도 아니다.

## 2. V1 read-only baseline과 source binding

문서 작성 시 확인한 Git 기준선:

| 항목 | 값 |
| --- | --- |
| Branch | `codex/runtime-trace` |
| HEAD | `b986c4e7306101c01257d2dfab72e856d67e6ebe` |
| Baseline worktree | `C:/Users/zun24/.codex/worktrees/runtime-nstep/numerical-audit-lab-recovered-2026-10-01` |
| V1 source pinset | 40개; `verified_driver/v1/live_chain/` 11개 포함 |
| Approved V1 source binding | `f75980706aefbbd68cddce09549695c2f633905e01185f92f96660db81a9e2cd` |
| V0 approved 89-file pinset 파일 SHA-256 | `c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3` |

V1 제품 소스, V0 gate·89-file pinset·source binding 의미, Runtime Trace 기존 계약, Task 4 TEST_ONLY fixture, Task 8과 그 이전 역사 evidence를 수정하지 않는다. 승인된 source binding은 기존 `live_source_snapshot()`의 canonical source map에 대한 binding이다. wrapper를 그 map에 넣거나 V1 source universe를 재정의하지 않는다.

Task 8의 historical CURRENT, store objects, acceptance receipts, checkpoint 또는 session은 새 실험의 live authority로 사용하지 않는다. 이전 PASS를 새 GCP run에 소급 적용하지 않는다.

정적 비교 reference로 허용되는 historical 정보는 승인된 source binding과 N=3 final public bits 및 그 provenance이다. `reference.json`은 이를 historical reference라고 표시하고 원본 locator와 hash를 기록한다. 이것이 새 run의 V1 ACCEPT나 checker PASS를 대신하지 않는다.

## 3. GCP execution environment identity

GCP가 primary experiment environment이다. 아래는 **저장된 준비 완료 snapshot**이며, 본 문서 작성 과정에서 VM을 실행하거나 현재 상태를 재검증했다는 뜻이 아니다. 실제 campaign은 warm-up 및 각 attempt 전후에 live invariant를 다시 확인해야 한다.

| 항목 | 준비 기준 |
| --- | --- |
| Project | `project-a2e66968-df2f-43a4-a77` |
| Zone | `us-south1-b` |
| Instance | `instance-20260925-221723` |
| Instance ID | `1987831758054968318` |
| VM | GCP N2 custom, 12 vCPU / 12 GiB configured RAM |
| 준비된 사용자 공간 rootfs | `/home/zun24/compute-metabolism-v0-prepared-20261006/rootfs` |
| V1 rootfs 내부 source root | `/workspace` |
| Python executable, rootfs 내부 | `/home/otherside123/venvs/gate2c1-trace/bin/python` |
| Python | `3.12.3 (main, Aug 31 2026, 10:18:26) [GCC 13.3.0]` |
| V1용 GDB | Ubuntu `15.1-1ubuntu1~24.04.1`, embedded Python 3.12.3 |
| 사용자 공간 | 원본 Ubuntu binaries, glibc 2.39 |
| 준비 당시 host kernel | `6.12.107+deb13-cloud-amd64` |
| System manager | systemd `257.13-1~deb13u1`, cgroup v2 |

VM host의 Debian GDB 16.3 / embedded Python 3.13.5와 host Python 3.13.5는 준비된 V1용 GDB/Python의 대체품으로 사용하지 않는다. GCP 하드웨어와 커널은 원래 WSL2 환경과 다르다. 원본 사용자 공간 재현을 host environment 전체의 동일성으로 표현하지 않는다.

| 원본 binary | SHA-256 |
| --- | --- |
| Python 3.12.3 | `e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f` |
| GDB 15.1 | `3832cc070ae1716e322105d3b39fb398695e5f031c9d39224cf227a8c2b889f6` |
| libc | `3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf` |
| libm | `fce00b6f25f459cf4ae0b7fae4257909a1a8a86f9149e7c029a5d617baf1ccd0` |
| Gala leapfrog extension | `a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc` |
| Original Gala wheel | `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0` |

준비된 Python distributions:

| Package | Version | Package | Version |
| --- | --- | --- | --- |
| Gala | 1.12.0 | NumPy | 2.5.3 |
| SciPy | 1.18.1 | Astropy | 8.0.1 |
| Cython | 3.3.0 | PyYAML | 6.0.3 |
| Pygments | 2.21.0 | astropy-iers-data | 0.2026.9.28.0.59.37 |
| iniconfig | 2.3.0 | mpmath | 1.3.0 |
| packaging | 26.3 | pip | 24.0 |
| pluggy | 1.6.0 | pyerfa | 2.0.1.5 |
| pytest | 9.1.1 | — | — |

준비 evidence는 재현 자산 8,992개 차이 0, 원본 Gala의 짧은 GDB launch, 자기 소유 프로세스 attach/detach, TEST_ONLY V1 model/protocol 42 PASS를 기록한다. 이는 **GCP의 N=3 live V1 성공 또는 benchmark 검증이 아니다**.

준비 자료 위치: `C:/Users/zun24/.codex/visualizations/2026/10/06/01a10fe0-8e9a-7033-913a-5fe8f4eb351f/compute-metabolism-v0-environment-preparation/`. `summary.json`, `execution-environment.json`, 원본/보충 identity manifest를 environment provenance로 사용한다. 준비된 rootfs 자체의 bytes는 campaign retained evidence에 포함하지 않는다.

## 4. CPU profiles와 동일 조건

| Profile | guest logical CPU set | `cpuset.cpus.effective` | `cpu.max` |
| --- | --- | --- | --- |
| 2C | 0,1 | `0-1` | quota `max`, unlimited |
| 1C | 0 | `0` | quota `max`, unlimited |
| 0.5C equivalent | 0 | `0` | **`50000 100000`** |

준비 당시 socket0/core0은 CPU0,6의 sibling pair이고 socket0/core1은 CPU1,7의 sibling pair이다. 따라서 CPU0,1은 **guest topology에서 서로 다른 core ID**이다. host physical core의 독점이나 다른 tenant와의 분리를 주장하지 않는다.

모든 profile에 동일하게 적용할 조건:

| 조건 | 값 |
| --- | --- |
| `MemoryMax` | 4 GiB = 4,294,967,296 bytes |
| `MemorySwapMax` | 0 |
| `OMP_NUM_THREADS` | 1 |
| `OPENBLAS_NUM_THREADS` | 1 |
| V1 writer reservation | 640 MiB/run |
| Per-run outer wall ceiling | 180초 |
| 입력 / ordinary measured workload | 동일 regular Gala 입력, dt=1/64, N=3 |
| 실행 방식 | 순차 실행; attempt 간 overlap 없음 |

N=1 warm-up은 별도 비채점 attempt이다. profile 간 timeout이나 verification 설정을 다르게 주지 않는다. 0.5C를 성공시키기 위해 quota 또는 timeout을 늘리지 않는다.

## 5. System transient unit architecture

새 wrapper의 system guard는 preflight에서 검증된 **sudo system transient unit** 경로를 사용한다. 기존 `runtime_trace.regular_nstep.resources.run_guarded()`는 `--user` transient unit을 사용하므로 이 실험의 엄격한 cpuset 강제 경로로 재사용하지 않는다. 기존 함수는 수정하지 않는다.

구조는 외부 guard/control layer와, profile이 강제된 하나의 system-unit process tree로 나뉜다. 제한되는 tree는 V1 controller, GDB, 하나의 persistent Gala inferior, producer 및 independent checker를 포함한다. worker가 별도 process session을 만들더라도 같은 제한 cgroup 안에 있어야 한다. numerical work나 worker를 quota 바깥으로 우회시키지 않는다.

준비된 rootfs를 `RootDirectory`와 API filesystem 접근을 갖춘 system unit에서 사용한다. 작업 UID1000/GID1003과 준비된 Python/GDB를 유지하고, V1 source·설치 사용자 공간·historical reference는 읽기 전용으로 사용한다. 새 store와 run evidence, writer quota counter 및 wrapper outputs는 별도 writable namespace를 사용한다.

guard는 V1 numerical 실행을 허용하기 전에 실제 cgroup의 effective cpuset, quota, memory 및 swap 제한을 확인해야 한다. 명령 성공이나 요청한 systemd property만으로 enforcement PASS를 만들지 않는다. 실행 중 및 terminal snapshot에서도 설정과 process-tree 귀속을 확인한다. cpuset 표현은 semantic CPU set으로 비교하되 raw 문자열도 보존하고, 0.5C의 quota/period는 정확히 `50000 100000`이어야 한다.

system-unit startup부터 termination/reap 완료까지 outer deadline과 누적 wall 과금을 적용한다. timeout/STOP 시 소유한 unit/process tree 전체에 V1 numerical body 진행 권한이 남지 않아야 한다. 기존 V1 containment·session·barrier 계약을 약화하지 않는다.

terminal cgroup counters와 peak memory를 수집하기 전에 unit/cgroup이 사라져서는 안 된다. 수집 실패를 0 비용이나 성공으로 처리하지 않는다. 실제 enforcement, process-tree containment, final counters 보존은 **향후 구현이 입증해야 할 설계 요구사항**이며 이 문서에서 구현 완료로 선언하지 않는다.

## 6. Trust/source 경계와 wrapper 계층

승인된 별도 계층의 예정 구조:

```text
compute_metabolism/
  v0/
    profiles.py
    system_guard.py
    run_v1.py
    campaign.py
    analyze.py
    tests/
    artifacts/
```

이 트리는 **구조 설계이며 아직 생성하거나 구현하지 않았다**.

| 계층 | 책임과 권한 |
| --- | --- |
| 기존 V1 | numerical acquisition, producer/checker, checkpoint, receipt 검증, atomic CURRENT, token/session/barrier binding |
| 새 `run_v1` | production `ChainStore`, `VerifiedChainDriver`, `V1Gate` 사용; fresh attempt 실행과 원본 결과 수집 |
| 새 system guard | OS envelope, run별 writer quota 제공, outer deadline, containment, cgroup measurements와 구조화된 guard receipts |
| 새 campaign | 실행 순서, 상위 resource ledger, STOP, 반복/완료 판정 |
| 새 analysis | raw records를 보존한 채 CV와 profile별 비교 ratios 생성 |

wrapper 소스는 `runtime_trace/` 및 `verified_driver/v1/` 밖에 둔다. wrapper에 별도의 source manifest/version identity를 기록한다. V1 source binding과 wrapper binding은 다른 필드로 유지하며 wrapper identity가 V1 acceptance authority를 대체하지 않는다.

Task 8 `workflow/live_runs.py`를 새 runner로 복사하거나 재사용하지 않는다. Task 8의 test/negative/replay/death helpers, gate substitution, session substitution을 measured path에 가져오지 않는다. wrapper가 checker를 건너뛰거나 acceptance receipt/CURRENT/token을 자체 발급하지 않는다.

신뢰 전제에는 OS/systemd/GDB의 실행 진실성, 기존 V1의 승인된 numerical/verification 전제 및 새 guard/계측의 올바름이 있다. wrapper의 판정은 독립적으로 검증된 V1 판정과 OS receipt에 의존하며, 새 wrapper만으로 formal certification 또는 외부 audit closure를 만들지 않는다.

## 7. Fresh attempt 규칙

warm-up과 모든 measured attempt는 각각 다음을 새로 만든다.

- 고유 run ID 및 존재하지 않는 exclusive output directory.
- fresh store와 generation0 genesis.
- fresh V1 session 및 새 Gala process identity.
- run별 writer quota counter와 guard receipt namespace.

이전 attempt의 CURRENT, Sk, live process, checkpoint, receipt, resume token, replay transition을 다음 attempt에 넘기지 않는다. profile 변경은 이전 tree의 종료/reap와 outcome·budget 기록이 끝난 뒤에만 수행한다. failed attempt도 ID와 evidence를 남기며 같은 output에 다시 실행하지 않는다.

V1 source root, store 및 run path는 기존 `no_alias`·namespace separation 계약을 만족해야 한다. measured run은 production driver의 기존 S0→S1→S2→S3 publication/resume 순서를 그대로 따른다.

## 8. Correctness admission gate

N=3 measured attempt를 성능 비교에 넣으려면 아래 모두를 새 run evidence로 확인해야 한다.

| 조건 | 요구 결과 |
| --- | --- |
| Source | 승인된 V1 source binding 일치; 실행 중 drift 없음 |
| V1 result | `ACCEPT` |
| Generation / step | generation3, step_index3 |
| Lineage | fresh S0→S1→S2→S3, 즉시 predecessor/receipt/checkpoint 연결 일치 |
| Terminal | S3 `FINAL_TERMINAL` |
| Independent edge checks | step1,2,3 각각 hash-bound `CHECKER_PASS`, LIVE role |
| Numerical bodies | body markers `[1,2,3]`, body4 없음 |
| Persistent process | body1~3에서 동일한 하나의 Gala inferior identity |
| Publication barrier | Sk의 atomic CURRENT publication 전에 body(k+1) 미실행 |
| Reference | 아래 ordinary N=3 reference와 final binary64 public bits 일치 |
| Experiment eligibility | environment/profile/budget integrity 유지; wrapper의 resource/STOP 조건 없음 |

Approved N=3 final public bits, 순서 고정:

```text
0x3f87fdfd0828277f
0x3f77fdfb883c273f
0x3fcff6ed62825295
0x3fbff6e3e3c24415
```

원본 reference provenance는 Task 8 `ordinary-02/harness_output.json` 및 실제 certified `positive-03/SUMMARY.json`과 해당 source pinset이다. 새 campaign의 `reference.json`은 정적 reference의 locator/hash를 보존한다. 새 ordinary benchmark나 추가 reference run을 이 spec에 자동 추가하지 않는다.

작은 wall/CPU 수치나 동일 q/v만으로 correctness admission을 대신하지 않는다. latent/Form/t-dt, full continuation, native trace/prefix/frontier, session/process/step 및 generation binding 검증은 기존 V1이 그대로 수행한다.

V1 원본 outcome과 wrapper/campaign outcome을 분리한다. 예를 들어 V1 ACCEPT 후 retained threshold를 넘으면 원본 ACCEPT evidence를 그대로 남기지만 그 attempt는 wrapper `REFUSED_RESOURCE: EVIDENCE_GROWTH`이며 성능 비교 대상이 아니다.

## 9. Measurement 계약

### 9.1 Cgroup raw metrics

attempt별 actual cgroup identity, unit identity, snapshot 시간과 함께 최소 다음을 수집한다.

| 영역 | Raw fields |
| --- | --- |
| CPU | `usage_usec`, `user_usec`, `system_usec` |
| Quota/throttle | `nr_periods`, `nr_throttled`, `throttled_usec` |
| Enforcement | `cpuset.cpus.effective`, `cpu.max`, effective memory/swap limits |
| Memory | cgroup `memory.peak`, `memory.current`, 관련 `memory.events`/OOM 관측 |
| Identity | cgroup path/epoch identity, unit, VM instance ID, boot_id, run/session/source |

before와 after의 원본 counters 및 동일 cgroup epoch에서의 delta를 둘 다 보존한다. CPU seconds의 권위값은 **`delta usage_usec / 1,000,000`**이다. counter reset, cgroup 대체, 음수 delta 또는 final snapshot 누락을 정상 비용으로 해석하지 않는다.

cgroup `memory.peak`를 authoritative peak로 기록한다. sampled RSS나 process-tree RSS를 추가 수집하면 별도 이름과 sampling 방식으로 기록하며 cgroup peak와 동일시하지 않는다. OOM을 판정하려면 해당 attempt의 cgroup event 증거를 보존한다. exit137 또는 SIGKILL만으로 OOM을 확정하지 않는다.

### 9.2 Wall과 evidence

outer guarded wall은 monotonic clock으로 system-unit launch/startup 시점부터 작업 및 소유 process tree의 종료/reap·timeout 처리 완료까지 측정한다. 실제 startup/cleanup 지연을 제외하거나 180초로 잘라 기록하지 않는다. 180초 deadline을 넘는 attempt는 resource refusal이며, 종료 처리가 더 걸리면 그 실제 시간도 상위 ledger에 과금한다.

pre/post environment inspection, cgroup snapshot, V1 내부 timing과 outer timestamps는 각자 경계를 명시한다. 이미 완료한 환경 준비, read-only architecture inspection, 최종 가벼운 분석/문서 작성 시간은 guarded compute budget에 합산하지 않고 별도 administrative timing으로 기록한다. 중복 계측으로 guarded 시간을 빼거나 더하지 않는다.

actual retained bytes는 정의된 evidence tree에 남은 파일의 logical byte length 합계로 기록한다. filesystem allocated blocks, writer reservation 또는 압축 추정량을 대신 쓰지 않는다. run별 count 경계와 campaign 전체 count 경계를 기록하고, 추가 metadata/report/addendum도 누적 retained accounting에 포함한다. 별도 rootfs는 제외한다.

### 9.3 기존 V1 barrier metrics

기존 `VerifiedChainDriver.metrics`와 `barrier-k.json`에서 initial acquisition, seal, produce, check, publication, paused 및 next-body acquisition을 수집한다. certified generation, step, barrier kind, public bits, source binding, session/process identity, trace prefix/frontier 및 checker/receipt/checkpoint IDs를 연결해 보존한다.

V1 내부에서 timing을 재구현하거나 계측을 위해 source를 바꾸지 않는다. 실패 전에 생성된 partial metrics도 보존한다. 없는 metric을 0 또는 완료된 단계로 대체하지 않는다.

### 9.4 Cloud/environment 상태

warm-up과 각 attempt 전후에 최소 `/proc/loadavg`, CPU pressure, `/proc/stat`의 steal 관련 원본 관측, instance identity, boot_id, CPU topology, actual cgroup 설정을 기록한다. 값과 timestamp/단위를 함께 보존한다. steal 관측이 없거나 0이라고 cloud noise 부재를 주장하지 않는다.

CPU load/pressure/steal은 해석을 위한 관측값이다. outlier를 삭제하거나 raw runtime에서 임의로 noise를 빼는 보정값으로 사용하지 않는다. boot_id는 campaign admission 시 live 값으로 고정해야 하며, 현재 문서가 미관측 boot_id를 임의로 기입하지 않는다.

## 10. Timing 중복 계산 금지

`paused_seconds`는 seal/produce/check/publication 등이 진행되는 paused 구간을 포함한다. 이를 하위 timing과 더해서 총 비용으로 만들지 않는다. initial/next-body acquisition, 단계별 timing, paused를 각각 분해 분석용 raw metric으로 표시한다.

전체 wall 비용의 권위값은 outer guarded wall, 전체 CPU 비용의 권위값은 cgroup CPU usage delta이다. CPU와 wall은 서로 다른 단위/측정이며 합산하지 않는다. raw metrics와 derived ratios/CV는 별도 자료로 유지한다.

## 11. 독립적인 세 budget

| Budget | 승인된 값 | 권위와 초과 처리 |
| --- | --- | --- |
| V1 writer reservation | **640 MiB = 671,088,640 bytes/run** | 기존 locked pre-write reservation; 구조적으로 입증된 초과는 `REFUSED_RESOURCE: WRITER_RESERVATION` |
| Post-run retained threshold | **96 MiB = 100,663,296 bytes/run** | terminal artifact tree 검사; 초과 evidence 보존, `REFUSED_RESOURCE: EVIDENCE_GROWTH`, 다음 run 금지 |
| Actual retained evidence ceiling | **3 GiB = 3,221,225,472 bytes** | warm-up, 모든 attempts와 metadata/report 포함; 소진/초과 시 STOP |
| Compute Metabolism upper guarded wall | **4200초** | 실제 outer wall 누적; 소진 시 `CAMPAIGN_RESOURCE_EXHAUSTED`, 자동 연장 금지 |
| Per-run outer wall | **180초**, 모든 profile 동일 | 초과 시 `REFUSED_RESOURCE: OUTER_WALL_TIMEOUT` |

writer reservation, retained bytes, guarded wall은 서로 대체하거나 합산하지 않는다. 640 MiB는 실제 디스크 사용량이나 retained threshold가 아니다. 새 guard가 run별 `RTN_QUOTA_FILE`과 `RTN_QUOTA_BYTES`를 제공하고 기존 `sealed_write()`·`reserve_writer()` 계약을 유지한다. 기존 tracer의 512 MiB 선예약을 수정·우회하지 않는다.

640 MiB는 승인된 **실행 시 검증할 상한**이다. GCP에서 충분하다고 검증된 값이 아니다. 같은 resource ceiling을 넘었다고 자동 증액하거나 별도 quota로 우회하지 않는다. 각 attempt에 fresh writer counter를 제공하는 것은 승인된 per-run 계약이며, 누적 wall/retained ledger의 reset을 뜻하지 않는다.

설계 근거로 확인한 기존 local Task8 N=3 writer 예약량은 positive-02의 566,429,350 bytes와 positive-03의 566,446,418 bytes이다. positive-03의 실제 보존 파일 합계는 39,992,841 bytes(약38.14MiB)였다. 이 관측치를 GCP 예측이나 640MiB 충분성 증명으로 사용하지 않는다.

96 MiB는 byte-exact한 실시간 kill boundary가 아니다. 초과 run을 보존하고 종료 후 STOP한다. 3 GiB도 이미 생성된 evidence를 삭제/절단해 맞추지 않는다. 경계에 닿거나 넘으면 실제 보존량과 경위를 기록하고 추가 numerical attempt를 허용하지 않는다. 최종 STOP/report 작성 bytes도 사용량에 포함하며, 이를 감추거나 ceiling을 자동 늘리지 않는다.

3 GiB 범위에는 warm-up, ACCEPT/refused/failed attempts, environment snapshots, cgroup receipts, V1 evidence, quota/ledger metadata 및 final analysis/report가 들어간다. 새 campaign namespace가 생겨도 기존 namespace의 보존량을 누적 상위 accounting에서 버리지 않는다.

4200초에는 warm-up, 모든 성공/자원거부/실패 attempt, 3→5→7 확대, system-unit startup, timeout 처리 및 containment/termination이 포함된다. 이미 끝난 준비/inspection 및 가벼운 최종 분석/보고 시간은 별도로 기록한다. 상위 ledger가 actual outer wall의 권위이며 내부 `experiment_wall_seconds`를 대신 과금하지 않는다.

최대 planned attempts는 warm-up1 + measured21이다. nominal ceiling 합은 3960초로 4200초보다 240초 작다. 이 산술은 cleanup이나 실패 후 재시작까지 완료할 수 있다는 보장이 아니다. 다음 attempt 전에 남은 wall/evidence allowance를 확인하고, 부족하면 해당 상위 ceiling의 구조화된 STOP receipt를 남긴다. partially funded attempt로 resource 결과를 왜곡하지 않는다.

## 12. Resource refusal taxonomy

| Run/campaign outcome | 조건 |
| --- | --- |
| `ACCEPT` | measured correctness gate와 environment/profile/budget eligibility 모두 충족 |
| `REFUSED_RESOURCE` | 해당 run에 bound 된 구조화된 guard/cgroup/quota/ledger 증거가 자원 원인을 입증 |
| `REFUSED_VERIFICATION` | bound independent checker의 명시적 거부 또는 correctness/lineage/body/final-bits 위반; campaign STOP |
| `ENVIRONMENT_INVALID` | source/environment/profile invariant 또는 계측 authority 위반; campaign STOP |
| `UNRESOLVED_FAILURE` | V1 STOP/예외의 원인을 확실히 분류할 증거가 없음; campaign STOP |
| `UNRESOLVED_VARIABILITY` | 최대 7 attempts에서도 승인된 outcome/CV 안정 조건 불충족; completion 보류 |
| `STABLE_RESOURCE_REFUSAL` | 0.5C의 최초 3회가 아래 §16의 동일 자원거부 조건을 충족 |
| `CAMPAIGN_RESOURCE_EXHAUSTED` | Compute Metabolism 상위 wall allowance 소진/다음 실행 allowance 부족; STOP |

구조화된 resource reasons에는 `OUTER_WALL_TIMEOUT`, `CGROUP_OOM`, `WRITER_RESERVATION`, `EVIDENCE_GROWTH`, `CAMPAIGN_EVIDENCE_CEILING`, `CAMPAIGN_WALL_CEILING`이 있다. run ID, unit/cgroup/epoch, 적용 ceiling, 관측 시간/값 및 원본 증거 hash/locator로 해당 attempt에 묶는다.

명령 exit code, error string, 일반 `V1 STOP`만으로 resource refusal을 발급하지 않는다. writer denial도 실패한 예약과 ceiling을 구조적으로 입증해야 하며, 기존 quota counter의 숫자만 보고 실패 원인을 추측하지 않는다. 그 증거를 V1 source/계약 변경 없이 제공하는 것은 새 guard의 설계 요구사항이다. 입증되지 않은 경우의 확정 판정은 `UNRESOLVED_FAILURE` + STOP이다.

이 분류의 정확성을 위해 기존 V1 report/exception/return code를 삭제하거나 재작성하지 않는다. V1 결과, wrapper 결과, campaign 결과를 별도 필드로 보존한다. 여러 이상 신호가 있으면 모두 기록하며, source/environment/verification 위반을 resource label로 가려서 campaign을 계속하지 않는다.

## 13. 내부 timeout과 즉시 campaign STOP

기존 내부 fail-closed 제한은 유지한다.

| 기존 제한 | 값 |
| --- | --- |
| Producer worker `communicate` | 60초 |
| Independent checker worker `communicate` | 60초 |
| Live frame wait | 120초 |

내부 timeout은 자동 `REFUSED_RESOURCE`가 아니다. 자원 원인이 구조적으로 입증되지 않으면 `UNRESOLVED_FAILURE`이고 campaign STOP이다. profile별로 이 값을 다르게 적용하거나 GCP 적응을 위해 늘리지 않는다.

다음 사건은 평균/반복으로 덮지 않고 즉시 campaign STOP한다.

- final bits mismatch, bound CHECKER failure, generation/lineage mismatch.
- unexpected body4, 잘못된 FINAL_TERMINAL, publication 이전 다음 body 진행, process/session binding 위반.
- source binding mismatch 또는 실행 중 source/environment binary drift.
- cpuset/cpu.max/memory/swap enforcement mismatch, cgroup evidence unavailable.
- VM instance identity, boot_id 또는 CPU topology 변경.
- 예상하지 않은 내부 V1/계측 예외, 원인 불명 STOP/failure.
- warm-up failure, retained growth/ceiling 또는 누적 wall allowance STOP.

STOP 후 다음 profile/run을 자동 시작하지 않는다. 환경 수정 후 재개가 필요하면 새로운 evidence campaign ID로 warm-up부터 시작해야 하며, 기존 namespace/실패 evidence는 보존한다. 상위 budget을 reset하지 않으며 수정 작업/추가 실행의 승인을 STOP이 자동 부여하지 않는다.

## 14. Repetition schedule과 CV

초기 9회는 아래 Round1~3이다. Round4~5, Round6~7은 승인된 판정에서 필요한 경우에만 실행한다.

| Round | 1번째 | 2번째 | 3번째 |
| --- | --- | --- | --- |
| 1 | 2C | 1C | 0.5C |
| 2 | 1C | 0.5C | 2C |
| 3 | 0.5C | 2C | 1C |
| 4 | 2C | 0.5C | 1C |
| 5 | 0.5C | 1C | 2C |
| 6 | 1C | 2C | 0.5C |
| 7 | 2C | 1C | 0.5C |

추가 round에서는 아직 안정되지 않은 profile만 위 상대 순서에 따라 실행한다. 이미 안정적으로 종료된 profile을 통계 모양 때문에 다시 실행하지 않는다. 시도 횟수에는 resource refusal이 포함되고, 이전 실패를 성공 실행으로 대체하거나 rolling window에서 제거하지 않는다.

먼저 outcome consistency를 검사한다. 모두 eligible ACCEPT인 profile에 대해 3, 5, 7 attempts의 누적 ACCEPT 표본을 사용해 각각 계산한다.

```text
sample_sd = sqrt(sum((x_i - mean(x))^2) / (n - 1))
CV = sample_sd / mean(x)

wall x_i = outer guarded wall_seconds
CPU  x_i = cgroup delta usage_usec / 1,000,000
```

wall CV와 CPU CV가 모두 **≤0.05**여야 안정적이다. 5%는 이 V0의 실험 설계 기준이며 자연법칙, confidence bound 또는 통계적 유의성 증명이 아니다. raw 값과 계산식/n/단위를 보존한다. 측정 누락·counter 오류를 0으로 대체하거나 CV를 임의 정의하지 않는다.

3회 모두 ACCEPT이고 두 CV가 기준을 만족하면 해당 profile을 종료한다. 하나라도 >5%면 5회로, 5회에서도 >5%면 7회로 확장한다. 7회에서도 불안정하면 `UNRESOLVED_VARIABILITY`이다. outlier 자동 삭제·winsorization·noise 차감·선택적 재실행은 하지 않는다.

## 15. ACCEPT/resource-refusal 혼재

ACCEPT와 구조적으로 입증된 resource refusal이 섞이면 ACCEPT subset의 낮은 CV로 안정 판정을 만들지 않는다. 3회 혼재는 5회로, 5회 혼재는 7회로 진행하고 7회에서도 혼재하면 `UNRESOLVED_VARIABILITY`이다.

전체 attempts를 누적하므로 이전 refusal이 후기 성공으로 사라지지 않는다. resource-refused attempts는 성능 비교 수치에 넣지 않지만 outcome counts, 사용한 wall/CPU, retained bytes와 원본 증거에서는 제거하지 않는다. verification/environment/unresolved failure는 반복 대상으로 취급하지 않고 즉시 STOP한다.

자원거부가 있는 2C/1C profile은 최소 3 valid ACCEPT와 안정성 gate를 대신 충족한 것으로 인정하지 않는다. 0.5C만 아래의 특별한 stable-resource completion 경로를 갖는다. 승인된 반복 분기 밖의 resource-only 결과에 추가 실행이나 새 상한을 자동 부여하지 않으며 completion은 성립하지 않는다.

## 16. 0.5C stable resource refusal

0.5C의 **최초 3 measured attempts 전부**가 `REFUSED_RESOURCE`이고 아래 조건을 모두 만족하면 해당 profile을 `STABLE_RESOURCE_REFUSAL`로 종료할 수 있다.

- 세 attempt 모두 CPU profile/source/environment invariant 정상.
- verification failure 또는 unresolved failure 없음.
- 세 attempt 모두 동일 종류의 입증된 resource ceiling에서 종료.
- raw evidence와 실제 비용·부분 generation/CURRENT를 그대로 보존.

campaign 자체의 wall/evidence 소진처럼 모든 후속 실행을 차단하는 global STOP을 0.5C의 고유 자원거부 결과로 대체하지 않는다. retained-growth STOP 뒤에도 stable outcome을 만들려고 남은 attempts를 실행하지 않는다.

허용되는 결론은 **“0.5C에서 주어진 자원 계약 안에 정확한 certified N=3 chain을 완성하지 못했다”**이다. numerical invalid, 보편적인 CPU 하한 또는 이론적 불가능성으로 해석하지 않는다. 성공시키기 위한 timeout/quota 증액은 금지한다.

## 17. Evidence namespace와 상위 ledger

계층의 예정 namespace:

```text
compute_metabolism/v0/artifacts/
  budget.json                   # 새 Compute Metabolism 상위 resource authority
  gcp-<campaign-id>/
    campaign.json
    environment.json
    reference.json
    ledger.json                 # 상위 ledger에 연결된 campaign 기록
    warmup/
    round-01/
    round-02/
    round-03/
    ...                         # 승인된 조건부 round-04~07
    analysis/
```

각 attempt는 최소 `pre-environment.json`, post-environment snapshot, `cgroup-before.json`, `cgroup-after.json`, fresh V1 evidence/store, writer quota/guard receipts, `execution.json`, `metrics.json`, `verdict.json`을 보존한다. partial/crash/timeout evidence도 삭제하거나 덮어쓰지 않는다. 새 분석/report는 raw evidence와 분리하고 provenance/hash로 연결한다.

새 상위 ledger는 Compute Metabolism 전용이며 기존 Task 8 `runtime_trace/regular_nstep/artifacts/budget.json` 및 `budget.running.json`을 변경·초기화·실행 권한으로 재사용하지 않는다. 숫자 4200이 같아도 서로 다른 승인/실험 ledger이다. 새로운 ledger 생성 권한은 이 설계에 있으나 **현재 문서 작성 단계에서 생성하는 것은 아니다**.

상위 ledger는 run ID, campaign ID, profile, round, warm-up/measured role, 실제 outer wall, CPU seconds, reserved/used writer bytes, retained bytes, verdict/reason, 누적 guarded wall 및 누적 retained 사용량을 구분해 기록한다. CPU seconds는 raw 비용이며 별도로 승인하지 않은 CPU ceiling이나 fitness를 만들지 않는다.

campaign별 `ledger.json`은 상위 ledger에 연결된 기록이며 독립적인 4200초 allowance를 발급하지 않는다. 새 campaign ID는 새 evidence namespace일 뿐이다. 이전 namespaces의 비용을 누적 상태에서 빼거나 상위 ledger를 0으로 reset하지 않는다. ceiling 증가 또는 초기화는 설계자 명시 승인이 필요하다.

fresh V1 driver/session에 전달되는 기존 ledger path 인자는 새 Compute Metabolism ledger를 가리킬 수 있어야 하며, Task 8 workflow의 hard-coded historical ledger 연결을 가져오지 않는다. V1 내부 ledger 존재 요건과 writer reservation 계약은 그대로 유지한다. ledger recovery/partial-attempt accounting이 확인되지 않은 상태에서 다음 attempt를 허용하지 않는다.

## 18. N=1 warm-up

각 새 campaign의 본 측정 전에 **2C, N=1, 1회, 비채점, outer timeout180초**의 fresh V1 warm-up을 수행한다. writer640 MiB 및 동일 memory/swap/thread 조건을 적용하고, 모든 wall/evidence 사용량을 상위 budget에 포함한다.

warm-up도 production V1 ACCEPT, fresh S0→S1, generation/step1, S1 FINAL_TERMINAL, bound independent checker PASS, body marker `[1]`, body2 없음과 source/environment invariant를 만족해야 한다. N=3 generation/terminal/reference bits를 N=1 결과에 잘못 적용하지 않는다.

목적은 GCP의 실제 live V1 경로를 확인하고 Python/GDB/shared-library/page-cache cold-start 영향을 본 measured runs와 구분하는 것이다. warm-up은 cache 상태가 완전히 통제되거나 이후 cloud variability가 사라진다는 증명이 아니다. 3→5→7 CV, profile runtime 비교, 성능 ratios에 넣지 않는다.

warm-up이 실패하면 9회 측정을 시작하지 않는다. 원본 실패를 보존하고 분류한 뒤 STOP한다. 같은 campaign에서 성공할 때까지 warm-up을 반복해 최초 실패를 숨기지 않는다. 새 campaign 재시작에는 상위 remaining allowance와 승인 범위를 그대로 적용한다.

## 19. GCP primary와 Ryzen 5600 cross-environment validation

GCP primary experiment의 completion 후에만, 로컬 Ryzen 5600 CPU가 idle일 때 별도 CPU-control preflight를 먼저 수행한다. 기존 로컬 memory/systemd guard 검증을 strict 2C/1C/0.5C enforcement 증거로 대체하지 않는다. 로컬 CPU 번호는 GCP의 0,1을 무조건 복사하지 않고 실제 local topology/preflight로 확인해야 한다.

local preflight PASS 후 2C/1C/0.5C 각 1회 sanity check를 별도 environment/campaign evidence로 수행하는 방향이다. 의미 있는 차이·이상 현상이 확인될 때만 별도 3회 반복으로 확대한다. 이 문서는 그 local 추가 실행의 구체 allowance 또는 자동 시작 권한을 발급하지 않는다. 실행 시 idle/preflight와 별도 범위를 확인해야 한다.

local 결과를 GCP 통계/CV/ratios/4200초 primary ledger에 섞지 않는다. GCP V0 completion gate에 local 결과를 포함하지 않는다. 현재는 로컬 실험도 수행하지 않는다.

## 20. 완료 조건과 주장 범위

Compute Metabolism V0의 GCP primary 결과를 `COMPLETE`로 제출하려면 다음 구조가 모두 성립해야 한다.

- warm-up PASS.
- 2C: 최소3 eligible ACCEPT, outcome consistency와 wall/CPU CV 기준 충족.
- 1C: 최소3 eligible ACCEPT, outcome consistency와 wall/CPU CV 기준 충족.
- 0.5C: eligible ACCEPT와 안정된 측정, 또는 §16의 STABLE_RESOURCE_REFUSAL.
- 모든 accepted measured runs: 동일 V1 correctness admission gate 통과.
- source/environment invariant 및 budget/ledger integrity 유지.
- 모든 attempts/outliers/refusals와 raw evidence 보존.
- raw metrics와 derived ratios/CV를 분리한 final analysis/report 제출.

0.5C의 UNRESOLVED_VARIABILITY, incomplete profile, resource exhaustion 또는 STOP은 “실험을 수행했다”는 기록이 될 수 있지만 COMPLETE를 대신하지 않는다. 문서·환경 준비·unit smoke·기존 V1 PASS는 새 campaign completion이 아니다.

허용되는 완료 후 주장: **현재 V1 N=3 workload가 이 GCP VM에서 승인된 CPU envelope 변화에 따라 보인 correctness outcome, CPU-time, wall-time, memory, throttle 특성을 측정했다.**

주장할 수 없는 범위는 실제 Joule/전력 효율, 모든 CPU/cloud/입력, 긴 N trajectory, role parallelism, 여러 코어 활용 최적화, neural controller, evolution, 자동 fitness, 일반 프로그램, 보편적인 numerical/physical correctness와 formal certification이다. 기존 V1의 init→step1 및 terminal→wrapper tail UNTRACED 범위, OS/GDB/root 전제와 audit/인증 수준을 넓히지 않는다.

## 21. 작성자 자체 검토와 제출 상태

이 항목은 written spec의 내부 일관성 검토 기록이다. independent audit, 구현 시험 또는 설계자의 written-spec 승인을 뜻하지 않는다.

| 검토 대상 | 문서 대조 결과 |
| --- | --- |
| 설계1/4~2/4 A안/GCP/동일 V1/순서/분리 | §1~4, §8~10, §14~20에 유지 |
| 설계3/4 wrapper/system guard/fresh/namespace/ledger | §5~7, §9, §17~18에 통합; 예정 구조로 표시 |
| 수정된 설계4/4 숫자 | §11에 180s / 4200s / 640MiB / 96MiB / 3GiB; §14에 3→5→7과5% |
| 640 MiB 충분성 표현 | §3/§11에 GCP NOT TESTED; 승인 상한으로만 표시 |
| 기존 V1 계약 유지 | source universe, 512MiB 예약, 60/120초, receipt/token/session/barrier를 변경하지 않음 |
| Task8 보호 | static reference provenance만 사용; 역사 ledger/live authority/receipts 재사용·초기화 금지 |
| Timing 중복 금지 | paused와 하위 timing 분리, authoritative outer wall/cgroup CPU 명시 |
| Resource 분류 | 구조화된 근거 필요; unknown/internal timeout은 자동 승격 금지 |
| Mixed outcomes/outliers | 전체 attempts 누적, CV로 실패 은폐 금지, 삭제/rolling window 금지 |
| Restart namespace | 상위 wall/retained accounting 유지; 새로운 budget 없음 |
| Proposal/implemented/tested | 문서 첫 상태표와 각 절에서 분리; wrapper 구현/GCP benchmark 없음 |
| 요구된20개 주제 | §1~20에 각각 명시 |

문서 검토가 실제 실행을 대체하지 않는 항목은 다음과 같다: system guard의 strict enforcement/containment와 cgroup final capture, V1 변경 없이 writer reservation denial을 구조적으로 입증하는 경로, partial-attempt ledger recovery, GCP에서640MiB의 충분성, warm-up 및 N=3 correctness와 반복 안정성. 이들은 현재 구현·시험 완료로 서술하지 않았다. 입증 실패 시 승인된 failure/STOP 규칙을 적용해야 한다.

작성 전후 보호 inventory 대조는 `verified_driver/`의 소스·역사 artifacts, Runtime Trace의 artifact 밖 Python sources, frozen source map 및 Task8의 `budget.json`/`budget.running.json` 등을 대상으로 수행했다. **1,611 entries 차이0**이다. 이 중5개는 symlink의 link target 문자열을 비교했고 alias를 따라가서 범위 밖 target의 내용을 검사했다고 주장하지 않는다. 승인된 V1 source40개 및 V0/Runtime Trace source89개는 각 approved pinset과 별도로 대조하여 변경0을 확인했다.

Git에서 새 파일은 본 spec1개뿐이며 기존 tracked 변경과 staged 변경은 없다. `git diff --check` exit0을 확인했고, untracked인 본 문서도 별도로 trailing whitespace0을 확인했다. implementation plan, `compute_metabolism/` 계층, ledger 또는 campaign artifacts를 만들지 않았다. 확인에 사용한 inventory와 source hashing은 read-only inspection이며 numerical test/benchmark나 guarded campaign execution으로 기록하지 않았다.

본 제출은 승인된 written design spec 한 문서이다. wrapper 코드, ledger 및 campaign artifacts를 생성하지 않고 warm-up/benchmark/로컬 실험을 실행하지 않는다. staging/commit/push를 수행하지 않는다. **implementation plan의 설계자 검토·승인 전에는 구현으로 넘어가지 않는다.**


## 2026-10-07 Operational namespace amendment (승인된 변경 기록)

Task 9 최초 운영 ledger 초기화는 `artifacts/budget.json`이 없고 그 부모에 보존된 Task 8 TEST_ONLY evidence가 있어 `missing upper ledger in nonempty artifact root; reset refused`로 STOP했다. 기존 승인 내용과 evidence를 보존하면서 이 충돌을 해소하기 위해, 2026-10-07 승인으로 운영 namespace를 아래와 같이 분리한다. 이 amendment는 위의 기존 `artifacts/budget.json` 및 campaign 배치 설명을 운영 실행에 한해 대체하며, 기존 설명은 변경 이력으로 남긴다.

- 운영 retained root: `compute_metabolism/v0/artifacts/operational/`.
- 유일한 운영 upper ledger: `compute_metabolism/v0/artifacts/operational/budget.json`.
- 실제 campaign config/identity/inputs, warmup, rounds, analysis 및 후속 metadata는 `operational/<campaign-id>/` 아래에 둔다.
- 승인된 누적 guarded wall 4200초와 retained evidence 3 GiB = 3,221,225,472 bytes는 이 operational subtree에만 적용한다. Task 8 TEST_ONLY sibling evidence는 현재 위치에서 이동·삭제·수정하지 않고 운영 사용량에 소급 산입하지 않는다.
- `CampaignLedger.open()`의 missing ledger + nonempty ledger root 거부 규칙은 그대로 유지한다. `operational/` 자체가 nonempty이면 ledger가 없어도 초기화가 거부되며, 운영 evidence가 있는 상태에서 budget만 삭제해 재생성하거나 새 campaign ID로 allowance를 얻을 수 없다.
- V1 source/numerical contract, system guard CPU/memory/swap 계약과 180초 deadline, 640 MiB writer, 96 MiB post-run threshold는 변경하지 않는다.
- 이번 실행 승인은 review 후 필요한 변경 배포와 운영 ledger 초기화 1회까지만 포함한다. Gala N=1 warm-up 및 Task 10은 이번 amendment 실행에서 시작하지 않는다.


## 2026-10-07 Environment identity + campaign restart amendment (승인된 변경 기록)

Task 9의 첫 warm-up은 준비 당시 platform 문자열과 현재 live platform의 차이를 영구 runtime identity 불일치로 판정하여 ENVIRONMENT_INVALID로 STOP했다. prepared execution-environment.json은 당시 provenance로 원본 bytes/hash를 보존한다. 아래 변경은 이전 승인 설명을 지우거나 실패 이력을 덮어쓰지 않고, prepared identity와 campaign 동안 유지할 live identity를 분리한다.

- Prepared exact identity: Python version/executable, installed package set/version, pinned runtime file hashes, V1 source count/binding/source match. 준비 당시 platform은 provenance이며 exact-match 기준에서 제외한다.
- 새 formal campaign 초기화 직전 live observation으로 얻은 platform을 campaign-environment.json에 저장하고 config/input SHA-256으로 bind한다. 특정 kernel/platform 문자열을 source에 하드코딩하지 않는다. 모든 attempt에서 live platform과 campaign platform, before/after platform, instance ID, boot ID, topology가 일치해야 한다.
- 기존 operational/budget.json 하나를 계속 사용한다. 새 campaign은 명시적 restart_from_campaign_id 및 restart_from_finalization_sha256을 config에 bind하고, 현재 campaign의 durable STOP finalization 및 proof hashes를 검증한 경우에만 생성한다. RUNNING은 null, 모든 기존 attempts는 FINISHED여야 하며, 새 ID는 달라야 하고 새 namespace는 없어야 한다. finalization/proof의 campaign/config, attempts, wall 및 STOP 정책 근거도 검증한다.
- 기존 binding을 formal_campaign_history에 보존하고 predecessor STOP identity와 successor binding을 campaign_restarts에 추가한다. 기존 attempt/finalization/evidence는 변경하지 않는다. 역사 campaign은 읽기 전용으로 조회할 수 있지만 run-next 실행 권한은 없다.
- 기존 guarded wall 1.0627413820002403초와 retained accounting/history를 이어간다. 새 campaign은 추가 allowance나 reset을 발급하지 않으며 총 4200초/3 GiB, 180초 deadline, 640 MiB writer reservation, 96 MiB retained threshold, 4 GiB memory/swap 0은 유지한다. CampaignLedger.open()의 reset 거부 계약, V1 source/numerical contract 및 system_guard CPU 계약은 변경하지 않는다.
- 이번 승인 실행은 RED → 최소 구현 → 관련 회귀 GREEN → fresh read-only review 후 필요한 wrapper/spec/plan 배포, live environment 재확인, successor formal campaign 정확히 1개 초기화 및 accounting/history 연속성 확인까지다. 이후 STOP한다. 두 번째 N=1 Gala warm-up, Task 10, Task 8 probe 반복, staging/commit/push는 포함하지 않는다.

## 2026-10-07 Adaptive execution and validation amendment

후속 Task 9에서 같은 pinned libc의 새 CPU 경로가 기존 frozen trace 계약 밖으로 나왔고, 결과 정리 helper의 `/usr/bin/env` 부재 및 실패 CPU 비용의 null 기록도 확인됐다. 설계자는 적응형 프로필 저장소·탐지·고정·격리 관찰·후보 생성·독립 승격 gate와 두 wrapper 결함을 하나의 정비 범위로 승인했다. 이전 STOP/evidence와 예산은 보존하며, 상세 계약은 `2026-10-07-compute-metabolism-adaptive-design.md`, 구현 절차는 대응 adaptive plan에 추가 기록한다.

VERIFIED profile은 기존 V1 검증을 대체하지 않는다. 호출 출처·ELF 경로·입력 범위를 추가 제한하고, 기존 producer/native checker/CURRENT publication 계약을 유지한다. 관찰은 certified state를 생성하지 않는다. 독립 증명 없는 EVEX 결과는 CANDIDATE이며 warm-up 권한이 없다. 새 실행부터 유효한 guard CPU 비용은 수치 성공 여부와 별개로 저장하고, 역사 null/UNAVAILABLE은 그대로 둔다. 새 formal campaign은 선택 profile ID/manifest hash와 환경 지문을 고정하고 동일한 operational upper allowance를 이어간다.

## 2026-10-08 execution ownership amendment (append-only)

The actual Gala observation `observation-gala-evex-01` stopped before child creation:
its root-owned 0755 attempt directory could not be written by UID 1000 / GID 1003.
This is an orchestration failure, not a verdict about the new CPU path. Preserve
that attempt, its STOP finalizations, unavailable measurements and all old evidence.

One immutable system-unit execution identity must supply both systemd credentials
and artifact ownership. Exclusively create the run directory and writer quota,
restrict them to 0700 and 0600, apply the execution owner's UID/GID, then read actual
ownership/type/mode back. Recheck both filesystem ownership and systemd argv identity
before launch. Preparation failure or mismatch refuses before starting any unit.
No 0777, user-unit fallback, CPU contract change or EVEX semantic change is authorized.

`system_guard.py` is outside the 49-file V1 numerical source snapshot but inside the
complete gate source authority. Keep the physical V1 binding 104578c1... and its old
receipts unchanged; issue a fresh guard-inclusive gate binding, source-epoch hash,
review and regression receipts. A different V1 digest must not be invented for
unchanged V1 bytes. The new campaign binds the complete new gate manifest.

Only GCP executes permission tests, related regression and numerical work. After
CLEAN review, first perform a small system-unit file-write check without Gala or a
Task 8 CPU/timeout rerun. Then initialize one explicitly last-STOP-linked successor
on the existing upper ledger (16.948194404001697 seconds, four attempts, 9210281 bytes
at authorization). No new allowance or reset. Observe one original Gala call in
uncertified mode. Independent promotion must close all original call/library/input,
13 instruction, complete state/effect and negative-test obligations. Failure STOPs.
Only VERIFIED permits one fresh 2C N=1 warm-up; if an observation STOP requires it,
one additional same-upper STOP-linked successor is authorized. Stop after that N=1
regardless of result. N=3, Task 10, staging, commit and push remain unauthorized.
### STOP-linked observation-only successor clarification

The original APIs require a STOP owned by the current formal campaign and a
VERIFIED execution profile for numerical campaigns. A fresh unknown-route successor
has neither. The authorized connection therefore declares OBSERVATION_ONLY in its
frozen config and binds exactly one run ID, profile 2C, no certified state progress,
fingerprint, source epoch, registry and GDB hashes. It supplies no execution profile.
Initialization still verifies the explicit predecessor STOP with the existing full
history/hash/allowance checks. The first observation rechecks its unique recorded
restart link using a read-only predecessor view; it never writes that view to the
ledger. Zero own attempts, no own closing receipt, all prior attempts FINISHED and
RUNNING null are required. A second observation cannot consume this authority.
Numerical run_next is refused before launch. The observation policy has no numerical
next item and records a genuine single-authorization STOP without changing the raw
observation outcome. A subsequent numerical successor must bind an independently
VERIFIED profile and that observation STOP; ordinary campaign policy is unchanged.