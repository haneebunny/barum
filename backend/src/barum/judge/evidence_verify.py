"""증빙 이미지 대조 (에이전틱 판정 2단계).

1단계(`reference/evidence_claim.py`)가 고른 문장에 대해, 광고에 첨부된 증빙 문서를
**실제로 읽어** 제품명·시험항목이 그 주장과 맞는지 본다.

왜 필요한가: 에스코 사례에서 광고는 "제주 시카 카밍 세럼은 미백 주름개선 2중 기능성을
보고한 제품입니다"라며 "결과 확인서"를 붙였는데, 그 확인서는 **다른 제품**("에스코 로즈
피디알엔 리페어 앰플")의 **피부 첩포 자극시험** 결과지였다. 제품명도 시험항목도 무관했다.
독립된 두 LLM이 텍스트만 보고 둘 다 못 잡았고, 한쪽은 "근거 이미지 제시됨"을 이유로
합법으로까지 판정했다. **문서가 있다는 것과 그 문서가 이 제품·이 주장과 맞는다는 것은
별개다**(상세: `docs/result/2026-08-15_확장정답셋_인용검증_보고서.md` §2).

비용 때문에 아무 문장에나 돌리지 않는다. 1단계가 고른 문장 중 2호(기능성) 주장에만
돌린다(팀장 확정 2026-08-19).

**⚠ 아직 파이프라인에 배선하지 않았다.** 배선 전 검증(양방향)은 끝났다. 남은 건
1단계 필터(`reference/evidence_claim.py`, PR #191)가 먼저 머지돼야 `run_check`에
붙일 수 있다는 것뿐이다.

확인된 것 — 위조를 잡는가 (에스코 원본 이미지, "2중 기능성" 클레임, 2026-08-19):
- doc_product_name="에스코 로즈 PDRN 리페어 앰플"(제품명 불일치), claim_match=False
  (자극시험이 미백·주름 클레임을 못 뒷받침) → is_mismatch=True, 정확히 격상.
- 제품명을 안 넘겨도 시험항목만으로 잡힌다(팀장 확정 2번 케이스가 실제로 동작).

확인된 것 — 진짜를 오판 안 하는가 (같은 페이지, "피부 무자극 테스트" 클레임, 2026-08-19
claim_match 프롬프트 수정 후 재검증):
- doc_product_name="에스코 제주 시카 카밍 세럼"(제품명 일치), claim_match=True(자극시험
  → 민감성 사용적합은 의미상 정합) → is_mismatch=False. **이전엔 여기서 claim_match=False가
  나와 정직한 광고를 위반으로 오격상했었다(아래 "고친 것" 참고). 지금은 재현 안 됨.**

**고친 것: claim_match 기준이 너무 엄격했다.**
판정 기본 provider(gpt-5-mini)는 증빙서 잔글씨를 **못 읽는다**. 진단해보니 배지·제목
같은 큰 글씨("미백, 주름 2중 기능성", "결과 확인서")만 인식하고 정작 제품명·시험항목이
있는 표 안 잔글씨는 전부 unknown이었다(2배 확대해도 동일). OCR provider(Gemini)로
바꾸니 "에스코 로즈 피디알엔 리페어 앰플"·"피부 첩포에 의한 일차자극 인체적용시험"까지
정확히 읽었다. **이 단계는 반드시 OCR provider로 호출해야 한다.**

원래 프롬프트는 "시험 항목이 주장을 뒷받침하는가"만 물어서, 모델이 문구가 토씨까지
같아야 한다고 과대해석해 "피부 첩포 자극시험"과 "민감성 사용적합"처럼 의미상 통하는
쌍도 무관하다고 판단했다. VERIFY_PROMPT에 일치/불일치 예시 쌍(자극시험 -> 무자극·
민감성적합은 정합, 자극시험 -> 미백·주름 기능성은 불일치)을 명시해 해결했다.
"""

import io
from dataclasses import dataclass

from barum.vlm import VLM

# 대조 결과를 못 믿을 때 쓰는 값. 모르면 기존 판정을 유지한다(격상도 강등도 안 함).
_UNKNOWN = "unknown"

