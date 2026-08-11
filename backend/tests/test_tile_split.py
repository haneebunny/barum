"""tile_split.split_image 밴드 반환 유닛테스트.

합성 이미지(단색)로 절단 동작을 결정론적으로 확인한다. VLM·실데이터 없음.

    ./venv/bin/python -m pytest tests/test_tile_split.py -q
"""

from PIL import Image

from tile_split import split_image


def test_short_image_returns_single_full_band(tmp_path):
    """안 긴 이미지는 1장 통과 — 밴드는 원본 전체(0~h)."""
    src = tmp_path / "source.png"
    Image.new("RGB", (1000, 1500), (255, 255, 255)).save(src)  # h < w*2, 안 김

    tiles = split_image(src, tmp_path / "tiles")

    assert len(tiles) == 1
    path, top, bot = tiles[0]
    assert path.exists()
    assert (top, bot) == (0, 1500)


def test_tall_image_returns_ordered_bands_covering_original(tmp_path):
    """세로로 긴 이미지는 여러 밴드로 쪼개지고, 밴드가 원본 세로를 덮는다."""
    src = tmp_path / "source.png"
    Image.new("RGB", (1000, 5000), (255, 255, 255)).save(src)  # 분할 조건 충족

    tiles = split_image(src, tmp_path / "tiles")

    assert len(tiles) >= 2
    for path, top, bot in tiles:
        assert path.exists()
        assert 0 <= top < bot <= 5000
    assert tiles[0][1] == 0  # 첫 밴드 상단 = 0
    assert tiles[-1][2] == 5000  # 마지막 밴드 하단 = 원본 높이
    tops = [top for _, top, _ in tiles]
    assert tops == sorted(tops)  # 밴드는 위→아래 순
