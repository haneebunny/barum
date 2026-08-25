# 판정 백엔드 API (프론트 연동용)

> 대상: 프론트·디자이너. 계약면 한 장 요약 + 샘플.
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
| `ingredients` | form | string | X | 전성분(콤마 구분, 예: `"정제수, 나이아신아마이드, 글리세린"`). 있으면 2호(기능성오인) 판정에 성분 정합 대조가 붙는다 |

- `ad_text`·`image` 중 **최소 하나** 필요. 둘 다 없으면 `422`.
- 둘 다 주면 이미지 문장 뒤에 글 문장을 이어 붙여 함께 판정.
- `ingredients`는 완전히 선택. 안 넣으면 2호 findings의 explanation에 "전성분 미입력" 안내만 붙고 판정 자체는 그대로 나간다.

### `GET /health`
`{"status": "ok"}`.

### `GET /reports/{result_id}`  (다시 보기)
저장된 검사를 다시 조회한다. `result_id`는 `POST /check` 응답에 실려 온다. 추측불가 랜덤 문자열이 곧 접근권(로그인 없음)이라, 못 찾으면 `404`.
```jsonc
// 200
{
  "result_id": "a3Fk9...",
  "created_at": "2026-08-11T09:00:00Z",
  "region": "KR",
  "image_available": true,          // 이미지 입력이었으면 true → 아래 이미지 프록시 사용
  "report": { /* CheckReport 그대로 */ }
}
```

### `GET /reports/{result_id}/image`  (원본 이미지 프록시)
이미지 입력이었던 검사의 원본을 백엔드가 그대로 스트리밍한다(밴드 하이라이트용 배경). 버킷은 비공개라 이 엔드포인트로만 접근한다. 이미지 없거나 없는 id면 `404`.

### `GET /reports?region=KR&limit=50`  (검사 이력 목록)
저장된 검사 결과를 최신순으로 요약 조회한다. 로그인 없이 데모 이력을 보여 주기 위한 API이며, 상세 결과는 각 항목의 `result_id`로 다시 조회한다. `limit`의 기본값은 50이다.

응답 항목은 다음 정보를 포함한다.

```jsonc
[
  {
    "result_id": "a3Fk9...",
    "created_at": "2026-08-11T09:00:00Z",
    "region": "KR",
    "product_name": "미백 크림",
    "image_available": true,
    "snapshot_available": true,
    "input_materials": ["ad_text", "ingredients"]
  }
]
```

### `POST /reports/{result_id}/export-readiness`  (국내 결과 기반 미국 준비도 재실행)
저장된 국내 검사 결과의 입력 스냅샷을 사용해 미국 수출 준비도 보고서를 새로 계산한다. 국내 판정 결과를 미국 판정으로 재사용하지 않고, 원문·전성분·제품 입력을 미국 readiness 규칙에 다시 넣는다.

선택적으로 JSON body로 `profile`을 전달할 수 있다.

```jsonc
{
  "profile_state": "PROVIDED",
  "profile": {
    "manufacturer_name": "예시 제조사",
    "facility_name": "예시 제조시설",
    "us_agent_name": "예시 U.S. Agent"
  }
}
```

응답은 `report_type: "export_readiness"`인 `ExportReadinessReport`이며, 결과에는 과거 입력을 보존하는 `profile_snapshot`과 `product_snapshot`이 포함된다. 원본 국내 검사에 입력 스냅샷이 없거나 지원하지 않는 레거시 결과이면 `422`를 반환한다.

### `GET /reports/{result_id}/readiness`  (저장된 readiness 다시 보기)
저장된 미국 readiness 보고서를 조회한다. 기존 `GET /reports/{result_id}` 계약과 별개로 readiness 응답의 discriminator(`report_type`)를 보존한다. 결과가 readiness 보고서가 아니거나 존재하지 않으면 `404`다.

#### 국내 검사에서 미국 readiness로 이어지는 데모 흐름

