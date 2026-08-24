"""모듈별 이미지 생성 오케스트레이션 (FR-13, create 모드).

계획된 모듈마다 배경 이미지를 만든다. **텍스트도 제품도 그리지 않는다.** 원료·질감·추상
배경만 만들고, 문구는 프론트가 위에 얹고 제품샷은 판매자가 직접 올린다.

제품을 그리게 했더니 모델이 라벨에 깨진 글자를 박아 넣었다("AYN", "D-OIBELRAMOLAI" 등,
2026-08-18 실측). "글자 금지"라고 써도 안 지켜진다. 규제 준수를 검사하는 서비스가 가짜
제품 라벨을 만들어내면 자기모순이라, 아예 제품을 안 그리는 쪽으로 바꿨다(하니 확정).

과금 호출이라 모듈 단위로 실패를 격리한다. 한 모듈이 실패해도 나머지는 계속 만들고,
실패분은 `ModuleImage.status="skipped"`에 사유를 남긴다(조용히 빠지지 않게).

판매자가 제품사진을 올리면(`req.product_photo_ids`) 얘기가 달라진다. 그때는 그 실제
사진을 참조로 넘겨 배경과 합성한다(AI 배경·연출 합성, 팀장 승인 방식 A). 이 경우엔
위 "제품을 안 그린다" 원칙이 뒤집힌다: 상상으로 새로 그리는 대신 참조 사진 속 실제
제품을 유지하며 그 주위만 합성하므로 가짜 라벨 문제가 없다.
"""

from concurrent.futures import ThreadPoolExecutor

from barum.models import CanvasBackground, GenerateRequest, LayoutModule, LayoutPlan, ModuleImage
from barum.reference.impersonation import check_impersonation

# 한 요청에 만들 이미지 수 상한. 과금 호출이라 모듈이 12개여도 다 만들지 않는다.
DEFAULT_MAX_IMAGES = 6

# 제품 종류별 질감 예시. 고정 목록 하나를 전부에 쓰면 토너에 크림 이미지가 나오는
# 식으로 제형이 안 맞는다(2026-08-19 실측, 팀장 지적, "촉촉 히알루론산 토너"인데
# 흰 크림 덩어리가 그려짐. build_image_prompt가 layout_plan.product_type을 아예
# 안 받고 예시에 "크림 질감"이 하드코딩돼 있던 게 원인).
_TEXTURE_HINTS: dict[str | None, str] = {
    "토너": "투명하거나 옅은 색의 맑은 액체, 튀는 물방울, 촉촉하게 젖은 표면. 걸쭉하거나 불투명한 질감은 넣지 마라",
    "세럼": "점도 있는 액상 방울, 유리 표면의 광택, 매끈하게 흐르는 액체 질감",
    "크림": "부드럽게 퍼바른 크림 스월, 뽀얗고 밀도 있는 질감",
    None: "잎, 물방울, 천, 돌 표면 같은 원료·소재 클로즈업(제품 제형은 특정하지 마라)",
}


def _texture_hint(product_type: str | None) -> str:
    """product_type에 맞는 질감 예시를 낸다. 모르는 종류거나 None이면 중립 힌트로 폴백."""
    return _TEXTURE_HINTS.get(product_type, _TEXTURE_HINTS[None])


# product_type별 기본 컬러톤·분위기. 인터뷰에서 값을 안 받았을 때 쓴다.
# 디디가 `layout_references/_vocabulary.json`의 `category_base_tone`으로 확정한 값
# (2026-08-19, PR #181). 이 파일의 hue_direction은 템플릿 색이 아니라 이 기본값
# 후보로 쓰라고 명시돼 있다(팀장 정정 커밋 71b3ebb 근거). 어휘집에 없는 종류(product_type
# 매핑 밖이거나 None)는 기존 중립 기본값으로 폴백.
_TONE_DEFAULTS: dict[str | None, str] = {
    "세럼": "투명・산뜻한 톤, 라이트 민트/세이지 계열",
    "토너": "맑고 산뜻한 톤, 워터 블루/민트 계열",
    "크림": "부드럽고 편안한 톤, 소프트 아이보리/베이지 계열(연한 톤만, 브라스·에스프레소 계열 금지)",
    "앰플": "집중・고농축 느낌, 딥그린 또는 딥네이비 + 화이트 대비",
    None: "투명하고 깨끗한 톤, 미니멀하고 차분한 분위기",
}


def _resolve_tone(req: GenerateRequest, product_type: str | None) -> str:
    """이번 생성 전체에 쓸 컬러톤·분위기 문구를 하나로 정한다.

    인터뷰에서 받은 값(req.color_tone·mood)이 있으면 그걸 우선한다. 없으면
    product_type 기본값, 그것도 없으면 전체 기본값(_TONE_DEFAULTS[None])으로
    폴백한다. **이 함수가 (req, product_type)에 대해 항상 같은 문자열을 내는 게
    핵심이다.** 그래야 6장 전부가 같은 아트 디렉션 문구를 받아서 한 페이지처럼
    읽힌다(지금까지는 모듈마다 톤 지정이 아예 없어서 색감·조명이 제각각이었다,
    2026-08-19 팀장 지적).
    """
    parts = [p for p in (req.color_tone, req.mood) if p]
    tone = ", ".join(parts) if parts else _TONE_DEFAULTS.get(product_type, _TONE_DEFAULTS[None])
    # 프리셋의 레이아웃 방향을 아트 디렉션에 함께 싣는다. 텍스트 프롬프트가 받는
    # 것과 같은 값이라 카드 전체가 한 방향으로 묶인다. 이 함수가 (req, product_type)에
    # 대해 항상 같은 문자열을 낸다는 성질은 그대로다.
    direction = getattr(req, "layout_direction", None)
    return f"{tone}. {direction}" if direction else tone


