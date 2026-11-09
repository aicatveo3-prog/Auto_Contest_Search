# AI 공모전 검색 — 개발/소스 폴더

실제 프로그램은 상위 폴더의 **`AI공모전검색.exe`** 하나입니다. (소스가 exe 안에 포함되어 있어 별도 설치 불필요)

```
상위 폴더/
├─ AI공모전검색.exe   ← 실행 프로그램 (유일, 보이는 파일)
├─ AGENTS.md          ← 숨김 파일: AI 정밀 판정 버튼이 사용하는 에이전트 규칙
├─ opencode.json      ← 숨김 파일: 에이전트 권한 설정
├─ data/              ← 수집 데이터 (db, 대시보드, csv)
└─ 개발소스/          ← 이 폴더 (소스·빌드 자료, 없어도 프로그램 동작에 지장 없음)
```

## 처음 사용 (받는 사람 기준)

1. `AI공모전검색.exe` 더블클릭
2. **데이터 갱신** — 최초 1회는 전체 수집이라 몇십 분 걸림 (기존 데이터가 있으면 즉시 완료)
3. **대시보드 실행** — 브라우저 자동 실행, 검색 · ★북마크 사용
4. (선택) **AI 정밀 판정** — 새 공모전의 본문을 AI 에이전트가 직접 읽고 자동 분류

> 창을 닫으면 서버도 종료됩니다. 의존성이 전부 exe에 포함되어 별도 설치가 필요 없습니다.
> AI 정밀 판정 버튼은 opencode가 설치된 개발 PC에서만 동작합니다 (공유받은 PC에서는 데이터 갱신까지 사용 가능).

## 공유 방법

- **exe 파일 1개만 전송** → 받는 사람은 Python 설치 불필요
- 받는 사람 PC에서 exe 옆에 `data/` 폴더가 자동 생성됩니다
- 내 데이터 초기화: `data/contests.db` 삭제 후 데이터 갱신

## 개발/수정

터미널로 직접 실행 (Python 필요):

```bash
py launcher.py                  # GUI 실행
py -m src.cli stats             # 통계
py -m src.cli serve             # 서버 단독 실행
py -m src.cli -h                # 전체 명령어
```

exe 재빌드:

```bash
py -m pip install pyinstaller
py -m PyInstaller --onefile --noconsole --clean ^
  --add-data "config/settings.yaml;config" ^
  --name AI공모전검색 launcher.py
```

빌드 결과는 `개발소스/dist/AI공모전검색.exe` → 상위 폴더로 복사 후 사용.
(소스 폴더에서 빌드하므로, 이 폴더 안의 src/ 스타일이 수정되면 반영됩니다)
