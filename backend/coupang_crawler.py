"""
쿠팡 상세페이지 이미지 크롤러 (DrissionPage)
==============================================
실제 브라우저(Whale/Chrome)를 제어하여 봇 탐지를 우회합니다.
검색어 → 상품 목록 수집 → 상세페이지 이미지 크롤링

사용법:
    python coupang_crawler.py "다이어트 보조제" --max-products 50
    python coupang_crawler.py "건강기능식품" --max-products 100 --no-download

설치:
    pip install DrissionPage pandas requests

주의:
    실행 전 Whale/Chrome 브라우저를 모두 닫아주세요.
    DrissionPage가 브라우저를 직접 실행합니다.
"""

import csv
import hashlib
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
except ImportError:
    print("DrissionPage가 설치되어 있지 않습니다.")
    print("설치: pip install DrissionPage")
    sys.exit(1)

import requests


# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────

DEFAULT_CONFIG = {
    "max_products": 50,
    "max_pages": 5,
    "delay_min": 3.0,
    "delay_max": 7.0,
    "scroll_delay": 0.5,
    "download_images": True,
    # 이미지 수집이 연속 몇 번 실패하면 '차단'으로 판단하고 크롤링을 중단할지
    "fail_streak_threshold": 3,
    # 사용할 브라우저: 'auto'(Whale→Chrome) | 'chrome' | 'whale'
    "browser": "auto",
    # 반수동 모드: 차단 감지 시 멈추고 사용자가 브라우저에서 직접 로그인/차단 해제
    "manual": False,
}

# Whale 브라우저 경로 (Mac 기준)
WHALE_PATHS = [
    "/Applications/Naver Whale.app/Contents/MacOS/Whale",
    "/Applications/Whale.app/Contents/MacOS/Whale",
    os.path.expanduser("~/Applications/Naver Whale.app/Contents/MacOS/Whale"),
]

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
]


# ──────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────

def safe_filename(text: str, max_len: int = 80) -> str:
    text = re.sub(r'[\\/*?:"<>|]', '_', text)
    text = re.sub(r'\s+', '_', text).strip('_')
    return text[:max_len]


def file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)


def random_sleep(min_s: float, max_s: float):
    time.sleep(random.uniform(min_s, max_s))


def find_browser_path(prefer: str = "auto"):
    """설치된 브라우저 경로를 찾습니다.

    prefer: 'chrome' → Chrome 우선, 'whale' → Whale 우선, 'auto' → Whale→Chrome 순.
    """
    whale = [p for p in WHALE_PATHS if os.path.exists(p)]
    chrome = [p for p in CHROME_PATHS if os.path.exists(p)]
    if prefer == "chrome":
        order = chrome + whale
    elif prefer == "whale":
        order = whale + chrome
    else:
        order = whale + chrome
    for path in order:
        print(f"  → 브라우저 발견: {path}")
        return path
    return None


# ──────────────────────────────────────────────
# 크롤러
# ──────────────────────────────────────────────