_PROMPT = """화장품 상세페이지에 쓸 **배경 이미지**를 만들어라.

{text_rule}

제품 종류: {product_name}{product_type_line}
이 배경의 역할: {purpose}
{copy_line}

**전체 컬러톤·분위기(이 상세페이지의 다른 배경 이미지들과 반드시 통일할 것): {tone}**

무엇을 그릴지:
{composition_lines}
{body_part_line}
- **가로가 세로보다 긴 비율로 그려라(가로:세로 = 3:2 정도).** 카드 위쪽에 눕혀
  얹히는 배경이라 세로로 긴 이미지는 화면을 아래로 한없이 늘린다. 세로로 긴
  구도로는 절대 그리지 마라.
- 위에 명시한 컬러톤·분위기를 따를 것
- **선명하고 또렷하게 그려라.** 안개 낀 듯 뿌옇거나 과도한 소프트포커스·흐림 효과는
  쓰지 마라. 실제 상품 사진처럼 디테일과 초점이 또렷해야 한다

절대 넣지 말 것:
{product_instruction}
- **글자·문구·숫자·로고를 새로 넣지 마라**(맨 위 최우선 규칙 재확인).
- **사람 얼굴은 어떤 형태로도 넣지 마라**(클로즈업뿐 아니라 원거리·실루엣도 금지).
- 의사·약사·전문가를 연상시키는 인물이나 소품(가운·청진기 등)을 넣지 마라.
{staged_look_forbidden}
- 시험 결과 그래프나 차트를 만들지 마라.

화면 한쪽은 비교적 비워 둬라. **그 빈 자리는 끝까지 비어 있어야 한다.** 거기에
글자나 소품을 채워 넣지 마라. 비어 보이는 건 잘못된 게 아니라 의도된 것이다."""

# layout_type별 "무엇을 그릴지" 지시. 예전엔 전 모듈에 "질감 클로즈업 또는 추상
# 배경(색·빛 그라데이션)"이 동일하게 들어가서, 모델이 매번 더 쉬운 쪽(추상 그라데이션)
# 으로 수렴했다(2026-08-19 팀장 실측 지적: 6장 이어붙여보니 대부분 "그냥 초록 블러"
# 였고, "상세페이지에 쓰기 힘들 만큼 추상적"·"전체적으로 뿌옇다"는 두 가지 문제 확인).
# 사진성이 필요한 유형은 "그라데이션만" 옵션을 아예 빼고 구체적 질감을 강제한다.
# 사진성이 필요없는 유형(icon_grid·table_info·banner_strip)은 아예 이미지 생성을
# 스킵한다(_NO_IMAGE_LAYOUT_TYPES, generate_module_images에서 처리).
_COMPOSITION_BY_LAYOUT_TYPE_TEMPLATES: dict[str, str] = {
    "hero_fullbleed": (
        "- 넓은 분위기컷으로 그려라. 공간감이 느껴지는 전체 장면 안에 구체적 질감이\n"
        "  또렷이 보여야 한다: {hint}. **순수 색상 그라데이션만으로 채우지 마라.**\n"
        "  실사 상세페이지 사진처럼 보여야 한다"
    ),
    "image_text_split": (
        "- 화면 한쪽에 치우친 구체적 질감 클로즈업 하나만 그려라: {hint}\n"
        "  (반대쪽은 아무것도 없이 확실히 비워라). 색상 그라데이션만으로 채우지 마라"
    ),
    "mood_macro": (
        "- 극단적인 클로즈업으로 구체적 질감 하나를 프레임 가득 채워라: {hint}\n"
        "  순수 그라데이션·색면은 안 된다. 여백 없이 꽉 채워라"
    ),
    "clinical_bar_compare": "- 짙은 톤의 단색 또는 은은한 그라데이션 배경만 그려라(수치·막대는 프론트가 얹는다)",
    "clinical_photo_compare": "- 차분한 단색 또는 은은한 그라데이션 배경만 그려라(비교 사진은 판매자가 올린다)",
    # 아래 4종은 PR #198에서 빠져 있어서 전부 _DEFAULT_COMPOSITION("제형 클로즈업")을
    # 탔다. 그 결과 mood_macro와 사실상 같은 지시를 받아 한 페이지에 제형 사진이 3장씩
    # 중복됐다(2026-08-20 팀장 지적, 실측 확인). 어휘집(_vocabulary.json) 정의에 맞춰
    # 서로 겹치지 않게 채운다.
    "section_statement": (
        "- **질감 클로즈업을 그리지 마라.** 이 유형은 어휘집상 '이미지 없이(또는 최소),\n"
        "  배경색 블록 하나로 존재감'이다. 넓고 차분한 단색 배경면만 그려라.\n"
        "  아주 은은한 재질감(종이·패브릭·석고 표면 정도)까지만 허용하고, 주제가 되는\n"
        "  피사체는 넣지 마라"
    ),
    "card_list_repeat": (
        "- 카드가 세로로 반복해서 얹힐 자리다. 어느 위치를 잘라 써도 어색하지 않게\n"
        "  **균일한 배경면**을 그려라: 은은한 재질감이 고르게 퍼진 표면. 한쪽에만\n"
        "  시선이 쏠리는 강한 피사체는 넣지 마라"
    ),
    "step_list": (
        "- 사용 순서를 설명하는 자리다. 제품을 쓰는 상황이 연상되는 **정돈된 공간**을\n"
        "  그려라(세면대 옆 선반, 정리된 테이블 등). 제형 질감 클로즈업은 쓰지 마라"
    ),
    "lineup_strip": (
        "- 제품 여러 개가 가로로 늘어서 얹힐 자리다. **가로로 긴 구도의 평평한 받침면**\n"
        "  (선반·단상·테이블 상판)을 그리고 그 위는 비워 둬라. 제품은 판매자가 올린다"
    ),
}

