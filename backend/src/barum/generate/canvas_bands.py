"""긴 배경 이미지에서 콘텐츠를 얹어도 되는 '안전지대' 밴드를 찾는다 (레이어 구조 2단계).

배치 좌표를 백엔드가 내려주는 이유: 오버레이를 **앉히는 것**은 프론트가 할 수 있지만
**어디에 앉힐지**는 이미지 안에 뭐가 그려졌는지 아는 쪽만 판단할 수 있다. 프론트는
image_url만 받는다(냐냐 판단, 2026-08-20).

프롬프트로 "이 구간은 비워라"를 지시하는 것에만 기대지 않는다. 모델이 안 지킬 수 있어서
**생성된 이미지를 실제로 분석**한다.

점수 함수는 `tile_split.find_quiet_rows()`를 그대로 쓴다(행별 회색조 표준편차 + 스무딩).
실측으로 긴 배경에서도 유효한 걸 확인했다(2026-08-20, 544x1952 실제 생성물):
구간별 점수가 이미지 내용과 일치했고, 뽑힌 밴드를 잘라 보니 평평한 석재 상판·벽면이었다.

**함정 두 개. 다음 사람이 여기서 같은 실수를 한다.**

1. **임계값을 절대값으로 잡으면 안 된다.** `tile_split`의 원래 용도는 흰 바탕에 글자가
   찍힌 상세페이지라 여백 점수가 0에 가깝다. 그런데 AI가 만든 사진 배경은 어디에도
   완전한 단색이 없어서 **최저 점수가 5.3, 평균 25.1**이었다. 절대 임계값을 쓰면
   "조용한 줄이 하나도 없다"는 답이 나온다.

   **그렇다고 단순 백분위도 안 된다.** 처음엔 30퍼센타일로 잡았는데, 점수 분포가
   이봉형(아주 평평한 구간 + 아주 복잡한 구간)이면 임계값이 **조용한 덩어리 한가운데**에
   떨어져 그 구간을 잘게 쪼갠다. 실측: 조용한 행 300개가 69조각으로 갈려 최장 23행이
   됐다(밴드 최소 40행 필요). 실제 생성 이미지는 분포가 넓게 퍼져 우연히 통했을 뿐이다.

   그래서 **범위 기반**으로 잡는다: `p5 + (p95 - p5) * 0.2`. 양 끝을 백분위로 잡아
   이상치(한 줄짜리 아주 복잡한 행)에 안 흔들리게 하고, 그 범위의 아래쪽 20% 지점을
   경계로 쓴다. 이봉형·연속형 둘 다에서 조용한 덩어리를 통째로 잡는다.

2. **`split_image()`는 재사용 못 한다.** 절단선 선택 로직이 "target_h마다 자른다" 같은
   상세페이지 전제로 박혀 있다. 점수 함수(`find_quiet_rows`)만 가져다 쓰고 밴드 선택은
   여기서 새로 한다.

**"밴드 2개 vs 모듈 8~11개"는 해소됐다(디디 §4).** 배경을 늘리거나 전면 스크림을 까는
게 아니라 **대상 스코프를 좁혀서** 푼다. 어휘집 12종 중 사진 위에 문구를 직접 겹치는
건 `hero_fullbleed`(페이지당 1회)와 `mood_macro`(보통 1회) **둘뿐**이고, 나머지 10종은
완전 평면이거나 이미지·텍스트 분리형이라 애초에 겹칠 일이 없다. 실제로 밴드를 다투는
건 1~2개라 2개로 충분하다.
"""

from dataclasses import dataclass

# 조용/복잡 경계를 점수 범위의 어디에 둘지(0.0=가장 조용한 값, 1.0=가장 복잡한 값).
# 0.2는 실측으로 고른 값이다: 합성 이봉형 이미지와 실제 생성 배경 양쪽에서 시끄러운
# 구간을 정확히 피했다(2026-08-20).
DEFAULT_QUIET_LEVEL = 0.2

# 범위 양 끝을 잡을 백분위. 0/100(최소·최대)을 쓰면 한 줄짜리 이상치가 범위를 왜곡한다.
_RANGE_LO_PCT, _RANGE_HI_PCT = 5.0, 95.0

# 밴드로 인정할 최소 높이(전체 세로 대비 비율). 너무 얇은 구간은 문구를 못 얹는다.
DEFAULT_MIN_BAND_RATIO = 0.04