1. `POST /check`로 국내 검사 결과를 생성한다.
2. 응답의 `result_id`로 `GET /reports` 목록에 결과가 나타나는지 확인한다.
3. 목록에서 결과를 선택하고 `POST /reports/{result_id}/export-readiness`를 호출한다.
4. 미국 리포트에서 상태별 항목과 다음 행동을 보여 준다.
5. 새로고침 후 `GET /reports/{result_id}/readiness`로 같은 readiness 결과를 다시 표시한다.

이 흐름의 readiness 문구는 법적 적합성이나 미국 수출 가능 여부를 확정하지 않고, 준비 필요 자료와 추가 확인 사항을 안내해야 한다.

## 응답: `CheckReport`

```jsonc
{
  "findings": [            // 위반으로 지목된 문구들(합법은 여기 없음)
    {
      "span": "미백에 도움",      // 위반 표현(현재는 문장 전체 = 하이라이트 대상)
      "sentence": "…",           // span이 속한 원문 문장
      "violation_type": "2호_기능성오인",
      "legal_basis": "화장품법 제13조 제1항 제2호 (기능성 오인)",
      "legal_basis_text": "기능성화장품이 아닌 화장품을 기능성화장품으로 잘못 인식할 우려가 있거나 기능성화장품의 안전성ㆍ유효성에 관한 심사결과와 다른 내용의 표시 또는 광고", // 조항 원문 전체(2026-08-15 추가). 원문 없는 유형은 null
      "flag": "검토필요",          // 위반 | 검토필요 (v1.8: 위험도 고/중/저 폐지)
      "explanation": "… (전성분 대조: 나이아신아마이드 확인됨, 기준 2~5%, 등록 여부 불명, 단정 못 함)",
      // 이미지 입력이면 타일 밴드 좌표(원본 이미지 y픽셀)와 원본 크기가 실린다.
      "location": {
        "tile": "detail_000_t00.png", "order": 0,
        "y_start": 0, "y_end": 1480, "source_h": 9000, "source_w": 1000
      }
    }
  ],
  "unjudged": [           // 판정 실패로 못 가린 문장(= '재검사 필요', 합법 아님)
    // 문구-only 입력이면 tile·좌표가 모두 null.
    { "sentence": "…", "location": { "tile": null, "order": 1, "y_start": null, "y_end": null, "source_h": null, "source_w": null } }
  ],
  "summary": {
    "region": "KR",
    "n_sentences": 5,     // 판정에 투입된 문장 수
    "n_findings": 3,      // findings 총 건수(위반+검토필요)
    "n_violation": 2,     // flag=위반 건수
    "n_needs_review": 1,  // flag=검토필요 건수
    "n_unjudged": 0,      // 미판정 문장 수(검토필요와 다른 개념, 아래 참조)
    "counts_by_type": { "1호_의약품오인": 1, "2호_기능성오인": 1, "5호_거짓과장기만": 1 }
  },
  "result_id": "a3Fk9..."  // 저장됐으면 다시 보기 id. 미저장(stub·DB없음·저장실패)이면 null
}
```

### 위반 vs 검토필요 (v1.8, 중요)
위험도(고/중/저) 등급을 폐지하고 **위반/검토필요 이진 플래그**로 바꿨다(FR-5·FR-7). "근거 있으면 위반, 근거 없으면 검토필요."
- **1호(의약품오인)·5호(거짓과장기만)**: 지금은 항상 `위반`. RagJudge(규칙집 대조)가 아직 없어 대조 수단 자체가 없다. recall 우선 원칙상 근거 없다고 함부로 낮추지 않는다.
- **2호(기능성오인)**: `ingredients`로 성분 정합을 실제로 대조할 수 있어 그 결과를 쓴다.
  - 고시원료가 전성분에 **없음** → `위반` (근거로 확증)
  - 고시원료가 전성분에 **있음** → `검토필요` (원료는 있으나 그 제품이 실제 기능성 심사·등록을 받았는지는 알 수 없어 단정 못 함)
  - `ingredients` **미입력** → `검토필요` (대조 근거 자체가 없음)

