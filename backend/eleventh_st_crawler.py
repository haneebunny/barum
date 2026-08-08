"""
11번가 Open API 상품 이미지 크롤러
====================================
11번가 공식 Open API를 사용하여 상품 검색 + 이미지 수집.
봇 탐지 없이 빠르고 안정적으로 대량 수집 가능.

사용법:
    python eleventh_st_crawler.py "다이어트 보조제" --max-products 100
    python eleventh_st_crawler.py "건강기능식품" --max-products 500 --no-download

설치:
    pip install requests pandas beautifulsoup4

파이프라인 임포트:
    from eleventh_st_crawler import crawl_11st
    results = crawl_11st("다이어트 보조제", max_products=100)
"""

import csv
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────

# 11번가 Open API 키는 env로 관리한다(하드코딩 금지 — public 리포).
# backend/.env 에 ELEVENTH_ST_API_KEY 를 두거나, --api-key 로 넘긴다.
load_dotenv()
API_KEY = os.environ.get("ELEVENTH_ST_API_KEY", "")
BASE_URL = "http://openapi.11st.co.kr/openapi/OpenApiService.tmall"

DEFAULT_CONFIG = {
    "max_products": 100,
    "max_pages": 10,        # 페이지당 약 50개 상품
    "delay": 0.3,           # API 호출 간 딜레이(초) - 공식 API라 짧아도 됨
    "download_images": True,
    "output_dir": "11st_output",
}


class EleventhStCrawler:
    """11번가 Open API 기반 상품 크롤러"""

    def __init__(self, api_key=API_KEY, config=None):
        self.api_key = api_key
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })

    def search_products(self, keyword, page=1):
        """상품 검색 API 호출"""
        params = {
            "key": self.api_key,
            "apiCode": "ProductSearch",
            "keyword": keyword,
            "pageNum": page,
            "pageSize": 50,
        }
        try:
            resp = self.session.get(BASE_URL, params=params, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [오류] API 호출 실패 (page {page}): {e}")
            return []

        # XML 파싱 (cp949 인코딩)
        try:
            xml_data = resp.content.decode("cp949", errors="replace")
        except Exception:
            xml_data = resp.text

        soup = BeautifulSoup(xml_data, "html.parser")

        # 에러 체크
        error_code = soup.find("code")
        if error_code and error_code.text.strip() != "200":
            error_msg = soup.find("message")
            print(f"  [API 오류] {error_code.text}: {error_msg.text if error_msg else '알 수 없는 오류'}")
            return []

        products = []
        for product in soup.find_all("product"):
            item = {}

            # 상품 코드
            code = product.find("productcode")
            item["product_code"] = code.text.strip() if code else ""

            # 상품명
            name = product.find("productname")
            item["product_name"] = name.text.strip() if name else ""

            # 가격
            price = product.find("productprice")
            item["price"] = price.text.strip() if price else ""

            # 이미지 URL들
            img = product.find("productimage")
            item["image_url"] = img.text.strip() if img else ""

            img100 = product.find("productimage100")
            item["image_url_100"] = img100.text.strip() if img100 else ""

            img150 = product.find("productimage150")
            item["image_url_150"] = img150.text.strip() if img150 else ""

            img200 = product.find("productimage200")
            item["image_url_200"] = img200.text.strip() if img200 else ""

            img250 = product.find("productimage250")
            item["image_url_250"] = img250.text.strip() if img250 else ""

            img300 = product.find("productimage300")
            item["image_url_300"] = img300.text.strip() if img300 else ""

            img800 = product.find("productimage800")
            item["image_url_800"] = img800.text.strip() if img800 else ""

            # 상세 URL
            detail_url = product.find("detailpageurl")
            item["detail_url"] = detail_url.text.strip() if detail_url else ""

            # 판매자
            seller = product.find("seller")
            item["seller"] = seller.text.strip() if seller else ""

            # 카테고리
            cat = product.find("category")
            item["category"] = cat.text.strip() if cat else ""

            # 평점
            rating = product.find("rating")
            item["rating"] = rating.text.strip() if rating else ""

            if item["product_code"]:
                products.append(item)

        return products

    def download_image(self, url, save_path):
        """이미지 다운로드 + SHA-256 해시"""
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            img_data = resp.content
            sha256 = hashlib.sha256(img_data).hexdigest()

            with open(save_path, "wb") as f:
                f.write(img_data)

            return sha256
        except Exception as e:
            print(f"  [다운로드 실패] {url}: {e}")
            return None

    def run(self, keyword, max_products=None, output_dir=None, download=None):
        """전체 크롤링 실행"""
        max_products = max_products or self.config["max_products"]
        output_dir = output_dir or self.config["output_dir"]
        download = download if download is not None else self.config["download_images"]

        # 출력 디렉토리 생성
        base_dir = Path(output_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        if download:
            img_dir = base_dir / "images"
            img_dir.mkdir(exist_ok=True)

        print(f"\n{'='*60}")
        print(f"  11번가 Open API 크롤러")
        print(f"  검색어: {keyword}")
        print(f"  목표: 최대 {max_products}개 상품")
        print(f"  이미지 다운로드: {'예' if download else '아니오'}")
        print(f"{'='*60}\n")

        all_products = []
        page = 1

        while len(all_products) < max_products and page <= self.config["max_pages"]:
            print(f"[페이지 {page}] 검색 중...")
            products = self.search_products(keyword, page)

            if not products:
                print(f"  → 더 이상 결과 없음. 종료.")
                break

            for p in products:
                if len(all_products) >= max_products:
                    break

                # 중복 체크 (상품코드 기준)
                if any(ep["product_code"] == p["product_code"] for ep in all_products):
                    continue

                all_products.append(p)
                print(f"  [{len(all_products):4d}] {p['product_name'][:50]}")

                # 이미지 다운로드 (가장 큰 사이즈 우선)
                if download:
                    img_url = (p.get("image_url_800") or p.get("image_url_300")
                               or p.get("image_url_250") or p.get("image_url"))
                    if img_url:
                        ext = os.path.splitext(img_url.split("?")[0])[-1] or ".jpg"
                        save_path = img_dir / f"{p['product_code']}{ext}"
                        sha = self.download_image(img_url, save_path)
                        if sha:
                            p["image_sha256"] = sha
                            p["image_local_path"] = str(save_path)

            print(f"  → 누적: {len(all_products)}개 수집")
            page += 1
            time.sleep(self.config["delay"])

        # ── 결과 저장 ──
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # CSV 저장
        csv_path = base_dir / f"11st_{keyword}_{timestamp}.csv"
        if all_products:
            fieldnames = list(all_products[0].keys())
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_products)

        # JSON 저장
        json_path = base_dir / f"11st_{keyword}_{timestamp}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "query": keyword,
                "source": "11st_openapi",
                "crawled_at": datetime.now().isoformat(),
                "total_products": len(all_products),
                "products": all_products
            }, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"  크롤링 완료!")
        print(f"  총 수집: {len(all_products)}개 상품")
        print(f"  CSV: {csv_path}")
        print(f"  JSON: {json_path}")
        if download:
            img_count = sum(1 for p in all_products if p.get("image_sha256"))
            print(f"  이미지: {img_count}개 다운로드됨")
        print(f"{'='*60}\n")

        return all_products