@dataclass(frozen=True)
class SafeBand:
    """콘텐츠를 얹어도 되는 세로 구간. 배경 세로 길이 대비 비율(0.0~1.0)로 낸다.

    픽셀이 아니라 비율인 이유: 배경 크기가 생성마다 달라진다(비율을 프롬프트로만
    지시하고 있어서). 절대 픽셀로 내리면 크기가 달라질 때마다 배치가 깨진다.
    """

    y_start_pct: float
    y_end_pct: float
    quiet_score: float  # 낮을수록 조용. 밴드끼리 우열을 가릴 때 쓴다.

    @property
    def height_pct(self) -> float:
        return self.y_end_pct - self.y_start_pct


def find_safe_bands(
    image_bytes: bytes,
    quiet_level: float = DEFAULT_QUIET_LEVEL,
    min_band_ratio: float = DEFAULT_MIN_BAND_RATIO,
) -> list[SafeBand]:
    """배경 이미지에서 안전지대 밴드를 찾아 위에서 아래 순서로 낸다.

    이미지를 못 읽으면 빈 목록을 낸다(예상된 실패로 본다 — 배치를 못 하면 프론트가
    기존 렌더로 폴백하면 되고, 배경 생성 전체를 실패시킬 이유는 없다).
    """
    import io

    import numpy as np
    from PIL import Image

    from tile_split import find_quiet_rows

    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("L")
    except Exception as e:
        print(f"    [skip] 배경 이미지 분석 실패(배치 없이 진행): {type(e).__name__}: {e}")
        return []

    gray = np.asarray(im, dtype=np.float32)
    height = gray.shape[0]
    if height == 0:
        return []

    score = find_quiet_rows(gray)
    lo = float(np.percentile(score, _RANGE_LO_PCT))
    hi = float(np.percentile(score, _RANGE_HI_PCT))
    threshold = lo + (hi - lo) * quiet_level
    min_rows = max(1, int(height * min_band_ratio))

    bands: list[SafeBand] = []
    start: int | None = None
    for y in range(height):
        quiet = score[y] < threshold
        if quiet and start is None:
            start = y
        elif not quiet and start is not None:
            if y - start >= min_rows:
                bands.append(_band(start, y, height, score))
            start = None
    if start is not None and height - start >= min_rows:
        bands.append(_band(start, height, height, score))
    return bands


def _band(start: int, end: int, height: int, score) -> SafeBand:
    """픽셀 구간을 비율 밴드로 바꾼다."""
    return SafeBand(
        y_start_pct=round(start / height, 4),
        y_end_pct=round(end / height, 4),
        quiet_score=round(float(score[start:end].mean()), 2),
    )


# 사진 위에 문구를 직접 겹치는 layout_type. 이 둘만 안전지대(밴드)를 다툰다.
#
# 디디 §4(`design/mockups/long-canvas-placement-rules.md`) 판단이다. 어휘집 12종 중
# 나머지 10종은 겹칠 필요가 없다:
# - 완전 평면(사진 없음): section_statement·clinical_bar_compare·icon_grid·step_list·
#   table_info·banner_strip
# - 이미지·텍스트 분리형(문구가 이미지 위가 아니라 자기 패널에): image_text_split·
#   clinical_photo_compare·card_list_repeat·lineup_strip
#
# 그래서 "밴드 2개 vs 모듈 8~11개" 불일치는 배경을 늘리거나 전면 스크림을 까는 게 아니라
# **대상 스코프를 좁혀서** 해소된다.
_OVERLAY_LAYOUT_TYPES = ("hero_fullbleed", "mood_macro")

# 겹침 대상이 밴드를 못 받았을 때 쓰는 바탕. 스크림이 1순위, 플레이트가 2순위다(디디 §2).
_MODE_SCRIM = "image_scrim"
_MODE_PLATE = "solid_plate"


