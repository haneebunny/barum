# barum 프론트 목업 핸드오프 (다음: 리포트 화면)

> 새 세션이 이걸 읽고 **리포트 화면**부터 이어서 만든다. 착수 전 계획을 하니에게 보여주고 승인받는다(CLAUDE.md 규칙).

## 0. 필독 순서
1. `design/mockups/barum-DESIGN.md` = 규칙 마스터(검증 절차·팔레트·타입·그린규칙·IA·입력계약·리포트 필드). **먼저 통독.**
2. 이 파일(현재 상태 + 다음 태스크).
3. `backend/src/barum/models.py` = 백엔드 `CheckReport` 스키마(아래 §4에 발췌). 리포트는 여기 1:1.
4. `reference/violation_types`, `reference/statute` = 위반유형·조항 도메인 정의(근거·대체표현 정확도용).

## 1. 프로젝트
- **barum(바름)**: 셀러(화장품 브랜드)용 규제 사전검수 SaaS. 셀프서비스. (식약처 내부용 네이비 KRDS는 폐기)
- 경로 `/Users/hani/Desktop/project/barum` · GitHub `haneebunny/barum`(**public**) · 브랜치 `v1.4-pivot`.
- 비주얼: 터미널/로그 + 그린-블랙, 시원한 워크벤치 배경(패널 부양), 전부 샤프(radius 0). 라이트 기본.

## 2. 지금까지 만든 것 (design/mockups/)
- `barum.html` — **홈**. 2입구(국내/해외 검증), 사이드바 아이콘레일 접기, 시원한 배경, 깜빡 커서, ZEN SERIF 로고(SVG 인라인), 대상국 모노 모달.
- `barum-inspect.html` — **검수**. 문구 textarea(일급) + 이미지 드롭존 공존, 검수 지시(mono)와 분리, 실시간 verify 로그 스트림(입력종류 분기: 문구만이면 OCR 스킵). "검수 결과 보기 →"(id `toReport`)는 아직 no-op → **리포트로 연결할 자리**.
- `barum-logo.svg` — "바름" 아웃라인 워드마크(폰트 아니라 아트워크 → 커밋 OK, currentColor 테마).
- `barum-DESIGN.md` — 규칙 마스터.
- `fonts/ZEN-SERIF-TTF-Regular.ttf` — 로고 원본 폰트. **재배포 금지 → gitignore(로컬 프리뷰 전용).** 로고는 SVG로 이미 repo에 있으니 팀원은 폰트 없어도 로고 보임.
- `_fontcompare.html` — 폰트 비교(임시, 무시/삭제 가능).
- **폐기(참고 금지)**: `HANDOFF.md`, `action.html`, `dashboard.html`, `inspection.html`, `review-*.html` = 옛 네이비 KRDS.

## 3. 다음 태스크: 리포트 화면 (`barum-report.html` 신규)
홈과 같은 셸(로고·사이드바·테마·쿨배경) 재사용. 구성:
1. **위험 요약 stat** — `summary` 매핑: 위반 `n_findings`, 유형별 `counts_by_type`, **미판정 `n_unjudged`(별도 표시)**, region. 종합 Grade는 프론트 파생(백엔드엔 없음).
2. **원문 하이라이트 2모드** (2026-08-11 결정)
   - **문구 입력**: 붙여넣은 텍스트에서 `sentence` 찾아 `span`에 빨간 밑줄+번호. 정밀 하이라이트 됨(좌표 문제 없음).
   - **이미지 입력**: 문장 단위 정밀 하이라이트는 **안 한다**(OCR이 글자 좌표를 안 줌). 대신 **원본 이미지 위에 구간(띠) 단위**로 "이 구간이 문제"를 번호와 함께 표시. 문장이 아니라 밴드 정밀도임을 감안.
   - ⚠ **블로커**: 밴드를 그리려면 `Location`에 좌표(`y_start`/`y_end`/`source_h`/`source_w`, 원본 대비 비율)가 추가돼야 한다. **지금 `models.py`엔 아직 없다**(`tile`/`order`만). 백엔드에 이 확장을 요청해둘 예정 — 붙기 전까진 이미지 모드는 옆 카드 목록(번호만)으로 임시 대응하고, 좌표 오면 밴드로 교체.
3. **지적 카드(Finding 1:1)** — `span`(지목 표현) · `sentence`(원문 문장) · `violation_type`(한글 라벨) · `legal_basis`(근거 조항 문자열) · `risk`(고/중/저) · `explanation`(설명).
   - **대체표현(2026-08-11 결정, 기획서 v1.7 FR-14 반영)**: 카드 하단에 "대체표현" 슬롯을 **자리만 먼저** 만든다(A안). 이유: v1.3에선 "대체표현 없음(법적 리스크)"이었지만 v1.7에서 **FR-14 수정 권고안**으로 정식 승격됨(우선순위 상, "위반 문구 100%에 권고안 제시"가 KPI). 단 지금은 백엔드 `Finding`에 필드가 없다(규칙집 완성 후 착수, 엔진 안정화 뒷단 일정). 목업은 **더미 문구**로 채우되 실제 API 필드명(`alternative` 예정, 확정 아님)이 오기 전까지는 no-op.
   - **반드시 넣을 가드레일 3종** (v1.7 FR-14 제약, 법적 책임 조항과 직결): ① 대체표현 옆에 **"권고안(확정 문구 아님)"** 고지 — 색 아니라 글자로. ② **조건표 기반**임을 암시(효능을 새로 만든 게 아니라 안전 표기 틀 안에서 골랐다는 톤). ③ **효능 창작 아님** — 원문에 없던 효능 주장을 대체표현이 새로 만들면 안 됨(더미 작성 시에도 이 규칙 지켜서 작성).
   - 수용/제외/보류 액션은 그대로 유지(사람이 최종 확정, 서비스 흐름과 일치).