VERIFY_PROMPT = """이 이미지는 화장품 광고의 일부다. 광고 문구 옆에 시험성적서·인증서·
결과확인서 같은 증빙 문서 이미지가 붙어 있을 수 있다.

광고가 하는 주장: "{claim}"
광고 중인 제품명: {product}

증빙 문서를 찾아 읽고 아래를 판단하라. 문서가 작아도 최대한 읽어라.

1. has_document: 증빙 문서 이미지가 실제로 붙어 있는가? (배지·로고·아이콘만 있고
   문서가 없으면 false)
2. doc_product_name: 그 문서에 적힌 제품명을 그대로 옮겨라. 못 읽으면 "unknown".
3. doc_test_item: 그 문서의 시험·심사 항목을 그대로 옮겨라(예: "피부 첩포에 의한
   원발자극 인체적용시험", "미백 기능성 심사"). 못 읽으면 "unknown".
4. product_match: 문서의 제품명이 광고 중인 제품과 같은가? ("unknown"이면 unknown)
5. claim_match: 문서의 시험 항목이 광고가 하는 주장을 뒷받침하는가? 시험 종류와 주장의
   "의미"가 통하면 true다. 문구가 토씨 하나까지 같아야 하는 게 아니다.
   - 일치 예: 피부 자극·첩포·원발자극 시험 -> "무자극"·"저자극"·"민감성 피부 사용
     적합"·"순한" 주장 (자극이 없다는 시험 결과가 자극 없음 주장을 뒷받침한다)
   - 불일치 예: 피부 자극·첩포 시험 -> "미백"·"주름개선"·"기능성" 주장 (자극이 없다는
     것과 미백 효과가 있다는 것은 무관하다)
   - 애매하면(둘 다 아니면) 억지로 true/false를 정하지 말고 "unknown".
   못 읽으면 "unknown".

추측하지 마라. 읽히지 않으면 "unknown"이라고 답하라. 틀린 단정보다 unknown이 낫다.

JSON으로만 답하라:
{{"has_document": true/false, "doc_product_name": "...", "doc_test_item": "...",
  "product_match": true/false/"unknown", "claim_match": true/false/"unknown"}}"""


@dataclass
class EvidenceVerdict:
    """증빙 대조 결과. 판정 격상·강등의 근거가 된다."""

    has_document: bool
    doc_product_name: str
    doc_test_item: str
    product_match: object  # True | False | "unknown"
    claim_match: object

    @property
    def is_mismatch(self) -> bool:
        """증빙이 주장과 어긋나는가. 위반 격상의 조건.

        제품명이 다르거나 시험항목이 무관하면 어긋난 것이다. 둘 중 하나만 확정돼도
        충분하다 - 에스코는 둘 다 어긋났지만, 제품명을 못 읽어도 시험항목만으로 잡힌다
        (제품명 미입력 케이스 대응, 팀장 확정 2026-08-19).
        """
        if not self.has_document:
            return False  # 문서가 없으면 대조할 게 없다. 별개 문제다.
        return self.product_match is False or self.claim_match is False

    @property
    def is_verified(self) -> bool:
        """증빙이 주장을 실제로 뒷받침하는가. 합법 강등의 조건.

        **둘 다 확정될 때만 True다.** 강등은 위험한 방향이라(새 미탐 경로가 된다)
        하나라도 unknown이면 기존 판정을 유지한다.
        """
        return (
            self.has_document
            and self.product_match is True
            and self.claim_match is True
        )


def _coerce(value: object) -> object:
    """모델이 준 값을 True/False/"unknown" 셋 중 하나로 정규화한다."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    return _UNKNOWN


def crop_band(image_bytes: bytes, y_start: int | None, y_end: int | None,
              pad: int = 400) -> bytes:
    """문장이 있는 세로 구간을 잘라 낸다. 좌표가 없으면 원본 그대로.

    상세페이지는 세로로 매우 길다(실측 18,376px). 통째로 보내면 비싸고 모델도 작은
    글씨를 놓친다. 증빙 문서는 보통 그 주장 문구와 같은 높이의 옆칸에 있으므로,
    문장 밴드에 여유(pad)를 두고 가로 전폭을 자르면 문서까지 함께 들어온다.
    """
    if y_start is None or y_end is None:
        return image_bytes
    from PIL import Image

    im = Image.open(io.BytesIO(image_bytes))
    top = max(0, y_start - pad)
    bottom = min(im.height, y_end + pad)
    out = io.BytesIO()
    im.crop((0, top, im.width, bottom)).save(out, format="PNG")
    return out.getvalue()


def verify_evidence(
    vlm: VLM, image_bytes: bytes, claim: str, product_name: str | None
) -> EvidenceVerdict | None:
    """증빙 문서를 읽어 주장과 대조한다. 실패하면 None(기존 판정 유지).

    VLM 호출은 과금이라 재시도하지 않는다(CLAUDE.md E). 실패는 예상된 실패로 보고
    None을 돌려 호출부가 판정을 그대로 두게 한다.
    """
    prompt = VERIFY_PROMPT.format(
        claim=claim, product=product_name or "(제품명 미입력, 시험항목만 대조하라)"
    )
    try:
        res = vlm.generate_json(prompt, [image_bytes])
    except Exception as e:  # noqa: BLE001
        print(f"    [evidence skip] 증빙 대조 실패: {type(e).__name__}: {e}")
        return None
    if not isinstance(res, dict):
        return None
    return EvidenceVerdict(
        has_document=bool(res.get("has_document")),
        doc_product_name=str(res.get("doc_product_name") or _UNKNOWN),
        doc_test_item=str(res.get("doc_test_item") or _UNKNOWN),
        product_match=_coerce(res.get("product_match")),
        claim_match=_coerce(res.get("claim_match")),
    )
