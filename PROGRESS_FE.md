# PROGRESS_FE: 바름 프론트엔드 진행상황

> 성격: 프론트엔드 세션 진행 기록(가변). 확정 결정은 `PROJECT.md`, 전체 로드맵은 `ROADMAP.md`, 작업 규칙은 `CLAUDE.md`.
> 갱신일: 2026-08-12. 담당: 프론트엔드 세션(안티그래비티).

---

## 2026-08-12 · [Micro-step 10] 리포트 화면 지적 카드 및 액션 구현 완료

### 무엇
- [ReportClient.tsx](file:///c:/dev/barum/frontend/app/report/%5Bid%5D/ReportClient.tsx)에 지적 카드 목록 동적 렌더링을 구현하고, `@phosphor-icons/react` 아이콘 및 텍스트 조합을 활용하여 디자인 규격(삼중 경보 신호)을 준수했습니다.
- 지적 카드의 "수용", "제외", "보류" 액션을 상태 관리에 연동하였으며, "제외" 처리 시 헤더의 위반 카운트 및 유형별 칩 개수가 실시간으로 재계산되어 업데이트되도록 수치 연동을 완료했습니다.
- 미판정 데이터가 존재할 시 알파벳 기호 배지와 함께 노출되는 "재검사 필요" 섹션을 하단에 구현했습니다.
- Windows 로컬 preflight 테스트(pytest 182건 전부 통과)를 완료했습니다.

---

## 2026-08-12 · [Micro-step 2] 홈 화면(HomePage) 정적 레이아웃 이식 완료

### 무엇
- `barum.html` 목업을 기반으로 홈 화면의 정적 마크업을 [page.tsx](file:///c:/dev/barum/frontend/app/page.tsx)에 완벽히 이식하였습니다.
  - 미확인 알림 바(`needbar`), 히어로 영역, 국내/해외 2입구 카드, 최근 프로젝트 목록, 하단 컴플라이언스 및 상태바 마크업 이식.
  - 대상국 선택 모달(`regionModal`)은 `hidden` 상태로 마크업만 배치 완료. (상태 제어는 Micro-step 3에서 추가 예정)
- [globals.css](file:///c:/dev/barum/frontend/app/globals.css) 하단에 홈 화면 전용 CSS 스타일 및 모바일 반응형 미디어 쿼리를 이식하였습니다.
- 로컬 PC 환경에 대응하여 PATH 환경 변수를 갱신하고 `npm run lint` 및 `npm run build` 검증(Turbopack)을 성공적으로 마쳤습니다.
- Windows 환경에서의 preflight 실행 호환성을 위해 [preflight.py](file:///c:/dev/barum/scripts/preflight.py)의 `cp949` 유니코드 인코딩 크래시 오류(em-dash)를 수정하였으며, 최종 preflight 빌드 및 테스트 패스를 확인하였습니다.

---

## 2026-08-12 · [Micro-step 1] AppShell 사이드바 내비게이션 활성화 완료

### 무엇
- [AppShell.tsx](file:///c:/dev/barum/frontend/components/AppShell/AppShell.tsx) 사이드바 내비게이션 메뉴에 마이페이지 (`/mypage`) 항목을 추가하였습니다.
- 목업 파일에 사용된 프로필/유저 형태의 SVG 아이콘과 라벨을 활성화하고, 현재 경로가 `/mypage`일 때 활성화 스타일(`on`)이 적용되도록 연동하였습니다.
- 브랜드 아이덴티티(BI)가 수립되지 않은 임시 레이아웃 상태로 뼈대를 선구축하였습니다.

---

## 2026-08-12 · 안티그래비티 연동 세팅 + 진행기록 분리

### 무엇
프론트엔드 개발을 안티그래비티(Antigravity)에서 진행하기로 하면서, 이 파일(`PROGRESS_FE.md`)을 새로 만들어
프론트 세션 기록을 백엔드(`PROGRESS_BE.md`)와 분리했다. `ROADMAP.md`는 하니 소관 팀 공용 문서라 이 세션에서
건드리지 않는다.

### 문제: 안티그래비티가 작업 규칙을 자동으로 못 읽음
안티그래비티는 프로젝트 루트의 `AGENTS.md`를 자동으로 읽는다(Claude Code의 `CLAUDE.md`와 같은 위치의
자동로드 파일, `@파일명` import 문법 지원). 그런데:
- 이 프로젝트의 실제 작업 규칙(착수 시 인터뷰 우선·코드 취향·디자인 안티슬롭 규칙)은 `CLAUDE.md`에 있고,
  `CLAUDE.md`는 Claude Code 전용 자동로드 파일명이라 안티그래비티는 그 존재를 모른다.
- `.claude/`(`launch.json`, `commands/interview.md`)는 Claude Code 전용 설정이라 안티그래비티가 못 읽는다.
  다만 `commands/interview.md`(인터뷰 우선 슬래시커맨드)는 내용이 `CLAUDE.md` §A와 중복이고,
  `launch.json`은 Claude Code 프리뷰 전용 dev서버 설정이라 안티그래비티엔 해당 없음(자체 실행 방식 사용).
  → 둘 다 별도 이관 불필요.

**조치**: 루트 `AGENTS.md`에 `@CLAUDE.md` import 한 줄을 추가해, `AGENTS.md`만 자동으로 읽는 툴(안티그래비티)도
`CLAUDE.md`의 작업 규칙을 같이 로드하게 함. `AGENTS.md`의 Git 협업 규칙 스코프 자체는 안 건드리고,
import 옆에 목적을 명시하는 인용구만 추가함.

### 확인 안 된 것 (다음 세션이 검증)
- 안티그래비티가 실제로 `AGENTS.md`의 `@CLAUDE.md`를 로드해서 규칙을 지키는지 아직 실기 검증 안 함
  (문서상 지원 확인만 함). 첫 안티그래비티 세션에서 "CLAUDE.md 규칙 알고 있어?" 등으로 로드 여부부터 확인할 것.
- `design/mockups/barum-report.html`, `barum-mypage.html`이 이미 존재하는데(오늘 반영), `ROADMAP.md`는 아직
  "리포트 화면 파일 자체가 없음"으로 돼 있어 최신 상태와 어긋남. 이 세션은 `ROADMAP.md`를 안 건드리므로
  갱신은 하니 확인 후 별도 처리.

### 다음
- 안티그래비티에서 실제 프론트 작업 착수 전, `CLAUDE.md` §A(착수 규칙)대로 인터뷰부터 한다.
- 디자인 작업 착수 시 `design/mockups/DESIGN.md`(규칙 마스터)·`design/mockups/HANDOFF.md` §3(안티슬롭 5규칙)·
  §4(색각이상 검증 절차) 먼저 확인한다(CLAUDE.md §F).