_DEFAULT_COMPOSITION = (
    "- 이 제품 제형에 맞는 질감·소재의 클로즈업: {hint}\n"
    "- 또는 색·빛·그라데이션 위주의 추상 배경(제형 질감 없이)"
)

# 같은 layout_type이 한 페이지에 여러 번 나오면 프롬프트가 사실상 같아진다
# (구도 지시·질감 힌트·톤 문구가 전부 layout_type/product_type만의 함수라서).
# 2026-08-20 실측: section_statement 2개 + mood_macro 1개가 거의 같은 제형 방울
# 사진으로 나왔다. 등장 순서로 결정적으로 갈라준다(같은 입력 -> 같은 결과 유지).
_VARIATION_DIRECTIVES: tuple[str, ...] = (
    "",  # 첫 등장은 변주 지시 없음(기존 동작 유지)
    (
        "- **이 페이지의 앞선 같은 유형 이미지와 반드시 다르게 그려라.**"
        " 다른 소재·다른 각도로 바꾸고, 더 멀리서 넓게 잡아라"
    ),
    (
        "- **이 페이지의 앞선 같은 유형 이미지들과 반드시 다르게 그려라.**"
        " 또 다른 소재를 쓰고, 위에서 내려다보는 각도로 바꿔라"
    ),
    (
        "- **이 페이지의 앞선 같은 유형 이미지들과 반드시 다르게 그려라.**"
        " 아직 안 쓴 소재를 골라 비스듬한 각도로, 화면을 더 비워서 그려라"
    ),
)


def _variation_line(variation_index: int) -> str:
    """같은 layout_type의 몇 번째 등장인지에 따라 변주 지시를 낸다.

    목록을 넘어가면 마지막 지시를 재사용한다(4번 이상 반복되는 경우는 드물고,
    그때도 "앞선 것들과 다르게"라는 방향은 유효하다).
    """
    if variation_index <= 0:
        return ""
    return _VARIATION_DIRECTIVES[min(variation_index, len(_VARIATION_DIRECTIVES) - 1)]


def _composition_lines(layout_type: str, product_type: str | None, variation_index: int = 0) -> str:
    """layout_type별 "무엇을 그릴지" 지시를 낸다. 카탈로그에 없는 유형은 기존
    범용 문구(질감 또는 추상 배경)로 폴백한다.

    variation_index는 같은 layout_type이 이 페이지에서 몇 번째로 등장하는지다.
    0이면 지시가 안 붙어 기존 동작 그대로다.
    """
    hint = _texture_hint(product_type)
    template = _COMPOSITION_BY_LAYOUT_TYPE_TEMPLATES.get(layout_type, _DEFAULT_COMPOSITION)
    lines = template.format(hint=hint)
    variation = _variation_line(variation_index)
    return f"{lines}\n{variation}" if variation else lines


# 사진성 배경이 필요없는 layout_type. 어휘집 정의상 아이콘·표·배너 텍스트라 사진
# 배경 슬롯이 아니다. 지금까지는 여기도 이미지를 만들어서 프론트가 그냥 버리고
# 있었다(2026-08-19, 팀장 확인 후 스킵 승인).
_NO_IMAGE_LAYOUT_TYPES = frozenset({"icon_grid", "table_info", "banner_strip"})

# **section_statement는 일부러 넣지 않았다.** 프론트가 이 유형을 텍스트 블록으로만
# 렌더해서 이미지가 버려지는 건 맞다(2026-08-20 실측: 6장 중 2장). 그런데 이 값은
# LayoutModule.layout_type의 **기본값이자 카탈로그 밖 값의 폴백**이라(models.py,
# layout.py `_DEFAULT_LAYOUT_TYPE`), 스킵 목록에 넣으면 플래너가 layout_type을
# 빠뜨리기만 해도 이미지가 통째로 안 만들어진다. 낭비를 줄이려다 기능을 죽인다.
# step_list도 프론트에 이미지 분기가 없어 같은 상태다.
# 두 유형은 "프론트 렌더를 고칠지 / 백엔드에서 안 만들지"를 디자이너·프론트와
# 정해야 한다(PM 전달함).


# layout_type별 손·팔 허용 여부. "손으로 제품 바르는 장면"이 모든 모듈에 예시로
# 똑같이 들어가 있으면 모델이 매번 그리로 수렴한다(2026-08-19 실측·팀장 지적: 한
# 페이지 6장이 전부 손 장면으로 나옴). kind는 LLM이 자유롭게 짓는 문자열이라
# 커버리지를 보장 못 해서 layout_type을 쓴다.
_HAND_ALLOWED_LAYOUT_TYPES = frozenset({"hero_fullbleed", "step_list"})

