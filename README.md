# barum

이커머스 상품 상세페이지의 **과대·부당광고**(식약처 「식품 표시·광고법」 위반)를 **VLM + 자체 DL**로 판정하는 에이전트. 첫 vertical = 다이어트 보조제.

> 단발 탐지가 아니라 **닫힌 순환**(탐지→검토→조치→추적→재학습). 판단은 사람, 순환·개선·행동은 에이전트.

## 모노레포 구조

```
barum/
├─ backend/        Python. 크롤·전처리(OCR·타일분할)·VLM 라벨러·DL 코어(예정)·API(예정)
│  ├─ src/barum/    얇은 패키지 (vlm, preprocess/, judge/)
│  ├─ scripts/         실행 스크립트 (run_ocr, run_prescreen, build_goldset, build_holdout, validate_holdout)
│  ├─ tests/           순수 로직 유닛테스트 (pytest)
│  ├─ legacy/          폐기 스크립트 보관
│  ├─ schema.sql       Supabase Postgres 스키마 (7테이블 + current_labels 뷰)
│  └─ requirements.txt
├─ frontend/       Next.js 웹 (reviewer/admin, 예정)
├─ reference/      식품 표시·광고 규제 레퍼런스 (법령·위반유형·사례). 판정 근거
├─ design/         목업·디자인 핸드오프
└─ docs/           명세·도메인 문서 (라벨링 기준서·판정카드 등)
```

거버넌스 문서: [PROJECT.md](PROJECT.md)(정의·아키텍처·확정 결정) · [ROADMAP.md](ROADMAP.md)(진행·할 일·데이터 현황) · [CLAUDE.md](CLAUDE.md)(작업 규칙).

## 개발 셋업 (backend)

```bash
cd backend
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 키 채우기 (GOOGLE_API_KEY, ELEVENTH_ST_API_KEY)
```

스크립트는 `backend/`에서 실행한다(상대경로로 `data/`·`11st_output/` 참조).

## 데이터 정책

크롤한 상세이미지·OCR 데이터·라벨은 **git에 두지 않는다**(`.gitignore`). 운영·학습 데이터는 Supabase, raw 이미지는 파일시스템/오브젝트 스토리지. 연구목적 소량 수집(crawl-delay ≥ 1s), 개인정보 미수집.
