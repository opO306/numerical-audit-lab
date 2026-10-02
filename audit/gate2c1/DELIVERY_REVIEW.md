# 최종 전달 검증 보완

5504237의 독립 checker로 full 재계산을 완료했다. 결과는 수정하지 않는다.
독립 source SHA-256: f80d07ca596f6b7a5982142058ba9ed353d6d4b08371bccda492dd480681c68b.
당시 code seal SHA-256: d7e8adae7778de0b8d801174807a76b386f76d4f007dc18b24169d9a5a84878c.
위 seal/tool/test bytes는 pre_delivery_revision/에 보존한다.

읽기 전용 재검토에서 기존 5 Major / 2 Minor의 직접 보완을 확인했으나,
ZIP 내부 PACKAGE_MANIFEST.json을 parse하지 않는 새 Major 1건을 발견했다.
실제 제작기는 정상 JSON을 쓰지만 재개봉 검증기가 손상된 내부 manifest를 수락할 수 있었다.

수치 실행 완료 뒤 package tool만 보완했다. T_bin, producer, 독립 graph/executor/checker, V2,
완료된 producer/independent 보고서와 segment/exact bytes는 변경하지 않았다.
manifest missing/invalid JSON/hash/schema/required path 공격 5개를 RED로 재현한 다음,
필수 JSON/schema/files/required 계약과 실제 member SHA 검증 및 --verify 재개봉 검사를 추가했다.
해당 6개 시험과 기존 3개 package 시험은 9 PASS다.

최종 code seal은 이 전달 tool revision을 포함한다. 이는 결과를 다시 측정했다는 뜻이 아니다.
측정 시 소스와 봉인은 0f2fc62 / 5504237 및 보존된 두 이전 seal로 식별한다.
새 외부 A1–A11 최종 감사는 PENDING이다.