_HAND_ALLOWED_LINE = (
    "- 필요하면 손·팔·뒷모습 등 얼굴이 안 보이는 신체 일부를 자연스럽게 넣어도 된다\n"
    "  (예: 손으로 제품을 바르는 장면). 얼굴은 절대 안 됨(아래 금지 목록 참고)"
)
_HAND_FORBIDDEN_LINE = "- 사람 신체(손·팔 포함)는 넣지 마라. 위 지시대로만 그려라"


def _body_part_line(layout_type: str) -> str:
    """모듈 구도 지시를 layout_type에 따라 가른다."""
    return _HAND_ALLOWED_LINE if layout_type in _HAND_ALLOWED_LAYOUT_TYPES else _HAND_FORBIDDEN_LINE


# "절대 넣지 말 것" 목록의 실제후기 금지 문구. **hero_fullbleed·step_list에서는
# 위 _HAND_ALLOWED_LINE과 자기충돌한다** - #312(라벨 버그)와 같은 계열의 프롬프트
# 자기충돌이다(2026-08-23, LangSmith 실 트레이스로 확인: 손 장면을 허용한 바로 그
# 프롬프트에 "손으로 직접 촬영한 듯한 스냅샷 구도... 얼굴이 없어도 금지다"가 볼드로
# 같이 박혀 있었다). #312와 똑같이 "무엇이 문제냐"가 아니라 "이 손 장면이 의도적으로
# 허용된 것이냐"로 갈라서, 열어준 손 장면과 안 부딪히게 좁힌다. 손이 금지된 나머지
# layout_type은 원래 문구 그대로 - 거기선 애초에 손 장면이 안 나오니 충돌도 없다.
_STAGED_LOOK_FORBIDDEN = (
    "- **실제 사용 후기·체험담처럼 보이는 연출을 만들지 마라**(사용 전후 비교, 손으로\n"
    "  직접 촬영한 듯한 스냅샷 구도 등). 얼굴이 없어도 금지다. 실제 후기로 오인되면\n"
    "  안 된다."
)
_STAGED_LOOK_FORBIDDEN_HAND_ALLOWED = (
    "- **일반 소비자가 스마트폰으로 찍은 듯한 캐주얼한 셀피·인증샷 구도는 만들지 마라**\n"
    "  (흔들린 각도, 어수선한 배경, 사용 전후 비교 등 실제 후기로 오인될 연출). 위에서\n"
    "  허용한 손 동작 장면은 이 금지 대상이 아니다 - 브랜드 화보처럼 정돈되고 의도적인\n"
    "  구도라면 손이 나와도 된다."
)


def _staged_look_forbidden_line(layout_type: str) -> str:
    """실제후기 금지 문구를 layout_type에 따라 가른다(_body_part_line과 같은 기준)."""
    return (
        _STAGED_LOOK_FORBIDDEN_HAND_ALLOWED
        if layout_type in _HAND_ALLOWED_LAYOUT_TYPES
        else _STAGED_LOOK_FORBIDDEN
    )


_NO_PRODUCT_INSTRUCTION = "- **제품(병·튜브·용기·패키지)을 그리지 마라.** 제품 사진은 판매자가 직접 올린다."
# 글자 금지 규칙. **참조 제품사진이 있느냐에 따라 갈린다.**
#
# 원래는 한 가지뿐이었고 "인쇄된 라벨 전부 포함"으로 라벨까지 금지했다. 참조 사진이
# 없을 때는 그게 맞다 - 모델이 그리는 라벨은 뭉개진 가짜 글자가 되기 때문이다(39b2b54).
#
# **그런데 참조 사진이 붙으면 이 규칙이 합성 지시와 정면으로 충돌한다.**
# 합성 지시는 "참조 사진 속 라벨을 그대로 유지하라"인데 최우선 규칙은 "라벨 금지"라,
# "최우선"이라고 두 번 강조된 쪽이 이겨서 **라벨 없는 빈 병**이 나왔다(2026-08-23 실측:
# 팀장이 제품사진을 올렸는데도 브랜드 글자가 하나도 없는 병이 생성됨).
#
# 구분은 "글자냐"가 아니라 **"네가 새로 쓰는 글자냐"**다. 참조 사진에 이미 인쇄돼
# 있던 라벨은 모델이 지어낸 글자가 아니라 실제 제품의 일부다.
_NO_TEXT_RULE = """# 최우선 규칙: 이 이미지에는 글자가 단 하나도 없어야 한다
읽을 수 있는 문자를 어떤 형태로도 그리지 마라. 한글·영문·숫자·로고·워터마크·
인쇄된 라벨 전부 포함이다. 글자처럼 보이는 장식적 흘림선도 안 된다.
아래에 제품명이 적혀 있지만 그건 **무엇을 그릴지 알려주는 정보일 뿐, 화면에
쓰라는 뜻이 아니다.** 제품명·브랜드명을 이미지 안에 절대 쓰지 마라.
완성된 이미지는 **글자가 하나도 없는 순수한 사진**이어야 한다."""

