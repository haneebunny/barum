"""
상세페이지 통짜 이미지 → VLM 판독용 타일 분할
====================================================
왜 필요한가: 상세 마케팅 이미지는 세로 2~3만px짜리 통짜라, 그대로 축소하면
글자가 뭉개지고, 그냥 등분하면 문장 중간이 잘림.
→ "글자 없는 빈 줄(콘텐츠 경계)에서 자르는 스마트 분할" + 경계 겹침(overlap).

동작:
- 세로가 별로 안 긴 이미지(비율 <= max_ratio)는 그대로 1장 통과.
- 긴 이미지는 목표 높이(target_h)마다 자르되, 그 부근에서 '가장 조용한(글자 없는) 줄'을
  찾아 거기서 절단 → 문장 안 잘림. 인접 타일은 overlap만큼 겹쳐서 경계 글자 손실 방지.

사용:
  # 단일 이미지
  ./venv/bin/python tile_split.py 11st_output/details/3458162245/detail_001.jpg
  # 한 상품 폴더 전체
  ./venv/bin/python tile_split.py 11st_output/details/3458162245
  # details 트리 전체 (모든 상품)
  ./venv/bin/python tile_split.py 11st_output/details --recursive
  # 쿠팡 데이터도 동일하게
  ./venv/bin/python tile_split.py coupang_output/images --recursive

출력: 원본 옆 tiles/ 폴더에  {원본이름}_t00.png, _t01.png ...
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None      # 초대형 이미지 허용 (2~3만px)

IMG_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def find_quiet_rows(gray: np.ndarray) -> np.ndarray:
    """각 행의 '콘텐츠 양' 점수. 낮을수록 글자/그림 없는 조용한 줄."""
    # 행별 표준편차: 단색 배경/여백 ≈ 0, 글자·그림 있는 줄 ≈ 큼
    row_std = gray.std(axis=1)
    # 살짝 스무딩(경계 노이즈 완화)
    k = 5
    kernel = np.ones(k) / k
    return np.convolve(row_std, kernel, mode="same")


def split_image(path: Path, out_dir: Path,
                target_h: int = 1400, max_ratio: float = 2.0,
                overlap: int = 80, search: int = 240) -> list[Path]:
    """이미지 1장 → 타일 파일 리스트."""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem

    # 안 긴 이미지: 그대로 1장
    if h <= w * max_ratio or h <= target_h * 1.3:
        dst = out_dir / f"{stem}_t00.png"
        im.save(dst)
        return [dst]

    gray = np.asarray(im.convert("L"), dtype=np.float32)
    score = find_quiet_rows(gray)

    # 절단선 계산: target_h 간격 목표점 부근에서 가장 조용한 줄을 실제 절단선으로
    cuts = [0]
    y = target_h
    while y < h:
        lo = max(cuts[-1] + target_h // 2, y - search)   # 너무 얕게 자르지 않도록 하한
        hi = min(h, y + search)
        if lo >= hi:
            cut = min(y, h)
        else:
            cut = lo + int(np.argmin(score[lo:hi]))       # 창 안에서 가장 조용한 줄
        cuts.append(cut)
        y = cut + target_h
    cuts.append(h)
    cuts = sorted(set(cuts))

    # 타일 생성 (아래쪽에 overlap 덧대서 경계 글자 겹침)
    tiles = []
    for i in range(len(cuts) - 1):
        top = cuts[i]
        bot = min(h, cuts[i + 1] + overlap)
        if bot - top < 40:            # 너무 얇은 조각 스킵
            continue
        tile = im.crop((0, top, w, bot))
        dst = out_dir / f"{stem}_t{i:02d}.png"
        tile.save(dst)
        tiles.append(dst)
    return tiles


def iter_images(target: Path, recursive: bool):
    if target.is_file():
        yield target
    elif target.is_dir():
        globber = target.rglob("*") if recursive else target.glob("*")
        for p in sorted(globber):
            if p.is_file() and p.suffix.lower() in IMG_EXT and p.parent.name != "tiles":
                yield p


def main():
    ap = argparse.ArgumentParser(description="상세 이미지 스마트 타일 분할")
    ap.add_argument("path", help="이미지 파일, 상품 폴더, 또는 details 트리")
    ap.add_argument("--recursive", action="store_true", help="하위 폴더까지 전부")
    ap.add_argument("--target-h", type=int, default=1400, help="타일 목표 높이(px)")
    ap.add_argument("--max-ratio", type=float, default=2.0, help="이 비율 이하면 분할 안 함")
    ap.add_argument("--overlap", type=int, default=80, help="타일 경계 겹침(px)")
    args = ap.parse_args()

    target = Path(args.path)
    if not target.exists():
        sys.exit(f"경로 없음: {target}")

    imgs = list(iter_images(target, args.recursive))
    if not imgs:
        sys.exit("처리할 이미지가 없습니다.")

    print(f"입력 이미지 {len(imgs)}장 처리 중...\n")
    total_tiles, split_cnt = 0, 0
    for p in imgs:
        out_dir = p.parent / "tiles"
        tiles = split_image(p, out_dir, target_h=args.target_h,
                            max_ratio=args.max_ratio, overlap=args.overlap)
        w, h = Image.open(p).size
        total_tiles += len(tiles)
        if len(tiles) > 1:
            split_cnt += 1
        flag = f"→ {len(tiles)}타일" if len(tiles) > 1 else "→ 통과(안 긺)"
        print(f"  {p.parent.name}/{p.name}  ({w}x{h})  {flag}")

    print(f"\n{'='*56}")
    print(f"  완료: {len(imgs)}장 → 타일 {total_tiles}개 "
          f"(분할된 이미지 {split_cnt}장, 평균 {total_tiles/len(imgs):.1f}타일/장)")
    print(f"  저장 위치: 각 이미지 옆 tiles/ 폴더")
    print(f"{'='*56}")


if __name__ == "__main__":
    main()