class CoupangCrawler:
    """DrissionPage 기반 쿠팡 크롤러 — 실제 브라우저 사용으로 봇 탐지 우회"""

    def __init__(self, config: dict = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.results = []
        self.page = None
        self.aborted = False  # 연속 실패로 크롤링이 중단됐는지

    def _init_browser(self):
        """실제 브라우저(Whale/Chrome)를 실행합니다."""
        co = ChromiumOptions()

        # 브라우저 경로 설정
        browser_path = find_browser_path(self.config.get("browser", "auto"))
        if browser_path:
            co.set_browser_path(browser_path)
        else:
            print("  → Whale/Chrome을 찾지 못했습니다. 시스템 기본 브라우저를 시도합니다.")

        # 브라우저 옵션
        co.set_argument("--start-maximized")
        co.set_argument("--disable-infobars")
        co.set_argument("--lang=ko-KR")

        # 자동화 탐지 방지
        co.set_argument("--disable-blink-features=AutomationControlled")

        # 새 프로필 사용 (기존 브라우저 세션과 충돌 방지)
        # 기존 쿠키를 쓰고 싶으면 아래 줄을 주석 처리
        # co.set_argument("--incognito")

        self.page = ChromiumPage(co)

    def _close_browser(self):
        if self.page:
            try:
                self.page.quit()
            except Exception:
                pass

    # ── 사람처럼 행동 ──

    def _human_scroll(self, times: int = 3):
        """사람처럼 스크롤"""
        for _ in range(times):
            scroll_amount = random.randint(300, 700)
            self.page.scroll.down(scroll_amount)
            time.sleep(random.uniform(0.3, 0.8))

    def _human_move_mouse(self):
        """마우스를 랜덤 위치로 이동"""
        try:
            self.page.actions.move(
                random.randint(100, 800),
                random.randint(100, 500)
            )
        except Exception:
            pass

    # ── 워밍업: 쿠팡 메인 방문 ──

    def warmup(self):
        """쿠팡 메인 페이지를 방문하여 쿠키/세션을 획득합니다."""
        print("  [워밍업] 쿠팡 메인 방문 중...")
        self.page.get("https://www.coupang.com")
        time.sleep(3)

        # 사람처럼 행동
        self._human_move_mouse()
        time.sleep(1)
        self._human_scroll(2)
        time.sleep(2)

        # 접근 차단 확인
        body_text = self.page.html
        if "사용권한이 제한" in body_text or "permission" in body_text.lower():
            print("  [워밍업] 메인 페이지도 차단됨 — 수동 로그인이 필요할 수 있습니다")
            print("  → 브라우저에서 직접 쿠팡에 로그인한 후 다시 실행해주세요")
            return False

        print("  [워밍업] 쿠키 확보 완료!")
        return True

    # ── 검색 ──

    def search_products(self, query: str) -> list[dict]:
        """검색어로 상품 목록을 수집합니다."""
        products = []
        max_products = self.config["max_products"]
        max_pages = self.config["max_pages"]

        for page_num in range(1, max_pages + 1):
            if len(products) >= max_products:
                break

            if page_num == 1:
                # 첫 페이지: 검색창에 직접 입력
                print(f"[검색] 검색어 입력: '{query}'")
                try:
                    # 검색창 찾기
                    search_input = self.page.ele(
                        'css:input.search-input,'
                        'css:input[name="q"],'
                        'css:input#headerSearchKeyword,'
                        'css:input[type="search"]',
                        timeout=5
                    )
                    if search_input:
                        search_input.click()
                        time.sleep(0.5)
                        search_input.clear()
                        time.sleep(0.3)
                        # 사람처럼 한 글자씩 입력
                        search_input.input(query, clear=True)
                        time.sleep(0.5)
                        # Enter 키로 검색
                        self.page.actions.key_down("Enter").key_up("Enter")
                        time.sleep(3)
                    else:
                        raise Exception("검색창을 찾을 수 없음")

                except Exception as e:
                    print(f"  [검색창 실패: {e}] URL로 직접 이동")
                    url = f"https://www.coupang.com/np/search?component=&q={quote(query)}&channel=user"
                    self.page.get(url)
                    time.sleep(3)
            else:
                url = f"https://www.coupang.com/np/search?component=&q={quote(query)}&channel=user&page={page_num}"
                print(f"[검색] 페이지 {page_num} 이동...")
                self.page.get(url)
                time.sleep(3)

            # 접근 차단 확인
            if "사용권한이 제한" in self.page.html:
                print("  [차단] 접근이 차단되었습니다. 딜레이 후 재시도...")
                random_sleep(15, 30)
                self.page.refresh()
                time.sleep(5)
                if "사용권한이 제한" in self.page.html:
                    print("  [차단] 여전히 차단됨. 검색 중단.")
                    break

            # 스크롤하여 상품 로딩
            self._human_scroll(4)
            time.sleep(1)

            # 상품 링크 수집
            try:
                links = self.page.eles('css:a[href*="/vp/products/"]')
                seen_ids = {p["product_id"] for p in products}
                page_products = []

                for link in links:
                    try:
                        href = link.attr("href") or ""
                        match = re.search(r'/vp/products/(\d+)', href)
                        if not match or match.group(1) in seen_ids:
                            continue

                        product_id = match.group(1)
                        seen_ids.add(product_id)

                        # 상품명 추출
                        name = ""
                        try:
                            # 부모 li 요소에서 이름 찾기
                            li = link.parent("li")
                            if li:
                                name_el = li.ele('css:.name, css:.product-name, css:[class*="name"]', timeout=1)
                                if name_el:
                                    name = name_el.text.strip()
                        except Exception:
                            pass
                        if not name:
                            name = link.text.strip()

                        # 가격 추출
                        price = ""
                        try:
                            if li:
                                price_el = li.ele('css:.price-value, css:[class*="price"] strong', timeout=1)
                                if price_el:
                                    price = price_el.text.strip()
                        except Exception:
                            pass

                        name = re.sub(r'\s+', ' ', name)[:200]
                        if len(name) > 3:
                            page_products.append({
                                "url": f"https://www.coupang.com/vp/products/{product_id}",
                                "name": name,
                                "price": price,
                                "product_id": product_id,
                            })
                    except Exception:
                        continue

                products.extend(page_products)
                print(f"  → {len(page_products)}개 상품 발견 (누적: {len(products)}개)")

                if len(page_products) == 0:
                    print("  → 더 이상 상품 없음, 검색 종료")
                    break

            except Exception as e:
                print(f"  [오류] 상품 목록 추출 실패: {e}")

            random_sleep(self.config["delay_min"], self.config["delay_max"])

        return products[:max_products]

    # ── 상세페이지 이미지 추출 ──

    def crawl_product_detail(self, product: dict) -> dict:
        """상품 URL로 이동해 상세 이미지를 추출한다 (자동 경로)."""
        try:
            self.page.get(product["url"])
            time.sleep(3)
            return self._extract_from(self.page, product)
        except Exception as e:
            product.update({
                "main_images": [], "detail_images": [], "all_images": [],
                "image_count": 0, "has_video": False,
                "crawled_at": datetime.now().isoformat(),
                "status": f"error: {str(e)}",
            })
            print(f"  [오류] {product['product_id']}: {e}")
            return product

    def _extract_from(self, target, product: dict) -> dict:
        """이미 로드된 페이지/탭(target)에서 상세 이미지를 추출한다. 재이동(get)하지 않는다.

        target: ChromiumPage 또는 ChromiumTab. 반수동 재시도 시 사용자가 직접 연 탭을
        그대로 긁기 위해, 추출 로직을 대상 객체로 분리했다.
        """
        # 스크롤하여 상세 이미지 lazy load 트리거
        try:
            for _ in range(5):
                target.scroll.down(random.randint(300, 700))
                time.sleep(0.4)
            for _ in range(5):
                target.scroll.down(800)
                time.sleep(0.5)
        except Exception:
            pass

        # 1) 메인 썸네일 이미지
        main_images = []
        try:
            imgs = target.eles(
                'css:.prod-image img, '
                'css:.prod-image__item img, '
                'css:.subType-IMAGE img, '
                'css:img[src*="coupangcdn"], '
                'css:img[src*="thumbnail"]'
            )
            for img in imgs:
                src = img.attr("src") or img.attr("data-src") or ""
                if src and src.startswith("http") and "icon" not in src and "logo" not in src:
                    # 고해상도 변환
                    src = re.sub(r'/q/\d+', '/q/100', src)
                    src = re.sub(r'/w/\d+', '/w/800', src)
                    if src not in main_images:
                        main_images.append(src)
        except Exception:
            pass

        # 2) 상세 설명 이미지
        detail_images = []
        try:
            detail_selectors = [
                'css:.product-detail-content-inside img',
                'css:.vendor-item-root-content img',
                'css:#productDetail img',
                'css:.product-detail img',
                'css:.product-body img',
            ]
            for sel in detail_selectors:
                try:
                    imgs = target.eles(sel, timeout=2)
                    for img in imgs:
                        src = img.attr("src") or img.attr("data-src") or img.attr("data-original") or ""
                        if (src and src.startswith("http") and
                            "icon" not in src and "logo" not in src and
                            "1x1" not in src and "pixel" not in src and
                            src not in detail_images and src not in main_images):
                            detail_images.append(src)
                except Exception:
                    continue
        except Exception:
            pass

        # 3) 영상 존재 감지 (F4 플래그)
        has_video = False
        try:
            videos = target.eles('css:video, css:iframe[src*="youtube"], css:iframe[src*="vimeo"]', timeout=2)
            has_video = len(videos) > 0
        except Exception:
            pass

        # 4) 페이지 제목
        page_title = ""
        try:
            title_el = target.ele(
                'css:.prod-buy-header__title, css:h1.title, css:h2.prod-buy-header__title',
                timeout=2
            )
            page_title = title_el.text.strip() if title_el else target.title
        except Exception:
            page_title = getattr(target, "title", "")

        image_count = len(main_images) + len(detail_images)
        product.update({
            "page_title": page_title,
            "main_images": main_images,
            "detail_images": detail_images,
            "all_images": main_images + detail_images,
            "image_count": image_count,
            "has_video": has_video,
            "crawled_at": datetime.now().isoformat(),
            # 이미지가 한 장도 없으면 성공이 아니라 실패로 표시 (차단/렌더 실패 신호)
            "status": "success" if image_count > 0 else "fail_no_images",
        })
        return product

    # ── 차단 판정 (반수동 모드용) ──

    @staticmethod
    def _looks_blocked(product: dict) -> bool:
        """상세페이지가 차단/챌린지로 보이는지 판정.

        상품 상세가 정상 렌더되면 page_title에 상품명이 들어오고 이미지가 잡힌다.
        차단 시엔 상품 콘텐츠가 없어 제목이 사이트 기본값('쿠팡!')으로 폴백되고 이미지도 0장.
        """
        title = (product.get("page_title") or "").strip()
        no_images = product.get("image_count", 0) == 0
        generic_title = title in ("", "쿠팡!", "쿠팡")
        return no_images or generic_title

    def _manual_pause_and_retry(self, product: dict, idx: int, total: int) -> dict:
        """반수동 모드: 차단된 상품에서 멈추고 사용자 입력을 받아 재시도/건너뛰기/종료.

        반환: {"action": "continue"|"skip"|"quit", "product": product}
        """
        while True:
            print("\n" + "─" * 60)
            print(f"  ⏸  [{idx + 1}/{total}] 차단 감지 — 상세페이지가 정상 로드되지 않았습니다.")
            print(f"     상품: {product['name'][:50]}")
            print(f"     URL : {product['url']}")
            print("     → 브라우저에서 로그인하거나 차단을 해제하세요.")
            print("     정상 상품 페이지가 뜨면 [Enter]=재시도 · [s]=이 상품 건너뛰기 · [q]=종료")
            print("─" * 60)
            try:
                choice = input("     입력> ").strip().lower()
            except EOFError:
                # 비대화형(백그라운드) 실행이면 입력을 받을 수 없음 → 건너뛰기 처리
                print("     [비대화형 실행] 입력을 받을 수 없어 이 상품을 건너뜁니다.")
                product["status"] = "fail_skipped"
                return {"action": "skip", "product": product}

            if choice == "q":
                product["status"] = "fail_skipped"
                print("     크롤링을 종료합니다.")
                return {"action": "quit", "product": product}
            if choice == "s":
                product["status"] = "fail_skipped"
                print("     이 상품을 건너뜁니다.")
                return {"action": "skip", "product": product}

            # Enter(빈 입력) 또는 기타 → 재이동하지 않고, 사용자가 지금 열어둔 탭을 그대로 긁는다.
            # (URL을 다시 열면 방금 푼 차단이 재발하므로, 최신 활성 탭에서 추출만 한다)
            print("     현재 열려 있는 탭에서 다시 읽는 중...")
            try:
                target = self.page.latest_tab
            except Exception:
                target = self.page
            product = self._extract_from(target, product)
            if not self._looks_blocked(product):
                print(f"     ✅ 정상 로드 — 이미지 {product.get('image_count', 0)}장 확인.")
                return {"action": "continue", "product": product}
            print("     여전히 이미지를 못 찾았습니다. 페이지를 끝까지 스크롤했는지 확인 후 "
                  "다시 [Enter], 또는 [s]/[q].")

    # ── 이미지 다운로드 ──

    def download_images(self, product: dict, output_dir: str):
        product_id = product["product_id"]
        product_dir = os.path.join(output_dir, "images", safe_filename(product_id))
        ensure_dir(product_dir)

        # 브라우저의 쿠키를 requests 세션에 복사
        session = requests.Session()
        try:
            cookies = self.page.cookies()
            for cookie in cookies:
                session.cookies.set(cookie.get("name", ""), cookie.get("value", ""))
        except Exception:
            pass

        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 Whale/4.38.386.14 Safari/537.36"
            ),
            "Referer": "https://www.coupang.com/",
        })

        downloaded = []
        for i, img_url in enumerate(product.get("all_images", [])):
            try:
                ext_match = re.search(r'\.(jpg|jpeg|png|gif|webp)', img_url, re.I)
                ext = ext_match.group(1) if ext_match else "jpg"
                img_type = "main" if i < len(product.get("main_images", [])) else "detail"
                filename = f"{img_type}_{i:03d}.{ext}"
                filepath = os.path.join(product_dir, filename)

                resp = session.get(img_url, timeout=15)
                if resp.status_code == 200 and len(resp.content) > 100:
                    with open(filepath, "wb") as f:
                        f.write(resp.content)
                    downloaded.append({
                        "filename": filename, "filepath": filepath,
                        "url": img_url, "size_bytes": len(resp.content),
                        "hash": file_hash(resp.content), "type": img_type,
                    })
            except Exception as e:
                print(f"    [다운로드 실패] {img_url}: {e}")

        product["downloaded_files"] = downloaded
        return product

    # ── 메인 실행 ──

    def run(self, query: str, output_dir: str = "./coupang_output"):
        ensure_dir(output_dir)
        start_time = time.time()

        print("=" * 60)
        print(f"쿠팡 크롤러 시작 (DrissionPage — 실제 브라우저)")
        print(f"검색어: {query}")
        print(f"최대 상품 수: {self.config['max_products']}")
        print(f"출력 경로: {output_dir}")
        print("=" * 60)
        print()
        print("⚠️  실행 전 Whale/Chrome 브라우저를 모두 닫아주세요!")
        print()

        try:
            print("[1/5] 브라우저 실행...")
            self._init_browser()

            print("[2/5] 워밍업 — 쿠키/세션 확보...")
            if not self.warmup():
                print("\n메인 페이지 접근 실패. 아래를 시도해주세요:")
                print("1. 브라우저에서 직접 coupang.com 접속")
                print("2. 로그인")
                print("3. 크롤러 다시 실행")
                return []

            print(f"\n[3/5] 상품 검색 중... ('{query}')")
            products = self.search_products(query)
            print(f"  → 총 {len(products)}개 상품 수집 완료")

            if not products:
                print("\n검색 결과가 없습니다.")
                return []

            print(f"\n[4/5] 상세페이지 크롤링 중... (총 {len(products)}개)")
            threshold = self.config["fail_streak_threshold"]
            manual = self.config.get("manual", False)
            if manual:
                print("  🖐  반수동 모드: 차단이 감지되면 멈춥니다. "
                      "브라우저에서 직접 풀어주세요.")
            consecutive_fails = 0
            for i, product in enumerate(products):
                print(f"  [{i+1}/{len(products)}] {product['name'][:50]}...")
                product = self.crawl_product_detail(product)

                # 반수동 모드: 차단으로 보이면 사용자가 풀 때까지 멈춘다
                if manual and self._looks_blocked(product):
                    decision = self._manual_pause_and_retry(product, i, len(products))
                    product = decision["product"]
                    if decision["action"] == "quit":
                        self.results.append(product)
                        self.aborted = True
                        break

                if self.config["download_images"] and product["status"] == "success":
                    product = self.download_images(product, output_dir)

                self.results.append(product)

                # 자동 모드에서만: 이미지 수집 연속 실패 → 임계 도달 시 차단으로 보고 중단.
                # (반수동 모드는 사용자가 직접 통제하므로 자동 중단하지 않음)
                if not manual:
                    if product["status"] == "success":
                        consecutive_fails = 0
                    else:
                        consecutive_fails += 1
                        print(f"    ⚠️  이미지 수집 실패 ({product['status']}) "
                              f"— 연속 {consecutive_fails}/{threshold}")
                        if consecutive_fails >= threshold:
                            print(f"\n  🛑 연속 {threshold}회 이미지 수집 실패 — "
                                  f"차단으로 판단하고 크롤링을 중단합니다.")
                            self.aborted = True
                            break

                if i < len(products) - 1:
                    random_sleep(self.config["delay_min"], self.config["delay_max"])

            print(f"\n[5/5] 결과 저장 중...")
            self._save_results(query, output_dir)

        finally:
            self._close_browser()

        elapsed = time.time() - start_time
        success = sum(1 for r in self.results if r["status"] == "success")
        failed = len(self.results) - success
        total_images = sum(r.get("image_count", 0) for r in self.results)

        print("\n" + "=" * 60)
        if self.aborted:
            print(f"🛑 크롤링 중단됨 — 이미지 수집 연속 실패(차단 추정)")
        else:
            print(f"크롤링 완료!")
        print(f"  성공: {success}/{len(self.results)}  (실패: {failed})")
        print(f"  총 이미지: {total_images}개")
        print(f"  소요 시간: {elapsed:.1f}초")
        print(f"  결과 경로: {output_dir}")
        print("=" * 60)

        return self.results

    def _save_results(self, query: str, output_dir: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # CSV
        csv_path = os.path.join(output_dir, f"crawl_{safe_filename(query)}_{timestamp}.csv")
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "product_id", "name", "price", "url", "page_title",
                "main_image_count", "detail_image_count", "total_images",
                "has_video", "status", "crawled_at",
                "main_image_urls", "detail_image_urls"
            ])
            for r in self.results:
                writer.writerow([
                    r.get("product_id", ""),
                    r.get("name", ""),
                    r.get("price", ""),
                    r.get("url", ""),
                    r.get("page_title", ""),
                    len(r.get("main_images", [])),
                    len(r.get("detail_images", [])),
                    r.get("image_count", 0),
                    r.get("has_video", False),
                    r.get("status", ""),
                    r.get("crawled_at", ""),
                    " | ".join(r.get("main_images", [])),
                    " | ".join(r.get("detail_images", [])),
                ])
        print(f"  CSV: {csv_path}")

        # JSON
        json_path = os.path.join(output_dir, f"crawl_{safe_filename(query)}_{timestamp}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "query": query,
                "crawled_at": datetime.now().isoformat(),
                "run_status": "blocked" if self.aborted else "completed",
                "total_products": len(self.results),
                "success_count": sum(1 for r in self.results if r["status"] == "success"),
                "fail_count": sum(1 for r in self.results if r["status"] != "success"),
                "total_images": sum(r.get("image_count", 0) for r in self.results),
                "products": self.results,
            }, f, ensure_ascii=False, indent=2)
        print(f"  JSON: {json_path}")