# 글자를 세 갈래로 가른다. **두 갈래로 나누면 참조 페이지의 광고 카피까지 따라 그린다**
# (2026-08-23 실측: 라벨은 살았는데 원본 상세페이지의 제목·본문·표를 통째로 복제했다).
# 모델 입장에선 그것도 "새로 쓴 글자가 아니"라서다. 기준은 **글자가 어디에 있느냐**다.
_KEEP_LABEL_TEXT_RULE = """# 최우선 규칙: 용기에 인쇄된 라벨만 남기고, 나머지 글자는 전부 없앤다
글자를 세 갈래로 구분하라.

1. **남길 것 — 참조 사진 속 제품 용기 표면에 인쇄된 것**
   브랜드명·제품명·용량 표기처럼 병·튜브·패키지에 직접 찍힌 글자다. 실제 제품의
   일부이므로 그대로 두어라. 지우거나 뭉개거나 철자를 바꾸지 마라.

2. **옮겨 그리지 말 것 — 참조 사진의 배경에 얹혀 있는 글자**
   광고 문구·제목·설명 문장·성분표·배지·워터마크가 여기 해당한다. 참조 사진에
   있더라도 **새 이미지에는 넣지 마라.** 그건 제품이 아니라 남의 페이지 디자인이다.

3. **새로 만들지 말 것 — 그 외 모든 글자**
   한글·영문·숫자·로고를 배경·연출에 새로 그리지 마라. 글자처럼 보이는 장식적
   흘림선도 안 된다.

아래 제품명은 **무엇을 그릴지 알려주는 정보일 뿐**이다. 화면에 쓰라는 뜻이 아니다.
결과는 **용기의 라벨 외에는 글자가 없는 사진**이어야 한다."""


_COMPOSITE_PRODUCT_INSTRUCTION = (
    "- **참조로 첨부된 실제 제품 사진 속 병·용기·패키지의 형태·라벨·색상을 그대로 유지하라.** "
    "제품을 다시 그리거나 상상해서 새로 만들지 마라. 배경·연출만 자연스럽게 그 주위에 합성하라."
)


def _copy_line(copy_text: str | None) -> str:
    """이 모듈에 실제로 실릴 카피를 프롬프트에 알려준다.

    전엔 플래너가 정한 한 줄 목적(`module.purpose`)만 보고 그렸다. 실제 문장은
    이미지보다 먼저 만들어지는데 넘기질 않아서 배경이 카피와 겉돌았다.

    **글자로 쓰라는 뜻이 아니라는 걸 같이 못박는다.** 안 그러면 모델이 이 문장을
    이미지에 그려 넣는다 — 참조 사진 라벨 건에서 확인한 것과 같은 함정이고,
    맨 위 글자 금지 규칙과 정면으로 충돌하는 입력이 된다.
    """
    text = (copy_text or "").strip().replace("\n", " ")
    if not text:
        return ""
    return (
        f"이 자리에 실릴 카피(참고용): {text[:200]}\n"
        "**이 카피는 어떤 장면을 그릴지 알려주는 정보일 뿐이다. "
        "이 문장을 이미지 안에 글자로 쓰지 마라.**"
    )


def build_image_prompt(
    module: LayoutModule,
    req: GenerateRequest,
    product_type: str | None = None,
    has_product_photo: bool = False,
    variation_index: int = 0,
    copy_text: str | None = None,
) -> str:
    """모듈 하나의 이미지 프롬프트를 만든다.

    product_type(플래너가 추측한 세럼/토너/크림 등)을 주면 그 제형에 맞는 질감
    예시를 넣는다. 안 주면 중립 힌트로 폴백한다(제형을 특정하지 않는 원료 클로즈업).
    컬러톤·분위기는 req와 product_type만으로 결정되므로(_resolve_tone), 같은
    요청의 모듈들은 전부 같은 톤 문구를 받는다. 호출자가 따로 안 맞춰줘도 된다.

    has_product_photo: 판매자가 올린 제품사진을 참조 이미지로 넘기는 경우(True)엔
    "제품을 그리지 마라"가 아니라 "참조 사진 속 실제 제품을 유지하며 합성하라"로
    지시가 바뀐다. 참조가 없을 땐 기존처럼 제품을 아예 안 그린다(가짜 라벨 방지,
    39b2b54 참고).

    module.layout_type으로 구도(_composition_lines)와 손·팔 허용 여부(_body_part_line)를
    가른다. 안 가르면 모든 모듈이 비슷한 추상 그라데이션이나 "손으로 제품 바르는
    장면"으로 수렴한다(2026-08-19 실측·팀장 지적).

    같은 layout_type 기준으로 실제후기 금지 문구도 가른다(_staged_look_forbidden_line).
    안 가르면 손 장면을 허용해 놓고 바로 아래에서 "손으로 찍은 듯한 구도 금지"가
    자기충돌해 손 장면이 억제된다(2026-08-23 LangSmith 트레이스로 확인, #312
    라벨 버그와 같은 계열).

    variation_index: 같은 layout_type이 이 페이지에서 몇 번째로 등장하는지(0부터).
    layout_type이 같으면 나머지 입력이 전부 같아 프롬프트가 거의 동일해지므로, 이
    값으로 소재·앵글·거리를 갈라준다(2026-08-20 실측: 같은 유형 3개가 거의 같은
    제형 사진으로 나왔다). 0이면 지시가 안 붙어 기존 동작 그대로다.
    """
    return _PROMPT.format(
        product_name=req.product_name or "화장품",
        product_type_line=f" ({product_type})" if product_type else "",
        purpose=module.purpose or module.kind,
        tone=_resolve_tone(req, product_type),
        composition_lines=_composition_lines(module.layout_type, product_type, variation_index),
        body_part_line=_body_part_line(module.layout_type),
        staged_look_forbidden=_staged_look_forbidden_line(module.layout_type),
        product_instruction=_COMPOSITE_PRODUCT_INSTRUCTION if has_product_photo else _NO_PRODUCT_INSTRUCTION,
        text_rule=_KEEP_LABEL_TEXT_RULE if has_product_photo else _NO_TEXT_RULE,
        copy_line=_copy_line(copy_text),
    )


