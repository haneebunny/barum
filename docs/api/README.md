# 판정 백엔드 API (프론트 연동용)

> 대상: 프론트(정빈)·디자이너. 계약면 한 장 요약 + 샘플.
> 원본 스키마: `backend/openapi.json` (서버 뜨면 `/openapi.json`·`/docs`로도 제공).
> 이 문서는 가변. 계약이 바뀌면 `scripts/dump_openapi.py`·`scripts/make_fixtures.py`를 다시 돌려 갱신한다.

## 엔드포인트

### `POST /check`  (multipart/form-data)
광고(이미지/글 + 나라)를 넣으면 문구별 위반 판정을 돌려준다. **동기**(요청 하나가 끝까지 돌고 결과 반환).

| 필드 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `region` | form | `KR` \| `US` | O | 검사 대상 국가. 현재 KR 실동작 |
| `ad_text` | form | string | △ | 검사할 광고 문구(붙여넣기) |
| `image` | file | 이미지 | △ | 상세페이지 이미지 |

- `ad_text`·`image` 중 **최소 하나** 필요. 둘 다 없으면 `422`.
- 둘 다 주면 이미지 문장 뒤에 글 문장을 이어 붙여 함께 판정.

### `GET /health`
`{"status": "ok"}`.

## 응답: `CheckReport`

```jsonc
{
  "findings": [            // 위반으로 지목된 문구들(합법은 여기 없음)
    {
      "span": "미백에 도움",      // 위반 표현(현재는 문장 전체 = 하이라이트 대상)
      "sentence": "…",           // span이 속한 원문 문장
      "violation_type": "2호_기능성오인",
      "legal_basis": "화장품법 제13조 제1항 제2호 (기능성 오인)",
      "risk": "중",               // 고 | 중 | 저
      "explanation": "…",         // 사람이 읽는 판정 근거
      "location": { "tile": "detail_000_t00.png", "order": 0 }
    }
  ],
  "unjudged": [           // 판정 실패로 못 가린 문장(= '재검사 필요', 합법 아님)
    { "sentence": "…", "location": { "tile": null, "order": 1 } }
  ],
  "summary": {
    "region": "KR",
    "n_sentences": 5,     // 판정에 투입된 문장 수
    "n_findings": 3,      // 위반 건수
    "n_unjudged": 0,      // 미판정 문장 수
    "counts_by_type": { "1호_의약품오인": 1, "2호_기능성오인": 1, "4호_거짓과장기만": 1 }
  }
}
```

### 하이라이트 2모드 (디자이너용)
- **이미지 입력**: `location.tile`이 채워짐 → 원문 이미지(해당 타일) 위에 표시.
- **문구-only 입력**: `location.tile`이 `null` → 붙여넣은 텍스트에서 `span` 스팬 하이라이트.
- `location.order`는 문장 순서(0부터). 좌표(bbox)는 없음(OCR 한계).

### 미판정(unjudged) 처리 (중요)
정책상 **미탐(위반을 놓침)이 제일 나쁘다.** 판정 실패 문장을 '합법'으로 보여주면 위반이 숨는다. 그래서 실패 문장은 findings에도 합법에도 넣지 않고 `unjudged`로 분리한다. UI는 이를 **"판정 못 함, 재검사 필요"** 상태로 보여줘야 한다(안전으로 오인 금지).

## 값 목록 (enum)
- `region`: `KR`, `US`
- `violation_type`: `합법`, `1호_의약품오인`, `2호_기능성오인`, `4호_거짓과장기만`, `대상외`
  - findings에 담기는 건 위반 3종(1·2·4호)뿐. `합법`·`대상외`는 finding을 안 만든다.
  - 화장품은 3호가 삭제된 조항이라 없다.
- `risk`: `고`, `중`, `저`

## 샘플 픽스처
`backend/fixtures/` (스키마 100% 유효, 실제 판정 아닌 예시):
- `check_report_image.json` — 이미지 입력(타일 하이라이트), 1·2·4호 골고루
- `check_report_text.json` — 문구-only(스팬 하이라이트)
- `check_report_with_unjudged.json` — 미판정 상태 포함

## 실행
```bash
cd backend
./venv/bin/python scripts/run_api.py            # 서버 (localhost:8000, /docs)
./venv/bin/python scripts/dump_openapi.py       # openapi.json 갱신
./venv/bin/python scripts/make_fixtures.py      # fixtures/*.json 갱신
```
- 판정기 기본은 Gemini(`GOOGLE_API_KEY` 필요). 키 없이 UI만 붙일 땐 `JUDGE_KIND=stub`(키워드 더미 판정)로 서버를 띄우면 된다.
- CORS는 개발 편의상 전체 허용(`*`).