def assign_placements(modules, bands: list[SafeBand]) -> list["ModulePlacement"]:
    """모듈들을 배경 위 좌표에 배치한다.

    **겹침 대상(hero_fullbleed·mood_macro)만 밴드를 소비한다.** 나머지는 애초에 사진 위에
    문구를 얹지 않으므로 `solid_plate`로 자기 자리를 갖는다(폴백이 아니라 기본값).

    `hero_fullbleed`는 항상 페이지 최상단이라 첫 밴드를 먼저 가져간다. 그 다음
    `mood_macro`가 남은 밴드를 받는다. 밴드가 모자라면 스크림으로 떨어지고, 그것도
    안 되는 경우는 지금 없다(스크림은 어떤 배경에서도 대비를 보장한다).

    평면 모듈의 구간은 겹침 대상이 쓰지 않는 나머지 세로를 순서대로 나눠 갖는다.
    """
    from barum.models import ModulePlacement

    overlay = [m for m in modules if m.layout_type in _OVERLAY_LAYOUT_TYPES]
    flat = [m for m in modules if m.layout_type not in _OVERLAY_LAYOUT_TYPES]

    placements: dict[str, ModulePlacement] = {}
    remaining = list(bands)

    # 히어로 먼저. 최상단 고정이라 가장 위 밴드를 준다.
    for module in sorted(overlay, key=lambda m: m.layout_type != "hero_fullbleed"):
        band = remaining.pop(0) if remaining else None
        if band is not None:
            placements[module.kind] = ModulePlacement(
                module_kind=module.kind,
                y_start_pct=band.y_start_pct,
                y_end_pct=band.y_end_pct,
                background_mode=_MODE_SCRIM,
            )
        else:
            # 밴드가 없어도 스크림이면 대비가 보장된다. 위치는 균등 분배로 잡는다.
            placements[module.kind] = ModulePlacement(
                module_kind=module.kind,
                y_start_pct=0.0,
                y_end_pct=0.0,
                background_mode=_MODE_SCRIM,
                status="skipped",
                reason="안전지대(quiet zone)가 부족해 좌표를 확정하지 못했습니다",
            )

    # 평면 모듈은 겹침 대상이 쓰고 남은 세로를 순서대로 나눈다.
    # **앞서 배치된 평면 모듈끼리도 안 겹쳐야 한다.** 겹침 대상만 피하고 각자 독립적으로
    # 밀면 평면 모듈끼리 같은 자리에 앉는다(2026-08-20 실측: cause_explain 39.9~59.9%와
    # ingredient_highlight 40.0~60.0%가 겹쳤다). 남은 구간을 통째로 계산해서 나눈다.
    used = sorted(
        (p.y_start_pct, p.y_end_pct) for p in placements.values() if p.status == "placed"
    )
    for module, (start, end) in zip(flat, _split_free_space(used, len(flat))):
        placements[module.kind] = ModulePlacement(
            module_kind=module.kind,
            y_start_pct=start,
            y_end_pct=end,
            background_mode=_MODE_PLATE,
        )

    # 계획 순서를 유지해서 낸다(프론트가 순서대로 렌더할 수 있게).
    return [placements[m.kind] for m in modules if m.kind in placements]


def _free_intervals(used: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """겹침 대상이 쓰고 남은 세로 구간들(위에서 아래 순)."""
    free: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in used:
        if start > cursor:
            free.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < 1.0:
        free.append((cursor, 1.0))
    return free


def _split_free_space(used: list[tuple[float, float]], count: int) -> list[tuple[float, float]]:
    """남은 구간 전체를 count개로 순서대로 쪼갠다. 서로 안 겹친다.

    **각 모듈은 하나의 빈 구간 안에만 들어간다.** 슬롯이 빈 구간 경계를 가로지르게 두면
    그 사이에 있는 겹침 대상 구간을 통째로 삼킨다(2026-08-20 실측: cause_explain이
    15.6~44.8%를 받아 히어로의 26.2~39.9%를 덮었다).

    빈 구간이 여러 조각이면 길이에 비례해 모듈 수를 나눠 준 뒤, 각 조각을 그 안에서
    균등 분할한다. 나머지는 큰 조각부터 하나씩 더 준다(최대잔여법).
    """
    if count <= 0:
        return []
    free = _free_intervals(used)
    total = sum(end - start for start, end in free)
    if not free or total <= 0:  # 겹침 대상이 세로 전체를 덮은 극단적 경우
        return [(0.0, 0.0)] * count

    # 길이 비례 배분 + 최대잔여법으로 정확히 count개를 맞춘다.
    exact = [(end - start) / total * count for start, end in free]
    quota = [int(x) for x in exact]
    remainder = count - sum(quota)
    for i in sorted(range(len(free)), key=lambda i: exact[i] - quota[i], reverse=True)[:remainder]:
        quota[i] += 1

    out: list[tuple[float, float]] = []
    for (start, end), n in zip(free, quota):
        if n <= 0:
            continue
        step = (end - start) / n
        for k in range(n):
            out.append((round(start + step * k, 4), round(start + step * (k + 1), 4)))
    return out