def _user_controlled_text(module: LayoutModule, req: GenerateRequest) -> str:
    """사칭 가드가 검사할 부분만 뽑는다.

    조립된 프롬프트 전체를 검사하면 안 된다. 프롬프트에는 "의사를 넣지 마라" 같은
    금지 지시문이 들어 있어서, 키워드 가드가 우리 안전장치를 사칭으로 오인한다.
    가드가 막아야 할 건 사용자·LLM이 넣은 값(상품명, 모듈 목적, 컬러톤·분위기).
    컬러톤·분위기도 인터뷰 자유서술이라 검사 대상에 넣었다(2026-08-19 추가).
    """
    return f"{req.product_name or ''} {module.purpose or ''} {req.color_tone or ''} {req.mood or ''}"


_CANVAS_PROMPT = """화장품 상세페이지 **전체 배경**으로 쓸 세로로 아주 긴 이미지를 만들어라.

# 최우선 규칙: 이 이미지에는 글자가 단 하나도 없어야 한다
읽을 수 있는 문자를 어떤 형태로도 그리지 마라. 한글·영문·숫자·로고·워터마크 전부
포함이다. 아래에 제품명이 적혀 있지만 그건 **무엇을 그릴지 알려주는 정보일 뿐,
화면에 쓰라는 뜻이 아니다.** 완성된 이미지는 글자가 없는 순수한 사진이어야 한다.

제품 종류: {product_name}{product_type_line}

**전체 컬러톤·분위기: {tone}**

구성:
- **세로로 아주 긴 비율**(폭보다 세로가 3배 이상)로 그려라.
- 위에서 아래로 장면이 자연스럽게 이어지되, 구간마다 다른 소재가 보이게 하라.
  위쪽은 넓은 공간감, 가운데는 제형 질감({hint}), 아래쪽은 차분한 정물 연출.
- 전체가 하나의 톤으로 이어져야 한다. 구간마다 색감이 튀면 안 된다.
- **선명하고 또렷하게 그려라.** 뿌옇거나 과도한 소프트포커스는 쓰지 마라.

절대 넣지 말 것:
- **제품(병·튜브·용기·패키지)을 그리지 마라.** 제품 사진은 판매자가 직접 올린다.
- 글자·문구·숫자·로고·라벨을 넣지 마라(위 최우선 규칙 재확인).
- **사람 얼굴은 어떤 형태로도 넣지 마라**(원거리·실루엣도 금지).
- 의사·약사·전문가를 연상시키는 인물이나 소품을 넣지 마라.
- 시험 결과 그래프나 차트를 만들지 마라.

이 배경 위에 문구·표·모듈 이미지가 얹힌다. **곳곳에 비교적 비어 있는 구간을
남겨라.** 그 빈 자리는 끝까지 비어 있어야 하고, 거기에 무언가를 채워 넣지 마라."""


def build_canvas_prompt(req: GenerateRequest, product_type: str | None) -> str:
    """긴 배경 이미지 하나의 프롬프트를 만든다.

    모듈 이미지와 같은 톤 문구(_resolve_tone)를 쓴다. 배경과 그 위에 얹히는
    이미지들이 같은 아트 디렉션을 받아야 한 페이지로 읽힌다.
    """
    return _CANVAS_PROMPT.format(
        product_name=req.product_name or "화장품",
        product_type_line=f" ({product_type})" if product_type else "",
        tone=_resolve_tone(req, product_type),
        hint=_texture_hint(product_type),
    )


def generate_canvas_background(
    req: GenerateRequest, product_type: str | None, generator
) -> tuple[CanvasBackground | None, bytes | None]:
    """긴 배경 이미지 1장을 만든다(레이어 구조 1단계).

    **모듈 이미지를 대신하지 않는다.** 배경 1장 위에 모듈 이미지·표·문구가 얹히는
    구조라 둘 다 필요하다(팀장 확정, 2026-08-20). 그래서 이미지가 한 장 늘고 과금도
    는다 — 조용히 비용을 올리지 않게 `req.image_generation.canvas_requested`로
    옵트인을 받는다.

    실제 배치(어느 모듈이 배경의 몇 % 지점에 앉는지)는 **2단계**에서 정한다. 프론트
    렌더 구조가 바뀌는 일이라 디자이너·프론트와 같이 잡아야 한다. 여기서는 배경만
    만들어 두고, 배치 정보를 실을 자리는 `CanvasBackground.placements`로 비워 둔다.

    과금 호출이라 실패해도 재시도하지 않고 사유만 남긴다(나머지 생성은 계속되게).
    """
    if generator is None:
        return None, None
    prompt = build_canvas_prompt(req, product_type)
    allowed, deny_reason = check_impersonation(
        f"{req.product_name or ''} {req.color_tone or ''} {req.mood or ''}"
    )
    if not allowed:
        return CanvasBackground(status="skipped", reason=deny_reason), None
    try:
        blob = generator.generate_image(prompt, [])
    except Exception as e:
        reason = f"긴 배경 이미지 생성 실패: {type(e).__name__}"
        print(f"    [skip] {reason}: {e}")
        return CanvasBackground(status="skipped", reason=reason), None
    return CanvasBackground(status="generated"), blob