# ──────────────────────────────────────────────
# 파이프라인용 함수 (F1에서 import해서 사용)
# ──────────────────────────────────────────────

def crawl_11st(query, max_products=100, output_dir="11st_output", download=True, api_key=API_KEY):
    """
    F1 파이프라인에서 호출하는 함수.

    Args:
        query: 검색 키워드
        max_products: 최대 수집 상품 수
        output_dir: 출력 디렉토리
        download: 이미지 다운로드 여부
        api_key: 11번가 API 키

    Returns:
        list[dict]: 수집된 상품 정보 리스트
    """
    crawler = EleventhStCrawler(api_key=api_key)
    return crawler.run(query, max_products=max_products,
                       output_dir=output_dir, download=download)


# ──────────────────────────────────────────────
# CLI 실행
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="11번가 Open API 상품 이미지 크롤러")
    parser.add_argument("keyword", help="검색 키워드")
    parser.add_argument("--max-products", type=int, default=100, help="최대 수집 상품 수 (기본: 100)")
    parser.add_argument("--output-dir", default="11st_output", help="출력 디렉토리 (기본: 11st_output)")
    parser.add_argument("--no-download", action="store_true", help="이미지 다운로드 안 함 (URL만 수집)")
    parser.add_argument("--api-key", default=API_KEY, help="11번가 API 키")

    args = parser.parse_args()

    crawler = EleventhStCrawler(api_key=args.api_key)
    crawler.run(
        keyword=args.keyword,
        max_products=args.max_products,
        output_dir=args.output_dir,
        download=not args.no_download
    )