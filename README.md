# 노부나가의 야망 혁신 PS2 한글 패치 v2.6

**Nobunaga's Ambition – Iron Triangle (USA), SLUS-21868**용 비공식 한글 패치입니다.

## 다운로드 / 적용

[정식 릴리즈 v2.6](https://github.com/snake759494/nobunagas-ambition-iron-triangle-ps2-korean-patch/releases/tag/v2.6)에서 `Nobunagas_Ambition_Iron_Triangle_KO_v2.6.xdelta` 하나를 받으세요.

수정하지 않은 북미판 원본 ISO에 xdelta3로 적용합니다. 일본판·다른 개정판·기존 한글 ISO에는 적용하지 않습니다. xdelta 실행 파일과 게임은 제공하지 않습니다.

```powershell
xdelta3 -d -s "Nobunaga's Ambition - Iron Triangle (USA).iso" Nobunagas_Ambition_Iron_Triangle_KO_v2.6.xdelta Nobunagas_Ambition_Iron_Triangle_KO.iso
Get-FileHash .\Nobunagas_Ambition_Iron_Triangle_KO.iso -Algorithm SHA256
```

| 대상 | SHA-256 |
|---|---|
| 원본 ISO | `e362862b1f2dd430dc88e8dbde63e71f33170974737fca55cc942a0d2b23ae9f` |
| 완성 ISO | `07ca68182806e570bacee023a9dc264976d096af0ef8bd65ad5ab7948ac92f2e` |
| xdelta | `058ac2fd72a85b391c40771f5dc599af46d6ccc89fc5832dfc579eb0be8d407a` |

ISO 크기: **2,203,615,232바이트**. 적용 후 새로 부팅하세요. 이전 빌드의 세이브스테이트는 예전 코드·텍스처를 포함할 수 있습니다.

## 포함 내용

- 메뉴·도움말·대사 등 N12F 16,770문자열, 실행 파일 3,348문자열, 시나리오 필드 103,019개 검증.
- 한글 본문 글꼴과 이미지 라벨, BGM 곡명 36개. 메뉴는 사용자 선호에 따라 v2.3 스타일로 복원했습니다.
- 신무장 성/이름 한글 조합 키보드, 겹모음·겹받침, 문자 단위 커서와 삭제 처리.
- v2.6: `ㄱ → ㅏ → ㄱ → ㄱ → ㅏ` 입력으로 R1 이동 없이 **각가**가 됩니다. 쌍받침은 `ㄲ`/`ㅆ` 키로 직접 입력합니다.
- □ 삭제 시 게임 함수 호출의 스택 정렬 문제 수정.

## 입력 한도 / 검증 범위

성·이름 각각 한글 최대 5자 또는 영문 11자입니다. 혼용 시 내용 11바이트 한도를 적용합니다. 한글 2,350자 + 조합용 기본 음절 50자 + 자모 51자를 지원하며 현대 한글 11,172자 전체를 지원하지는 않습니다. 기존 저장 구조를 늘리지 않았습니다.

사용자가 v2.5 시점에 한글 키보드 동작을 확인했습니다. v2.6의 연속 자음 수정은 컴파일된 MIPS 코드에서 검증했습니다. 게임 그리기·효과음은 해당 테스트에서 대체하므로 전체 게임 실행 확인과는 다릅니다. v2.6 최종 ISO의 실제 입력, 전체 플레이, 모든 화면, 저장/불러오기, PS2 실기는 미검증입니다. 정식 릴리즈 표기는 완전한 실기 QA를 뜻하지 않습니다.

공개 소스로 재빌드한 ISO도 정식 빌드와 SHA-256이 일치합니다. [재현 검증](validation/public_rebuild.json).

ISO 읽기, 메뉴 리소스 7개와 제목 항목 49개의 이전 버전 일치, 한글 2,350자 조합, 삭제 콜백 33개 사례, xdelta 복원 해시를 검증했습니다. [검증 기록](validation/verification.json) · [입력기 테스트](validation/ime_tests.json).

## 개발 / 권리

[재빌드 안내](docs/BUILD.md) · [변경 내역](CHANGELOG.md) · [권리 및 배포 범위](RIGHTS.md).

이 저장소에는 패치 소스·한국어 번역·추출 위치/해시·검증 기록이 있습니다. 원본 대사 파일·ISO·게임 실행 파일·추출 바이너리·폰트·외부 실행 파일은 포함하지 않습니다. 원문 자료는 사용자의 원본 ISO에서 로컬로 복원합니다. 번역에는 스포일러가 있습니다.