4. **미판정 문장(UnjudgedSentence)** — VLM 실패로 못 가린 문장. recall 우선이라 존재. **"미판정 N건 · 확인 필요"로 반드시 노출, 그린/통과로 숨기지 말 것.**
5. **하단 브릿지** — "이 수정안대로 상세페이지 만들기 →" = 초안 생성 진입(초안 화면은 그다음).
6. `barum-inspect.html`의 "검수 결과 보기 →"를 `barum-report.html`로 연결.

⚠ 착수 전 `backend/src/barum/models.py`를 다시 열어 필드명·enum을 그대로 쓴다(아래는 발췌라 최신 아닐 수 있음).

## 4. 백엔드 CheckReport 스키마 (backend/src/barum/models.py 발췌)
```
ViolationType(str,Enum):
  legal="합법"
  type_1_drug_misperception="1호_의약품오인"
  type_2_functional_misperception="2호_기능성오인"
  type_5_deception="5호_거짓과장기만"     # 개정법 기준(현행 4호). 2026.11.27 AI조항 신설로 5호로 밀림
  out_of_scope="대상외"          # 3호는 삭제 조항이라 없음

RiskLevel(str,Enum): high="고"  medium="중"  low="저"
Region(str,Enum): KR="KR"  US="US"

Location: { tile: str|None, order: int }        # 이미지 타일/순서
Finding: { span, sentence, violation_type, legal_basis, risk, explanation, location }
UnjudgedSentence: { sentence, location }         # 판정 실패 문장
Summary: { region, n_sentences, n_findings, n_unjudged, counts_by_type: {유형:건수} }
CheckReport: { findings: [Finding], unjudged: [UnjudgedSentence], summary: Summary }
```

## 5. 반드시 지킬 규칙 (요약, 상세는 barum-DESIGN.md)
- **검증 매번**: 색·대비·CVD 눈 판단 금지 → `contrast.mjs`(대비 4.5:1)·dataviz `validate_palette.js`(그린↔빨강 deutan≥8) 실행. **em-dash 금지**.
- **타입 분리**: Pretendard(사람: 제목·본문·설명·원문·span) / JetBrains Mono(기계: 로그·수치·태그·조항코드·상태바).
- **색**: **그린 = 브랜드·터미널·액션 전용, 합격/안전 신호 금지(CVD).** **빨강 = 위험만.** 위험도 매핑: **고=빨강, 중·저=회색**(앰버 금지). 상태·통과는 색 아니라 글자+아이콘.
- 기본 라이트(키 `barum-theme`), 사이드바 레일(키 `barum-nav`). 시원한 배경, 패널 부양, radius 0. 모달=모노 터미널 다이얼로그.
- 스킬: frontend-design(비주얼) · taste-skill(안티슬롭만, 랜딩 히어로 규칙은 무시) · dataviz(차트·심각도색·필수) · ui-ux-pro-max(스타일/색/폰트 탐색). **잠긴 방향(터미널 그린) 우선**, DB추천 중 글래스모피즘·전면모노·다크기본은 오버라이드.

## 6. 실행/프리뷰 (macOS TCC 주의)
- `preview_start`(MCP)는 `~/Desktop` TCC로 막힘. **백그라운드 Bash로 서버**:
  ```bash
  /usr/bin/python3 -m http.server 4321 --directory /Users/hani/Desktop/project/barum/design/mockups
  ```
  그다음 브라우저 MCP로 `http://localhost:4321/barum-report.html` 등 열어 확인.
- 검증: 콘솔 에러 0, 라이트+다크 둘 다, em-dash 0, 새 색은 대비·CVD 통과.

## 7. 열린 결정 (하니)
- 로고 마크 글자: 지금 임시 "바". 파비콘·마크 이미지는 하니가 직접 제작 예정.
- ~~CheckReport enum 라벨을 UI에 그대로 노출할지~~ → **결정(2026-08-11): C안.** "호수 + 짧은 라벨 병기"(예: `1호_의약품오인` → "1호 · 의약품 오인"). 언더스코어만 걷고 호수는 유지 — 법 개정으로 호수가 바뀔 수 있어(오늘 4→5호처럼) 추적성 유지 목적. 프론트에 가벼운 매핑 상수 필요. `counts_by_type`도 동일 규칙.
- (참고) 기획서 **v1.7**로 개정됨(`~/Downloads/2조_최종프로젝트_기획서_v1.7.docx`). 화면이 3개→**4개**(+콘텐츠 생성, FR-11/13)로 늘었고 서비스 흐름이 "탐지→근거→수정→생성"으로 재구조화. 리포트 화면 자체엔 이번 컷 영향 없지만, 다음 화면(콘텐츠 생성) 착수 전엔 v1.7 통독 필요.