# 사업자가 직접 낸 자료를 담는 모듈. 자유생성 카피에 밀려 이미지를 못 받으면 안 된다.
_SELLER_DATA_PREFIXES = ("clinical",)
_SELLER_DATA_KINDS = frozenset({"survey_result"})


def _budget_tier(index: int, module: LayoutModule) -> int:
    """이미지 상한을 나눠줄 우선순위. 낮을수록 먼저 받는다.

    0) 첫 모듈(히어로). 맨 위에서 제일 크게 보이는 자리라 여기가 비면 제일 티가 난다.
    1) 사업자가 낸 자료(실증자료·설문). 우리가 지어낸 게 아니라 사업자가 넣은 값이라
       이게 빈칸이면 "자료를 넣었는데 안 실렸다"가 된다.
    2) 나머지 자유생성 카피.
    """
    if index == 0:
        return 0
    if module.kind.startswith(_SELLER_DATA_PREFIXES) or module.kind in _SELLER_DATA_KINDS:
        return 1
    return 2


def _budget_order(modules: list[LayoutModule]) -> list[int]:
    """상한을 나눠줄 순서(계획 인덱스). 이 순서대로 돌면서 상한까지 만든다.

    **왜 계획 순서로 그냥 자르면 안 되나**: 예전엔 계획 순서대로 돌다 6장을 채우면
    끝냈다. 자유생성 카피가 앞에 몰리면 사업자가 낸 실증자료 카드가 이미지를 못 받고
    글만 남았다. 같은 입력을 세 번 돌렸더니 임상 카드가 각각 2장·1장·0장씩 이미지를
    받았다(2026-08-24 실측). 실행마다 달라져서 리허설에선 안 보이다가 시연에서 터진다.

    카드 상한(`layout.py`)에서 이미 세운 원칙과 같다 - 사업자 자료가 자유생성 카피에
    밀리지 않는다. **상한 자체는 그대로다. 누가 먼저 가져가는지만 바꾼다.**

    그림 그리는 순서만 바뀌고 프롬프트 내용은 안 바뀐다. `build_image_prompt`가 계획
    위치를 안 쓰기 때문이다(쓰는 건 `variation_index`뿐인데, 그건 같은 layout_type이
    몇 번째로 **생성**됐는지라 원래도 계획 위치와 별개다).
    """
    # 티어가 같으면 계획 순서를 지킨다(sorted는 안정 정렬).
    return sorted(range(len(modules)), key=lambda i: _budget_tier(i, modules[i]))


