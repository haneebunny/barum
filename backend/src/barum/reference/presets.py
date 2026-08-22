"""콘텐츠 생성 프리셋 로더.

프리셋 하나가 **타겟팅 + 레이아웃 방향 + 색/무드 + 폰트단**을 한 세트로 묶는다.
요청에 프리셋 id만 오면 그 값들이 텍스트 생성 프롬프트와 이미지 생성 프롬프트
**양쪽에** 들어간다(팀장 확정, 2026-08-22).

**폰트는 백엔드 개념이 아니다.** 실제 폰트는 프론트 CSS에 있고(Pretendard·SUIT),
백엔드가 프롬프트에 폰트 이름을 넣어봐야 이미지 생성에만 닿는다. 그래서 여기선
`font_tier` id만 실어 보내고 해석은 프론트가 한다.

**color_tone·mood는 원래 있던 필드다**(인터뷰에서 직접 받던 값). 프리셋은 그걸
묶어 이름을 붙이는 것이고, 진짜 신규는 targeting·layout_direction이다. 그래서
요청에 명시값이 있으면 프리셋보다 그쪽이 이긴다(인터뷰 경로를 안 깨뜨린다).
"""

import json
from functools import lru_cache
from pathlib import Path

_PRESET_FILE = Path(__file__).resolve().parent / "data" / "content_presets.json"


@lru_cache(maxsize=1)
def load_presets() -> dict[str, dict]:
    """프리셋 id → 프리셋 dict. 파일이 깨졌으면 즉시 터뜨린다(예상 못 한 실패)."""
    raw = json.loads(_PRESET_FILE.read_text(encoding="utf-8"))
    return {p["id"]: p for p in raw["presets"]}


def get_preset(preset_id: str | None) -> dict | None:
    """id로 프리셋 하나. 없는 id면 None(요청을 막지 않는다).

    없는 id를 400으로 막지 않는 이유: 프리셋은 표현 힌트라 없으면 기존 경로 그대로
    생성하면 된다. 여기서 막으면 프리셋 목록이 바뀔 때마다 생성이 통째로 실패한다.
    호출부가 로그로 남긴다.
    """
    if not preset_id:
        return None
    return load_presets().get(preset_id)


def preset_ids() -> list[str]:
    """정의된 프리셋 id 목록(순서 유지). API 목록 응답·검증용."""
    return list(load_presets().keys())


def apply_preset(req):
    """프리셋 값을 채운 요청 사본과 프리셋 dict를 낸다. 프리셋이 없으면 원본 그대로.

    **명시값이 프리셋을 이긴다.** color_tone·mood는 원래 인터뷰에서 직접 받던 값이라,
    프리셋이 덮어쓰면 기존 경로가 조용히 무력화된다.

    모르는 id는 막지 않고 로그만 남긴다. 프리셋은 표현 힌트라 없으면 기존 경로로
    생성하면 되고, 여기서 400을 내면 프리셋 목록이 바뀔 때마다 생성이 통째로 실패한다.
    """
    preset = get_preset(req.preset)
    if preset is None:
        if req.preset:
            print(f"[preset] 모르는 프리셋 id라 무시하고 진행한다: {req.preset!r}")
        return req, None

    update = {
        field: preset[field]
        for field in ("targeting", "layout_direction", "color_tone", "mood")
        if not getattr(req, field, None) and preset.get(field)
    }
    return (req.model_copy(update=update) if update else req), preset


def audience_hint(req) -> str:
    """**텍스트 생성용** 타겟 힌트. 타겟팅만 넣는다. 없으면 빈 문자열.

    **레이아웃 방향은 일부러 뺀다**(2026-08-22 실측). 처음엔 타겟팅과 함께 넣었더니
    레이아웃 지시가 고객이 읽는 카피로 새어나왔다. quiet_luxury 프리셋
    ("어두운 바탕에 제품 하나만 놓고 조명을 낮게")으로 실제 생성한 결과:

        "이미지: 드롭퍼 디테일, 텍스처 클로즈업... 설명: ..."
        "아이콘 그리드: 무향료·무색소... 설명: ..."
        "미세한 광택을 어둠 속 조명 아래 정교하게 포착했습니다"

    레이아웃 방향은 **이미지 프롬프트에만** 간다(`images._resolve_tone`). 글은 누구에게
    말하는지만 알면 되고, 어떻게 배치되는지는 알 필요가 없다.
    """
    targeting = getattr(req, "targeting", None)
    return f"타겟 독자: {targeting}" if targeting else ""
