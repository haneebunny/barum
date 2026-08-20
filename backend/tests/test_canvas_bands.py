"""긴 배경 안전지대 밴드 찾기 유닛테스트.

실제 생성 이미지 대신 합성 이미지를 쓴다(외부 의존 없이, 결과가 결정적이게).
"""

import io

import numpy as np
import pytest
from PIL import Image

from barum.generate.canvas_bands import DEFAULT_MIN_BAND_RATIO, find_safe_bands


def _png(rows: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rows.astype(np.uint8), mode="L").save(buf, format="PNG")
    return buf.getvalue()


def _canvas(busy_bands: list[tuple[int, int]], height: int = 1000, width: int = 300) -> bytes:
    """평평한 배경에 지정 구간만 시끄럽게(가로로 값이 튀게) 만든 세로 이미지."""
    rng = np.random.default_rng(0)
    arr = np.full((height, width), 200.0)
    # 완전 단색이면 실제 사진과 다르다. 전체에 옅은 노이즈를 깔아 사진에 가깝게 만든다.
    arr += rng.normal(0, 2.0, size=arr.shape)
    for a, b in busy_bands:
        arr[a:b] += rng.normal(0, 60.0, size=(b - a, width))
    return _png(np.clip(arr, 0, 255))


def test_시끄러운_구간을_피해_밴드를_찾는다():
    blob = _canvas([(300, 500), (700, 900)])
    bands = find_safe_bands(blob)
    assert bands, "안전지대를 하나도 못 찾았다"
    for band in bands:
        # 시끄러운 구간(30~50%, 70~90%)과 겹치면 안 된다.
        assert not (band.y_start_pct < 0.50 and band.y_end_pct > 0.30)
        assert not (band.y_start_pct < 0.90 and band.y_end_pct > 0.70)


def test_밴드는_위에서_아래_순서로_나온다():
    bands = find_safe_bands(_canvas([(300, 500), (700, 900)]))
    starts = [b.y_start_pct for b in bands]
    assert starts == sorted(starts)


def test_비율로_낸다():
    """픽셀이 아니라 비율이라야 배경 크기가 달라져도 배치가 안 깨진다."""
    for height in (600, 2400):
        bands = find_safe_bands(_canvas([(int(height * 0.3), int(height * 0.5))], height=height))
        assert bands
        for band in bands:
            assert 0.0 <= band.y_start_pct <= 1.0
            assert 0.0 <= band.y_end_pct <= 1.0
            assert band.y_start_pct < band.y_end_pct


def test_너무_얇은_구간은_밴드로_안_친다():
    """문구를 못 얹을 만큼 얇으면 배치 후보가 아니다."""
    height = 1000
    thin = int(height * DEFAULT_MIN_BAND_RATIO / 2)
    # 얇은 조용 구간 하나만 남기고 나머지를 전부 시끄럽게 만든다.
    blob = _canvas([(0, 400), (400 + thin, height)], height=height)
    bands = find_safe_bands(blob)
    assert all(b.height_pct >= DEFAULT_MIN_BAND_RATIO - 0.001 for b in bands)


def test_전체가_노이즈여도_상대적으로_조용한_구간을_찾는다():
    """사진 배경은 최저 점수가 0이 아니다(실측 5.3). 절대 임계값이면 밴드가 0개가 된다."""
    rng = np.random.default_rng(1)
    height, width = 1000, 300
    arr = np.full((height, width), 180.0) + rng.normal(0, 12.0, size=(height, width))
    arr[400:600] += rng.normal(0, 50.0, size=(200, width))  # 상대적으로 더 시끄러운 구간
    bands = find_safe_bands(_png(np.clip(arr, 0, 255)))
    assert bands, "전 구간에 노이즈가 있으면 절대 임계값으로는 못 찾는다. 백분위라야 한다"


def test_깨진_이미지는_빈_목록을_낸다():
    """배치를 못 해도 배경 생성 전체를 실패시키지 않는다(프론트가 기존 렌더로 폴백)."""
    assert find_safe_bands(b"not an image") == []


def test_경계를_올리면_밴드가_더_넓어진다():
    """quiet_level을 올리면 더 관대해져 커버 면적이 줄지 않아야 한다."""
    blob = _canvas([(300, 500)])
    tight = sum(b.height_pct for b in find_safe_bands(blob, quiet_level=0.1))
    loose = sum(b.height_pct for b in find_safe_bands(blob, quiet_level=0.5))
    assert loose >= tight > 0


def test_이봉형_분포에서_조용한_구간이_안_쪼개진다():
    """단순 백분위를 쓰면 임계값이 조용한 덩어리 한가운데 떨어져 잘게 갈린다.
    실측: 조용한 행 300개가 69조각(최장 23행)으로 갈렸다. 범위 기반이라야 통째로 잡는다."""
    blob = _canvas([(300, 500), (700, 900)])
    bands = find_safe_bands(blob)
    # 0~30% 구간이 통째로 하나의 밴드여야 한다(쪼개지면 40행짜리도 안 나온다).
    top = [b for b in bands if b.y_start_pct < 0.05]
    assert top, "맨 위 조용한 구간을 못 찾았다"
    assert top[0].height_pct > 0.2, f"조용한 구간이 쪼개졌다: {top[0].height_pct:.2f}"


# ── 모듈 배치 (디디 §4: 겹침 대상은 hero_fullbleed·mood_macro 둘뿐) ──