def generate_module_images(
    plan: LayoutPlan,
    req: GenerateRequest,
    generator,
    max_images: int = DEFAULT_MAX_IMAGES,
    photo_resolver=None,
    copy_by_kind: dict[str, str] | None = None,
) -> tuple[list[ModuleImage], dict[str, bytes]]:
    """계획된 모듈마다 이미지를 만든다.

    반환: (모듈별 결과 메타, {모듈kind: PNG바이트}). 바이트 저장은 호출자가 정한다.
    generator가 None이면 아무것도 만들지 않는다(생성기 미도입 상태에서도 응답은 나가게).

    photo_resolver: `(req) -> PNG/JPEG 바이트 목록`. 있으면 모든 모듈에 같은 참조
    이미지로 넘긴다(합성, 팀장 승인 방식 A). 배경마다 다른 사진을 쓰는 기능은 아직
    없다. 조회는 한 번만 한다(모듈마다 다시 부르면 저장소를 반복 왕복한다).

    **`req.product_photo_ids`만 보지 않는다.** create 모드는 그 필드로 참조를
    찾지만, improve 모드는 원본 검사에 첨부된 리포트 이미지(`req.result_id`)가
    참조다 - 저장 위치가 서로 달라 photo_resolver가 req를 통째로 받아 내부에서
    가른다(`api/app.py` `_resolve_reference_photos`, 2026-08-24). 이 함수는
    photo_resolver가 있기만 하면 그냥 부르고, 참조가 없다는 판단은 콜백에 맡긴다.

    **실제 API 호출(`generator.generate_image`)은 우선순위 묶음(파도) 단위로
    병렬로 나간다**(2026-08-24, PM 지시 - 장당 ~13초 순차 호출이 6장이면 80초대
    였다). 프롬프트 조립·사칭가드·상한 판정은 순차로 하고(빠르고 상태 의존적),
    실제 네트워크 호출만 `ThreadPoolExecutor`로 동시에 보낸다. 상한(`max_images`)은
    "성공한 개수" 기준 그대로다 - 한 파도에서 일부가 실패하면 다음 파도가 그
    빈자리를 우선순위 다음 모듈로 채운다(순차 버전과 같은 성질). `vlm.py`의
    `GeminiVLM._throttle`/`_record_usage`가 락 없이 공유 상태를 건드려서 동시
    호출이면 경합했는데, 그쪽에 락을 걸어 해결했다(같은 커밋).
    """
    results: list[ModuleImage] = []
    blobs: dict[str, bytes] = {}
    if generator is None:
        # **조용히 빈 목록을 내지 않는다.** 사용자는 이미지를 요청했는데 결과에
        # 아무 흔적이 없으면 "왜 안 나왔는지"를 알 방법이 없다(2026-08-23: 실제로
        # module_images=[] · reason=null 로 나가서 원인 추적에 시간을 썼다).
        for module in plan.modules:
            results.append(
                ModuleImage(
                    module_kind=module.kind,
                    status="skipped",
                    reason="이미지 생성이 꺼져 있습니다(IMAGE_GENERATION_ENABLED).",
                )
            )
        return results, blobs

    reference_images: list[bytes] = []
    if photo_resolver is not None:
        try:
            reference_images = photo_resolver(req)
        except Exception as e:
            # 예상된 실패(사진 조회 실패)라 참조 없이 계속 진행한다(배경만 생성).
            print(f"    [skip] 제품사진 조회 실패(참조 없이 진행): {type(e).__name__}: {e}")

    # 이미지 배정 대상만 추린다. 사진 배경이 필요없는 유형은 상한을 소모하지 않고
    # 즉시 skip이라 파도 계산에서 아예 뺀다(원래 셀 자격이 없던 이미지).
    eligible: list[int] = []
    for module_index in _budget_order(plan.modules):
        module = plan.modules[module_index]
        if module.layout_type in _NO_IMAGE_LAYOUT_TYPES:
            results.append(
                ModuleImage(
                    module_kind=module.kind,
                    status="skipped",
                    reason=f"{module.layout_type}은 사진 배경이 필요없는 유형이라 이미지를 만들지 않습니다",
                )
            )
            continue
        eligible.append(module_index)

    # layout_type별 등장 횟수. 같은 유형이 반복될 때 프롬프트를 갈라주는 데 쓴다.
    # **병렬화 이후엔 "시도한" 순서로 센다(성공 여부와 무관).** 순차 버전은 실제
    # 성공한 것만 셌지만, 병렬 호출은 어느 게 먼저 성공하는지가 실행마다 흔들려서
    # 그 성질을 그대로 재현할 수 없다 - 결과가 갈리는 건 이 변주 문구 한 줄뿐이고
    # (짝짓기·성패에는 영향 없음), 실사용엔 지장이 없다고 판단했다.
    seen_layout_types: dict[str, int] = {}

    def _run(job: tuple[LayoutModule, str]) -> tuple[LayoutModule, bytes | None, Exception | None]:
        module, prompt = job
        try:
            return module, generator.generate_image(prompt, reference_images), None
        except Exception as e:
            return module, None, e

    made = 0
    cursor = 0
    # 우선순위 순서대로, 성공 개수가 상한(max_images)을 채우거나 후보가 떨어질
    # 때까지 파도 단위로 돈다. **상한은 "성공한 개수" 기준**(순차 버전과 동일) -
    # 실패·사칭가드 거부는 안 세므로 다음 파도가 우선순위상 다음 모듈로 그 자리를
    # 채운다. 한 파도 안의 실제 API 호출만 동시에 보낸다.
    while made < max_images and cursor < len(eligible):
        wave = eligible[cursor : cursor + (max_images - made)]
        cursor += len(wave)

        # 프롬프트 조립·사칭가드는 상태(seen_layout_types)를 쓰고 빠르므로 순차로.
        jobs: list[tuple[LayoutModule, str]] = []
        for module_index in wave:
            module = plan.modules[module_index]
            variation_index = seen_layout_types.get(module.layout_type, 0)
            seen_layout_types[module.layout_type] = variation_index + 1
            prompt = build_image_prompt(
                module,
                req,
                plan.product_type,
                has_product_photo=bool(reference_images),
                variation_index=variation_index,
                copy_text=(copy_by_kind or {}).get(module.kind),
            )
            allowed, deny_reason = check_impersonation(_user_controlled_text(module, req))
            if not allowed:
                results.append(
                    ModuleImage(module_kind=module.kind, status="skipped", reason=deny_reason)
                )
                continue
            jobs.append((module, prompt))

        if not jobs:
            continue

        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            outcomes = list(pool.map(_run, jobs))

        for module, blob, err in outcomes:
            if err is not None:
                # 과금 호출이라 재시도하지 않는다. 이 모듈만 스킵하고 나머지는 계속.
                reason = f"이미지 생성 실패: {type(err).__name__}"
                print(f"    [skip] 이미지 생성 실패({module.kind}): {type(err).__name__}: {err}")
                results.append(ModuleImage(module_kind=module.kind, status="skipped", reason=reason))
                continue
            blobs[module.kind] = blob
            results.append(ModuleImage(module_kind=module.kind, status="generated"))
            made += 1

    if cursor < len(eligible):
        # 상한으로 잘린 것도 기록한다. 조용히 자르면 "다 만들었다"로 오해된다.
        for module_index in eligible[cursor:]:
            module = plan.modules[module_index]
            results.append(
                ModuleImage(
                    module_kind=module.kind,
                    status="skipped",
                    reason=f"이미지 생성 상한({max_images}장)을 넘어 건너뛰었습니다",
                )
            )

    # 결과는 계획 순서로 되돌린다. 카드 짝짓기는 kind로 하니 순서와 무관하지만,
    # 로그와 응답을 사람이 읽을 때 화면에 뜨는 순서와 같아야 헷갈리지 않는다.
    position = {m.kind: i for i, m in enumerate(plan.modules)}
    results.sort(key=lambda r: position.get(r.module_kind, len(position)))
    return results, blobs
