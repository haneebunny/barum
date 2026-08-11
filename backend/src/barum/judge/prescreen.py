"""홀드아웃 사전 선별 — 정제 + product_type 판별 + 유형 힌트를 한 번에.

⚠️ 여기서 나오는 `hint`는 **층화 추출용 내부 정보**다. 라벨러에게 주는 시트에는
절대 넣지 않는다(정답을 알려주면 홀드아웃이 무의미해진다).
"""

from barum.vlm import VLM

PRESCREEN_PROMPT = """너는 식약처 「식품 등의 표시·광고에 관한 법률」 위반 광고를 선별하는 실무자다.
아래는 한 상품의 상세페이지에서 OCR로 뽑은 문장 목록이다.

## 상품명
{product_name}

## 문장 목록
{numbered}

## 할 일

### 1) product_type 판정
이 상품이 **건강기능식품**인지 **일반식품**인지 판정하라.

- `건강기능식품`: 건강기능식품 인정마크·"기능성 내용"·"영양·기능정보" 표기,
  건강기능식품 문구가 **제품 자체**를 가리키는 경우
- `일반식품`: 일반식품임이 드러나거나, "본 제품은 건강기능식품이 아닙니다" 표기
- `불명`: 위 근거가 없거나 애매한 경우. **애매하면 반드시 불명로 하라.**

주의: "3종 건강기능식품 주원료 배합"처럼 **원료**를 설명하는 문구는 제품이
건강기능식품이라는 근거가 아니다. 오히려 일반식품이 기능성을 흉내낸 정황일 수 있다.

### 2) 문장별 선별
각 문장에 대해 판정 대상인지 정하라.

`keep=false` (홀드아웃에서 제외):
- 가격·배송·통관·결제·교환/반품·고객센터 안내
- 제품명·용량·회사명·인증마크 이름 같은 단순 표기 조각
- 성분 함량표·영양성분표의 나열
- 의미를 알 수 없는 짧은 조각, 영문/숫자만 있는 것

`keep=true` (판정 대상): 소비자에게 제품의 효과·특성을 주장하는 **광고 문구**

### 3) 유형 힌트
`keep=true`인 문장에만 아래 중 하나를 `hint`로 붙여라.

- `합법` — 위반 아님
- `1호_질병표방` — 질병명·증상의 예방·치료·개선을 표방 (예: "관절염 개선", "변비 개선")
- `2호_의약품오인` — 의약품 명칭 사용, 의약품 대체·효능 증대 (예: "다이어트약", "위고비", "GLP-1")
- `3호_건기식오인` — **일반식품인데** 건기식 기능성을 표현 (예: "체지방 감소", "면역력 강화")
- `4호_거짓과장` — 인정 기능성에 없는 신체 작용 (예: "붓기 제거", "피부 탄력")
- `5호_소비자기만` — 후기·체험기, 전문가 추천, 원재료 효능을 제품 효능으로
- `대상외` — 6~10호로 보이는 것

3호 판정에는 위 1)의 product_type을 반영하라. 건강기능식품이면 "체지방 감소"는 합법이다.

JSON으로만 답하라:
{{"product_type": "...", "product_type_evidence": "판정 근거 한 줄",
  "items": [{{"i": 0, "keep": true, "hint": "3호_건기식오인"}}]}}"""

LABELS = [
    "합법", "1호_질병표방", "2호_의약품오인",
    "3호_건기식오인", "4호_거짓과장", "5호_소비자기만", "대상외",
]


def prescreen_product(record: dict, vlm: VLM) -> dict:
    """상품 1개의 OCR 결과를 선별한다.

    입력: run_ocr.py가 만든 레코드 / 출력: product_type + 문장별 keep·hint
    """
    sentences = record["sentences"]
    numbered = "\n".join(f"{i}. {s['text']}" for i, s in enumerate(sentences))
    prompt = PRESCREEN_PROMPT.format(
        product_name=record.get("product_name", ""), numbered=numbered
    )

    result = vlm.generate_json(prompt, [])
    ptype = result.get("product_type", "불명")
    if ptype not in ("건강기능식품", "일반식품", "불명"):
        ptype = "불명"

    # 모델이 items를 한 겹 더 감싼 배열로 뱉는 경우가 있어 평탄화한다.
    raw_items = result.get("items", [])
    flat = []
    for item in raw_items if isinstance(raw_items, list) else []:
        flat.extend(item) if isinstance(item, list) else flat.append(item)

    by_index = {}
    for item in flat:
        if not isinstance(item, dict):
            continue
        try:
            by_index[int(item["i"])] = item
        except (KeyError, ValueError, TypeError):
            continue  # 인덱스 깨진 항목은 버린다(해당 문장은 keep=false 처리)

    kept = []
    for i, s in enumerate(sentences):
        item = by_index.get(i)
        if not item or not item.get("keep"):
            continue
        hint = item.get("hint")
        kept.append({**s, "hint": hint if hint in LABELS else "합법"})

    return {
        "product_id": record["product_id"],
        "product_name": record.get("product_name", ""),
        "product_type": ptype,
        "product_type_evidence": result.get("product_type_evidence", ""),
        "sentences": kept,
        "n_input": len(sentences),
        "n_kept": len(kept),
    }