`flag`가 `검토필요`일 때 `explanation`에 괄호로 이유가 붙는다:
- `(전성분 대조: 나이아신아마이드 확인됨, 기준 2~5%, 등록 여부 불명, 단정 못 함)`
- `(전성분 대조: 미백 고시원료가 전성분에 없음, 위반 소지 큼)`. 이 경우는 `flag=위반`
- `(전성분 미입력, 성분 정합 확인 못 함)`

**`unjudged`와 헷갈리지 말 것**: `unjudged` = 판정 자체를 못함(VLM 호출 실패). `검토필요` = 판정은 했는데 근거가 약해서 확정 못함. 둘 다 "위반으로 확정 못 함"이라는 공통점 때문에 헷갈리기 쉽지만 서로 다른 필드다.

### 하이라이트 2모드 (디자이너용)
- **이미지 입력**: `location.tile`이 채워짐 → 원문 이미지(해당 타일) 위에 표시. 추가로 `y_start`·`y_end`(원본 이미지 세로 픽셀 범위)와 `source_h`·`source_w`(원본 크기)가 실려, 원본 위에 **밴드(가로 띠)를 하이라이트**할 수 있다. 밴드는 그 문장이 나온 타일의 세로 범위다.
- **문구-only 입력**: `location.tile`이 `null` → 붙여넣은 텍스트에서 `span` 스팬 하이라이트. 좌표는 전부 `null`.
- `location.order`는 문장 순서(0부터).
- **밴드는 타일 단위, 문장 단위 아님**: OCR이 글자 bbox를 안 줘서 문장 정밀 좌표는 없다. 같은 타일의 여러 문장은 같은 밴드(`y_start`~`y_end`)를 공유한다. 원본 축척 환산은 `source_h`/`source_w`로 한다(표시 이미지가 리사이즈됐으면 비율만 곱하면 됨).

### 미판정(unjudged) 처리 (중요)
정책상 **미탐(위반을 놓침)이 제일 나쁘다.** 판정 실패 문장을 '합법'으로 보여주면 위반이 숨는다. 그래서 실패 문장은 findings에도 합법에도 넣지 않고 `unjudged`로 분리한다. UI는 이를 **"판정 못 함, 재검사 필요"** 상태로 보여줘야 한다(안전으로 오인 금지).

## 값 목록 (enum)
- `region`: `KR`, `US`
- `violation_type`: `합법`, `1호_의약품오인`, `2호_기능성오인`, `5호_거짓과장기만`, `대상외`
  - findings에 담기는 건 위반 3종(1·2·5호)뿐. `합법`·`대상외`는 finding을 안 만든다.
  - 화장품은 3호가 삭제된 조항이라 없다. 거짓·과장·기만은 현행법상 4호이나, 2026.11.27
    시행 개정법에서 AI 생성물 관련 조항이 신설 4호로 들어오며 5호로 밀린다. 우리는
    개정법 기준(5호)을 쓴다(상세: `reference/cosmetic_kr/statute/law_article_13.md`).
- `flag`: `위반`, `검토필요` (v1.8. 예전 `risk`(고/중/저)는 폐지됨)

## 샘플 픽스처
`backend/fixtures/` (스키마 100% 유효, 실제 판정 아닌 예시):
- `check_report_image.json`: 이미지 입력(타일 하이라이트), 1·2·5호 골고루
- `check_report_text.json`: 문구-only(스팬 하이라이트)
- `check_report_with_unjudged.json`: 미판정 상태 포함

## 실행
```bash
cd backend
./venv/bin/python scripts/run_api.py            # 서버 (localhost:8000, /docs)
./venv/bin/python scripts/dump_openapi.py       # openapi.json 갱신
./venv/bin/python scripts/make_fixtures.py      # fixtures/*.json 갱신
```
- 판정기 기본은 Gemini(`GOOGLE_API_KEY` 필요). 키 없이 UI만 붙일 땐 `JUDGE_KIND=stub`(키워드 더미 판정)로 서버를 띄우면 된다.
- CORS는 개발 편의상 전체 허용(`*`).
