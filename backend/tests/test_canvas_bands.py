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
