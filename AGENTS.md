# AI 공모전 판정 규칙 (batch 자동 분석)

작업: `data/exports/batch_auto.json` 파일을 열어 `items` 배열의 모든 항목을 분석하고,
결과를 `data/exports/labels_auto.json` 로 저장(덮어쓰기)하세요.

출력 형식: JSON 배열. 각 항목:

```json
{"ix": 123, "ai_policy": "allowed", "ai_modality": "text,image", "ai_evidence": "짧은 근거 인용", "source_level": "L2", "confidence": 0.8, "fit_score": 80}
```

## 필드 규칙
- `ix`: 배치 items의 `ix` 값을 그대로 사용
- `ai_policy`: `must` | `allowed` | `unclear` | `prohibited`
  - `must`: AI 생성물 제출이 참가 요건 자체 (예: "AI로 영상을 제작해야 함")
  - `allowed`: 규정에 AI 사용 허용이 명시됨 (제작 과정 일부 활용 허용 포함)
  - `unclear`: AI 관련 규정이 본문에 명시되지 않음 (가능 여부 판단 불가)
  - `prohibited`: AI(자동 생성물) 사용이 금지됨
- `ai_modality`: `video|image|text|audio|software` 중 해당 것들 (복수면 쉼표 구분)
- `ai_evidence`: 판단 근거가 되는 본문 구절을 짧게 한 문장
- `source_level`: `L0` 제목만 / `L1` 공지 요약 / `L2` 본문 확인 / `L3` 공모요강 문서 확인
- `confidence`: 0.0 ~ 1.0
- `fit_score`: 0 ~ 100 (AI로 제작할 수 있는지 종합 점수)

## 주의
- 판단은 `body_text`(본문 전문) 기준. 제목·카테고리만으로 결정하지 말 것.
- 본문이 비어 있으면: `ai_policy: "unclear"`, `confidence: 0.3`, 근거는 "본문 없음".
- 규정 문구에 "AI", "생성형", "ChatGPT", "Midjourney", "Sora", "Suno", "프롬프트" 등이 있으면 관련 정책 반드시 반영.
- 영상·사진·디자인·음악·웹·게임 같은 창작 카테고리는 AI 활용 가능성이 있으나 명시가 없으면 `unclear`로 두고 근거를 작성.
- 배치 items의 모든 항목을 빠짐없이 처리할 것.
- `labels_auto.json` 외의 어떤 파일도 생성/수정하지 말고, CLI 명령은 실행하지 말 것.
- 끝나면 처리한 건수와 분류 요약만 한 줄씩 출력.

## 권한
파일 읽기/쓰기 허용됨. 이 외 명령은 불필요.
