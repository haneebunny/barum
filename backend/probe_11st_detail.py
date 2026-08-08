"""
11번가 상세 페이지 네트워크 프로브 (Plan B 탐색)
- 상세 페이지를 열고 모든 네트워크 요청을 로깅
- 상세 마케팅 이미지를 주는 API/CDN 경로를 식별
- 부수적으로 렌더된 긴 이미지 URL도 수집 (Plan A 대비)
사용: ./venv/bin/python probe_11st_detail.py <prdNo>
"""
import sys, json, re
from playwright.sync_api import sync_playwright

PRD = sys.argv[1] if len(sys.argv) > 1 else "3458162245"
URL = f"https://www.11st.co.kr/products/{PRD}"

img_reqs = []      # 이미지 응답 (url, type, size)
data_reqs = []     # xhr/fetch/document 응답 (url, type, status, img_hit)

def on_response(resp):
    try:
        req = resp.request
        rtype = req.resource_type
        url = resp.url
        ct = (resp.headers or {}).get("content-type", "")
        if rtype == "image" or re.search(r"\.(jpg|jpeg|png|gif|webp)(\?|$)", url, re.I):
            clen = (resp.headers or {}).get("content-length", "")
            img_reqs.append((url, ct, clen))
        elif rtype in ("xhr", "fetch", "document"):
            body_img_hits = 0
            snippet = ""
            if "json" in ct or "html" in ct or "text" in ct:
                try:
                    body = resp.text()
                    # 본문에 상품 상세 이미지로 보이는 CDN URL이 몇 개 들어있나
                    hits = re.findall(r'https?://[^"\'\\ ]*011st[^"\'\\ ]*\.(?:jpg|jpeg|png|webp)', body, re.I)
                    body_img_hits = len(hits)
                    if body_img_hits:
                        snippet = hits[0][:120]
                except Exception:
                    pass
            data_reqs.append((url, rtype, resp.status, ct[:30], body_img_hits, snippet))
    except Exception:
        pass

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        viewport={"width": 1280, "height": 900},
    )
    page = ctx.new_page()
    page.on("response", on_response)
    print(f"[navigate] {URL}")
    page.goto(URL, wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(2500)
    # 상세영역 로드 유도: 여러 번 스크롤
    for i in range(12):
        page.mouse.wheel(0, 2000)
        page.wait_for_timeout(700)
    page.wait_for_timeout(2000)

    # 렌더된 img 중 세로로 긴(상세로 보이는) 것 수집
    rendered = page.eval_on_selector_all(
        "img",
        """els => els.map(e => ({src: e.currentSrc || e.src, w: e.naturalWidth, h: e.naturalHeight}))
                    .filter(o => o.src && o.h > 0)"""
    )
    # iframe src 목록 (상세설명이 iframe인 경우)
    iframes = page.eval_on_selector_all("iframe", "els => els.map(e => e.src).filter(Boolean)")
    # iframe 내부 img까지 수집
    iframe_imgs = []
    for fr in page.frames:
        if fr == page.main_frame:
            continue
        try:
            fi = fr.eval_on_selector_all(
                "img",
                """els => els.map(e => ({src:e.currentSrc||e.src, w:e.naturalWidth, h:e.naturalHeight})).filter(o=>o.src&&o.h>0)"""
            )
            for o in fi:
                o["frame"] = fr.url[:80]
            iframe_imgs.extend(fi)
        except Exception:
            pass
    browser.close()

print("\n================ products/view/pc/<섹션> 전체 목록 ================")
sections = sorted(set(re.sub(r".*/products/view/pc/([^/]+)/.*", r"\1", u)
                     for u,_,_,_,_,_ in data_reqs if "/products/view/pc/" in u))
for s in sections:
    print("  ", s)

print("\n================ iframe src (상세설명 iframe 후보) ================")
for f in iframes:
    print("  ", f[:130])
print(f"  iframe 내부 img {len(iframe_imgs)}개")

print("\n================ esmplus / 11src/dl (셀러 상세이미지 후보) 실측 ================")
det = [o for o in (rendered + iframe_imgs)
       if re.search(r"esmplus|/11src/dl/|/11src/pd/", o["src"], re.I)]
seen=set()
for o in det:
    k=o["src"].split("?")[0]
    if k in seen: continue
    seen.add(k)
    fr = o.get("frame","main")
    print(f"  {o['w']}x{o['h']}  {o['src'][:100]}  [{fr}]")
print(f"  → 상세이미지 후보 {len(seen)}개")

# ---- 리포트 ----
print("\n================ [B] 상세 이미지를 '본문에 담아 주는' 응답 (API 후보) ================")
api_candidates = [d for d in data_reqs if d[4] > 0]
api_candidates.sort(key=lambda d: -d[4])
for url, rtype, status, ct, hits, snip in api_candidates[:15]:
    print(f"  img{hits:>3}개 | {rtype:8} {status} | {ct}")
    print(f"        URL: {url[:130]}")
    if snip:
        print(f"        예시이미지: {snip}")
if not api_candidates:
    print("  (본문에 상세 이미지 URL을 담은 xhr/fetch/document 응답 없음)")

print("\n================ [A] 렌더된 img 중 세로 긴 상세 후보 (h/w>1.8, 폭>=500) ================")
tall = [o for o in rendered if o["w"] >= 500 and o["h"]/max(o["w"],1) >= 1.8]
# 중복 제거
seen=set(); uniq=[]
for o in tall:
    k=o["src"].split("?")[0]
    if k in seen: continue
    seen.add(k); uniq.append(o)
for o in uniq[:20]:
    print(f"  {o['w']}x{o['h']} (비율{o['h']/o['w']:.1f})  {o['src'][:110]}")
print(f"  → 세로 긴 상세이미지 후보 {len(uniq)}개")

print("\n================ 이미지 CDN 호스트 분포 (상위) ================")
from collections import Counter
hosts = Counter(re.sub(r"https?://([^/]+)/.*", r"\1", u) for u,_,_ in img_reqs)
for h,c in hosts.most_common(10):
    print(f"  {c:>4}  {h}")
print(f"\n총 이미지 요청 {len(img_reqs)}건, 데이터 요청 {len(data_reqs)}건")