# ──────────────────────────────────────────────
# 파이프라인 연동용 (F1 → F3)
# ──────────────────────────────────────────────

def crawl_coupang(
    query: str,
    max_products: int = 50,
    output_dir: str = "./coupang_output",
    download: bool = True,
) -> list[dict]:
    """
    다른 모듈에서 import해서 사용.

    Usage:
        from coupang_crawler import crawl_coupang
        results = crawl_coupang("다이어트 보조제", max_products=100)
    """
    crawler = CoupangCrawler({
        "max_products": max_products,
        "download_images": download,
    })
    return crawler.run(query, output_dir)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="쿠팡 상세페이지 이미지 크롤러 (DrissionPage — 실제 브라우저)"
    )
    parser.add_argument("query", help="검색어")
    parser.add_argument("--max-products", type=int, default=50, help="최대 상품 수 (기본: 50)")
    parser.add_argument("--max-pages", type=int, default=5, help="검색 결과 최대 페이지 (기본: 5)")
    parser.add_argument("--output", default="./coupang_output", help="출력 디렉토리")
    parser.add_argument("--no-download", action="store_true", help="이미지 다운로드 안 함 (URL만)")
    parser.add_argument("--delay-min", type=float, default=3.0, help="최소 딜레이 초")
    parser.add_argument("--delay-max", type=float, default=7.0, help="최대 딜레이 초")
    parser.add_argument("--fail-streak", type=int, default=3,
                        help="이미지 수집 연속 실패가 이 횟수에 도달하면 크롤링 중단 (기본: 3)")
    parser.add_argument("--browser", choices=["auto", "chrome", "whale"], default="auto",
                        help="사용할 브라우저 (기본: auto = Whale→Chrome)")
    parser.add_argument("--manual", action="store_true",
                        help="반수동 모드: 차단 감지 시 멈추고 브라우저에서 직접 로그인/해제 후 Enter")

    args = parser.parse_args()

    crawler = CoupangCrawler({
        "max_products": args.max_products,
        "max_pages": args.max_pages,
        "download_images": not args.no_download,
        "delay_min": args.delay_min,
        "delay_max": args.delay_max,
        "fail_streak_threshold": args.fail_streak,
        "browser": args.browser,
        "manual": args.manual,
    })

    crawler.run(args.query, args.output)


if __name__ == "__main__":
    main()