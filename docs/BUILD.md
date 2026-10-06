# 재빌드

Python 3.13에서 검증했습니다. 저장소 루트에 해시가 일치하는 원본을 `Nobunaga's Ambition - Iron Triangle (USA).iso`라는 이름으로 두고, `NanumSquareNeo-cBd.ttf`와 `SeoulHangangB.ttf`를 별도로 준비합니다. 파일은 Git에서 제외됩니다.

```powershell
python -m pip install -r requirements.txt
python -X utf8 tools/prepare.py
python -X utf8 tools/test_ime.py
python -X utf8 tools/build.py
python -X utf8 tools/verify_build.py
```

각 명령이 성공한 뒤 다음 명령을 실행하세요. `prepare.py`는 먼저 원본 ISO 전체 SHA-256을 검사합니다. 원본 추출·원문·번역 작업 입력을 `work/`, `translation/src`, `translation/jobs`, `translation/ko`에 재구성합니다. 원문 위치/해시를 검증하며 다른 원본은 거부합니다. 번역 수정은 공개 입력인 `translation/data/*.tsv`, `translation/fix_data.tsv`, `translation/source_index.json`의 한국어 추가 문자열, `translation/names.tsv`, `translation/image_bgm.tsv`에 반영합니다. term 키는 SHA-256으로 저장하며 prepare 단계에서 원본 필드로 복원합니다.

`build.py`는 원본 ISO를 보존하고 완성 ISO를 별도로 만듭니다. 검증은 완성 ISO를 다시 읽어 리소스·인코딩·경계·후크·메뉴 복원·비수정 영역을 확인합니다. 코드를 바꿨으면 테스트를 다시 실행하세요. `tools/ime/tables.h`, `hooks.S`, `bank.ld`는 컴파일 때 자동 생성됩니다.

정식 릴리즈의 패치 생성/복원:

```powershell
xdelta3 -e -s "Nobunaga's Ambition - Iron Triangle (USA).iso" Nobunagas_Ambition_Iron_Triangle_KO.iso Nobunagas_Ambition_Iron_Triangle_KO_v2.6.xdelta
xdelta3 -d -s "Nobunaga's Ambition - Iron Triangle (USA).iso" Nobunagas_Ambition_Iron_Triangle_KO_v2.6.xdelta roundtrip.iso
```

완성 ISO SHA-256은 README와 일치해야 합니다. xdelta 버전/옵션에 따라 패치 바이트는 달라질 수 있지만 복원 ISO는 같아야 합니다. 생성한 게임 자료나 폰트를 커밋하지 마세요.