from barum.generate.canvas_bands import SafeBand, assign_placements  # noqa: E402
from barum.models import LayoutModule  # noqa: E402


def _mod(kind: str, layout_type: str) -> LayoutModule:
    return LayoutModule(kind=kind, purpose="p", layout_type=layout_type)


def _bands(*pairs) -> list[SafeBand]:
    return [SafeBand(a, b, 10.0) for a, b in pairs]


def test_겹침_대상만_밴드를_소비한다():
    """평면·분리형 모듈은 사진 위에 문구를 안 얹으므로 밴드를 다투지 않는다."""
    modules = [
        _mod("hero_intro", "hero_fullbleed"),
        _mod("cause_explain", "section_statement"),
        _mod("texture", "mood_macro"),
        _mod("spec", "table_info"),
    ]
    out = assign_placements(modules, _bands((0.26, 0.40), (0.67, 0.75)))
    by_kind = {p.module_kind: p for p in out}
    assert by_kind["hero_intro"].background_mode == "image_scrim"
    assert by_kind["texture"].background_mode == "image_scrim"
    assert by_kind["cause_explain"].background_mode == "solid_plate"
    assert by_kind["spec"].background_mode == "solid_plate"


def test_히어로가_가장_위_밴드를_가져간다():
    """hero_fullbleed는 항상 페이지 최상단이다."""
    modules = [_mod("texture", "mood_macro"), _mod("hero_intro", "hero_fullbleed")]
    out = {p.module_kind: p for p in assign_placements(modules, _bands((0.26, 0.40), (0.67, 0.75)))}
    assert out["hero_intro"].y_start_pct == 0.26
    assert out["texture"].y_start_pct == 0.67


def test_밴드가_모자라면_스킵으로_기록한다():
    """조용히 빠지지 않게 사유를 남긴다(CLAUDE.md §E)."""
    modules = [_mod("hero_intro", "hero_fullbleed"), _mod("texture", "mood_macro")]
    out = {p.module_kind: p for p in assign_placements(modules, _bands((0.26, 0.40)))}
    assert out["hero_intro"].status == "placed"
    assert out["texture"].status == "skipped"
    assert "안전지대" in out["texture"].reason


def test_평면_모듈은_겹침_대상_구간을_피한다():
    modules = [_mod("hero_intro", "hero_fullbleed")] + [
        _mod(f"m{i}", "section_statement") for i in range(3)
    ]
    out = assign_placements(modules, _bands((0.0, 0.20)))
    hero = next(p for p in out if p.module_kind == "hero_intro")
    for p in out:
        if p.module_kind == "hero_intro":
            continue
        assert not (p.y_start_pct < hero.y_end_pct and p.y_end_pct > hero.y_start_pct)


def test_계획_순서를_유지한다():
    """프론트가 순서대로 렌더할 수 있어야 한다."""
    modules = [_mod("a", "section_statement"), _mod("b", "hero_fullbleed"), _mod("c", "table_info")]
    out = assign_placements(modules, _bands((0.0, 0.2)))
    assert [p.module_kind for p in out] == ["a", "b", "c"]


def test_밴드가_아예_없어도_평면_모듈은_배치된다():
    """배경 분석이 실패해도 평면 모듈은 원래 밴드가 필요 없다."""
    modules = [_mod("a", "section_statement"), _mod("b", "table_info")]
    out = assign_placements(modules, [])
    assert all(p.status == "placed" for p in out)
    assert all(p.background_mode == "solid_plate" for p in out)


def test_평면_모듈끼리도_안_겹친다():
    """겹침 대상만 피하고 각자 독립적으로 밀면 평면 모듈끼리 같은 자리에 앉는다.
    실측: cause_explain 39.9~59.9%와 ingredient_highlight 40.0~60.0%가 겹쳤다."""
    modules = [_mod("hero", "hero_fullbleed")] + [
        _mod(f"m{i}", "section_statement") for i in range(6)
    ]
    out = [p for p in assign_placements(modules, _bands((0.26, 0.40))) if p.status == "placed"]
    spans = sorted((p.y_start_pct, p.y_end_pct, p.module_kind) for p in out)
    for a, b in zip(spans, spans[1:]):
        assert a[1] <= b[0] + 1e-9, f"{a[2]}와 {b[2]}가 겹친다: {a[:2]} / {b[:2]}"


def test_슬롯이_겹침_대상_구간을_삼키지_않는다():
    """빈 구간 경계를 가로지르는 슬롯을 허용하면 그 사이 히어로 자리를 덮는다.
    실측: cause_explain이 15.6~44.8%를 받아 히어로의 26.2~39.9%를 덮었다."""
    modules = [_mod("hero", "hero_fullbleed"), _mod("a", "section_statement"), _mod("b", "table_info")]
    out = {p.module_kind: p for p in assign_placements(modules, _bands((0.26, 0.40)))}
    hero = out["hero"]
    for kind in ("a", "b"):
        p = out[kind]
        assert not (p.y_start_pct < hero.y_end_pct and p.y_end_pct > hero.y_start_pct)


def test_세로를_빠짐없이_덮는다():
    """구간이 비면 배경이 그대로 드러난다. 남은 공간을 다 나눠 가져야 한다."""
    modules = [_mod(f"m{i}", "section_statement") for i in range(4)]
    out = assign_placements(modules, [])
    covered = sum(p.y_end_pct - p.y_start_pct for p in out)
    assert abs(covered - 1.0) < 0.01, f"커버리지 {covered:.3f}"
