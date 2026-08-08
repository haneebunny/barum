"""
11번가 상세페이지 이미지 수집기 (완성본 + 중복 제거 A/B)
====================================================
Open API로 상품 검색 → 각 상품의 상세설명(view-desc)에서 상세 마케팅 이미지 다운로드.

핵심 경로 (역추적으로 확정):
    https://www.11st.co.kr/products/{상품번호}/view-desc
    → plain HTML 조각, <img src>에 상세 이미지가 직접 박혀 있음 (브라우저/렌더링 불필요).

출력 구조는 쿠팡 크롤러와 동일:
    {output_dir}/details/{product_code}/detail_000.jpg, ...
    → 기존 VLM 과대광고 판정 파이프라인이 그대로 소비 가능.

중복 제거:
    A. 크로스런 상품 스킵  — 이미 모은 product_code는 재수집 안 함 (--force로 무시)
    B. 완전동일 해시 dedup — 바이트가 같은 이미지는 한 번만 저장 (여러 셀러가 같은
       상세 이미지를 재업로드하는 케이스 차단). 인덱스는 {output_dir}/.dedup_index.json에
       유지되어 다음 실행에도 적용됨.
    (C. 시각적 근접중복 pHash는 미포함 — 필요 시 추가)

사용:
    ./venv/bin/python collect_11st_details.py "다이어트 보조제" --max-products 30
    ./venv/bin/python collect_11st_details.py --codes 3458162245,1062226837
    ./venv/bin/python collect_11st_details.py --from-json 11st_output/11st_....json
    ./venv/bin/python collect_11st_details.py "다이어트 보조제" --force   # 중복 스킵 끔
"""
import argparse
import hashlib
import io
import json
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from PIL import Image

from eleventh_st_crawler import EleventhStCrawler, API_KEY

Image.MAX_IMAGE_PIXELS = None
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

MIN_SIDE = 200
VALID_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp")
INDEX_NAME = ".dedup_index.json"


# ── (A) 이미 모은 상품 ─────────────────────────────
def existing_codes(output_dir: str) -> set[str]:
    """이미 상세 이미지를 확보한 product_code 집합 (details/{code}/detail_* 존재)."""
    root = Path(output_dir) / "details"
    if not root.exists():
        return set()
    return {d.name for d in root.iterdir()
            if d.is_dir() and any(d.glob("detail_*"))}


