"""
11번가 상세페이지 이미지 수집 (Plan B 확정 파이프라인)
- 브라우저/렌더링 불필요. 순수 requests.
- 발견 경로: 상세설명은 iframe = https://www.11st.co.kr/products/{prdNo}/view-desc
             → plain HTML 조각, <img src>에 상세 마케팅 이미지가 직접 박혀 있음.
사용: ./venv/bin/python fetch_11st_desc.py <prdNo>
"""
import sys, re, requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

def fetch_detail_images(prd_no: str) -> list[str]:
    """상품번호 → 상세페이지 이미지 URL 리스트 (순수 requests, 안티봇 없음)."""
    url = f"https://www.11st.co.kr/products/{prd_no}/view-desc"
    r = requests.get(url, headers={
        "User-Agent": UA,
        "Referer": f"https://www.11st.co.kr/products/{prd_no}",
    }, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    urls = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        # 아이콘/썸네일/공지 제외는 다운로드 후 크기로 거르는 게 안전 — 여기선 전부 반환
        urls.append(src)
    # 중복 제거(순서 보존)
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u); out.append(u)
    return out

if __name__ == "__main__":
    prd = sys.argv[1] if len(sys.argv) > 1 else "3458162245"
    imgs = fetch_detail_images(prd)
    print(f"상품 {prd} 상세 이미지 {len(imgs)}개:")
    for u in imgs:
        print("  ", u)
