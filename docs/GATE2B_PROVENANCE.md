# Gate 2B provenance — 감사 대상 gala 1.12.0

| 항목 | 값 | 확인 방법 |
|---|---|---|
| 패키지 | gala 1.12.0 (MIT), 저자 Adrian Price-Whelan, 저장소 `adrn/gala` | PyPI JSON 메타데이터 |
| 실행 wheel | `gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl` | — |
| wheel SHA-256 | `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0` | ① PyPI 메타데이터 ② 구현자가 내려받아 다시 계산 ③ PyPI attestation의 subject digest — 세 값이 같다 |
| PyPI attestation 발행자 | GitHub, repository `adrn/gala`, workflow `wheels.yml`, environment `release` | `https://pypi.org/integrity/gala/1.12.0/<wheel>/provenance` |
| **GitHub source commit** | **`bebac7d728478c5122a568e12175ef894d1c1516`** | 설계자 제공값. 구현자가 attestation 서명 인증서(Fulcio) 안의 문자열에서 같은 값을 찾았다. 같은 인증서에 `wheels.yml@refs/tags/v1.12.0`도 있다 |
| sdist (소스 읽기용) | `gala-1.12.0.tar.gz`, SHA-256 `68d80d4ffbe296e9c8656e130cb4ec3698e28319d08ef512d344bce4d9983c50` | PyPI 값과 다시 계산한 값이 같다 |
| 확인한 실행 환경 | Python 3.12.3, numpy 2.5.3, astropy 8.0.1 (클라우드 Linux x86-64 venv) | import 확인. 실제 실행 시 다시 기록 |

**한계:**
- attestation은 PyPI가 제공한 JSON을 받아 subject digest와 인증서 안의 문자열을 확인한 것이다.
- sigstore 서명 체인(인증서 → Fulcio 루트, Rekor 투명성 로그)을 **암호학적으로 검증하지는 않았다.** 검증하려면 `sigstore`/`pypi-attestations` 도구가 필요하다.
- GitHub에 직접 접속해 해당 commit의 소스를 받아 sdist와 대조하지 않았다. 이 환경에서는 github.com이 차단되어 있다.