# ── (B) 완전동일 해시 인덱스 ───────────────────────
def load_dedup_index(output_dir: str) -> dict[str, str]:
    """sha256 → 최초 저장 경로. 인덱스 파일이 없으면 기존 이미지들을 해시해 생성."""
    idx_path = Path(output_dir) / INDEX_NAME
    if idx_path.exists():
        try:
            return json.loads(idx_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # 인덱스 없음 → 기존 details 이미지들로 재구성 (최초 1회)
    index: dict[str, str] = {}
    for f in (Path(output_dir) / "details").glob("*/detail_*"):
        try:
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            index.setdefault(h, str(f))
        except Exception:
            continue
    return index


def save_dedup_index(output_dir: str, index: dict[str, str]) -> None:
    (Path(output_dir) / INDEX_NAME).write_text(
        json.dumps(index, ensure_ascii=False, indent=0), encoding="utf-8")


# ── 상세 이미지 URL ────────────────────────────────
def fetch_detail_image_urls(prd_no: str, session: requests.Session) -> list[str]:
    url = f"https://www.11st.co.kr/products/{prd_no}/view-desc"
    r = session.get(url, headers={"Referer": f"https://www.11st.co.kr/products/{prd_no}"},
                    timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    urls, seen = [], set()
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original")
        if not src:
            continue
        src = src.strip()
        if src.startswith("//"):
            src = "https:" + src
        if not src.startswith("http") or src in seen:
            continue
        seen.add(src)
        urls.append(src)
    return urls


def _download(url: str, session: requests.Session):
    r = session.get(url, timeout=25)
    r.raise_for_status()
    data = r.content
    try:
        w, h = Image.open(io.BytesIO(data)).size
    except Exception:
        w = h = 0
    return data, w, h


# ── 수집 본체 ──────────────────────────────────────
def collect_details(products: list[dict], output_dir: str = "11st_output",
                    delay: float = 0.4, dedup_index: dict[str, str] | None = None) -> list[dict]:
    base = Path(output_dir)
    details_root = base / "details"
    details_root.mkdir(parents=True, exist_ok=True)

    index = dedup_index if dedup_index is not None else {}
    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    manifest = []
    dup_total = 0
    for i, p in enumerate(products, 1):
        code = str(p.get("product_code") or "").strip()
        name = p.get("product_name", "")
        if not code:
            continue

        try:
            urls = fetch_detail_image_urls(code, session)
        except Exception as e:
            print(f"[{i}/{len(products)}] {code} {name[:32]}  ✗ view-desc 실패: {e}")
            manifest.append({"product_code": code, "product_name": name, "status": f"error: {e}",
                             "detail_image_count": 0, "dup_count": 0, "detail_images": []})
            time.sleep(delay)
            continue

        pdir = details_root / code
        pdir.mkdir(exist_ok=True)

        imgs, idx, skipped, dups = [], 0, 0, 0
        for u in urls:
            try:
                data, w, h = _download(u, session)
            except Exception:
                skipped += 1
                continue
            if max(w, h) < MIN_SIDE:                 # 아이콘/버튼 제외
                skipped += 1
                continue
            sha = hashlib.sha256(data).hexdigest()
            if sha in index:                          # (B) 완전동일 → 저장 안 함
                dups += 1
                imgs.append({"url": u, "sha256": sha, "width": w, "height": h,
                             "skipped_as_dup": True, "dup_of": index[sha]})
                continue
            ext = u.split("?")[0].rsplit(".", 1)[-1].lower()
            ext = f".{ext}" if f".{ext}" in VALID_EXT else ".jpg"
            fn = f"detail_{idx:03d}{ext}"
            (pdir / fn).write_bytes(data)
            index[sha] = str(pdir / fn)               # 인덱스 등록
            imgs.append({"url": u, "filename": fn, "filepath": str(pdir / fn),
                         "sha256": sha, "width": w, "height": h, "size_bytes": len(data)})
            idx += 1

        saved = idx
        dup_total += dups
        status = "ok" if saved else ("all_dup" if dups else "empty")
        note = ""
        if dups:
            note += f" (완전중복 {dups} 재사용)"
        if skipped:
            note += f" (잡이미지 {skipped} 제외)"
        if not saved and not dups:
            note += "  ⚠ 상세이미지 없음(셀러 lazy-load일 수 있음 → Playwright 폴백)"
        print(f"[{i}/{len(products)}] {code} {name[:32]:32} → 신규저장 {saved}개{note}")

        manifest.append({"product_code": code, "product_name": name,
                         "detail_url": p.get("detail_url", ""), "seller": p.get("seller", ""),
                         "status": status, "detail_image_count": saved, "dup_count": dups,
                         "detail_images": imgs})
        time.sleep(delay)

    if dup_total:
        print(f"\n  ※ 완전동일 이미지 {dup_total}건은 재저장/재판정 없이 스킵됨 (비용·통계 보호)")
    return manifest


# ── 상품 목록 확보 (A: 이미 모은 상품 스킵) ─────────
def _get_products(args, skip: set[str]) -> tuple[list[dict], int]:
    skipped = 0

    def _filter(prods):
        nonlocal skipped
        out = []
        for p in prods:
            c = str(p.get("product_code") or "").strip()
            if not c:
                continue
            if not args.force and c in skip:
                skipped += 1
                continue
            out.append(p)
        return out

    if args.from_json:
        data = json.load(open(args.from_json, encoding="utf-8"))
        prods = data.get("products", data if isinstance(data, list) else [])
        return _filter(prods)[: args.max_products], skipped

    if args.codes:
        prods = [{"product_code": c.strip(), "product_name": ""}
                 for c in args.codes.split(",") if c.strip()]
        return _filter(prods)[: args.max_products], skipped

    # 검색어: '신규' 상품을 max_products개 모을 때까지 페이지 진행
    crawler = EleventhStCrawler(api_key=args.api_key)
    collected, seen_codes, page = [], set(), 1
    while len(collected) < args.max_products and page <= 20:
        found = crawler.search_products(args.keyword, page)
        if not found:
            break
        for p in found:
            c = str(p.get("product_code") or "").strip()
            if not c or c in seen_codes:
                continue
            seen_codes.add(c)
            if not args.force and c in skip:          # (A) 이미 모은 상품
                skipped += 1
                continue
            collected.append(p)
            if len(collected) >= args.max_products:
                break
        page += 1
        time.sleep(0.3)
    return collected, skipped


def main():
    ap = argparse.ArgumentParser(description="11번가 상세페이지 이미지 수집기 (+중복제거)")
    ap.add_argument("keyword", nargs="?", default=None)
    ap.add_argument("--codes", default=None, help="상품번호 직접 지정 (쉼표 구분)")
    ap.add_argument("--from-json", default=None, help="기존 11st JSON에서 상품 로드")
    ap.add_argument("--max-products", type=int, default=30, help="수집할 '신규' 상품 수")
    ap.add_argument("--output-dir", default="11st_output")
    ap.add_argument("--delay", type=float, default=0.4)
    ap.add_argument("--force", action="store_true", help="이미 모은 상품/중복 무시하고 재수집")
    ap.add_argument("--api-key", default=API_KEY)
    args = ap.parse_args()

    if not (args.keyword or args.codes or args.from_json):
        ap.error("검색어, --codes, --from-json 중 하나는 필요합니다.")

    print(f"\n{'='*60}\n  11번가 상세페이지 이미지 수집기 (+중복제거 A/B)\n{'='*60}")
    skip = set() if args.force else existing_codes(args.output_dir)
    dedup_index = {} if args.force else load_dedup_index(args.output_dir)
    if skip:
        print(f"  이미 모은 상품 {len(skip)}개 → 스킵 대상 (--force로 무시 가능)")
    if dedup_index:
        print(f"  기존 이미지 해시 인덱스 {len(dedup_index)}개 로드")

    products, skipped_cnt = _get_products(args, skip)
    print(f"  이번에 수집할 신규 상품: {len(products)}개  (스킵된 기존 상품 {skipped_cnt}개)")
    print(f"{'='*60}\n")

    manifest = collect_details(products, output_dir=args.output_dir,
                               delay=args.delay, dedup_index=dedup_index)

    if not args.force:
        save_dedup_index(args.output_dir, dedup_index)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(args.output_dir) / f"11st_details_{ts}.json"
    out.write_text(json.dumps({
        "source": "11st_view_desc", "collected_at": datetime.now().isoformat(),
        "query": args.keyword, "total_products": len(manifest), "products": manifest,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = sum(1 for m in manifest if m["status"] == "ok")
    total_imgs = sum(m["detail_image_count"] for m in manifest)
    total_dups = sum(m.get("dup_count", 0) for m in manifest)
    print(f"\n{'='*60}")
    print(f"  완료: 신규 상세이미지 {total_imgs}장 / {ok}개 상품")
    print(f"        완전중복 스킵 {total_dups}건, 기존상품 스킵 {skipped_cnt}개")
    print(f"  매니페스트: {out}")
    print(f"  해시 인덱스: {args.output_dir}/{INDEX_NAME}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
