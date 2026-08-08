# 스펙: Frontend 앱 격 + 디자인 시스템 (Next.js)

- **작성일:** 2026-08-07
- **범위:** vericops 모노레포 `frontend/`에 Next.js 앱의 **골격 + 디자인 시스템**만 구축. 화면 콘텐츠·데이터·API는 후속.
- **근거 문서:** `design/mockups/HANDOFF.md`(디자인 시스템·구속 규칙), `PROJECT.md`(reviewer/admin·닫힌 순환), `CLAUDE.md` §F(디자인 규칙).

---

## 1. 목표 / 비목표

**목표 (이번 컷):**
- `frontend/`에 Next.js(App Router + TypeScript, npm) 스캐폴딩.
- 검증된 디자인 토큰을 **globals.css 단일 소스**로 이식(목업의 5파일 복제 → 1소스).
- 앱 셸: 상단바(브랜드 + nav + 테마 토글), 다크/라이트 테마(시스템 기본 + localStorage + no-flash).
- 확립된 공용 컴포넌트 이식: StateBadge, EvidenceShield.
- 5개 화면 경로를 **자리표시 스텁**으로 생성.
- `/styleguide` = 토큰·컴포넌트를 렌더하는 살아있는 쇼케이스(디자인 시스템 검증).

**비목표 (후속 컷):**
- 화면별 실제 콘텐츠/레이아웃(큐 목록·검토 상세 원문 재현·대시보드 차트·조치·점검 로직).
- mock/실데이터, 백엔드 API, Supabase 연결.
- 인증·역할(reviewer/admin) 게이팅.
- 차트 구현.

## 2. 스택 / 관례

- Next.js **App Router**, **TypeScript**, **npm**, ESLint. create-next-app 기본 관례 준수(최대한 관례대로).
- 아이콘: **Phosphor** (`@phosphor-icons/react`). HANDOFF §3.3 "라이브러리 아이콘".
- 폰트: **Pretendard**. 우선 CDN(목업 패리티), self-host는 후속.
- 스타일: **globals.css의 CSS 변수 = 토큰 단일 소스** + **Tailwind v4 (CSS-first, `@theme`로 변수 매핑) 유틸리티 우선**. CSS-in-JS·CSS Modules 미사용. (2026-08-07 PM 결정으로 기존 'Tailwind 미사용' 번복.)
- 런타임: **Node 22 LTS** (`frontend/.nvmrc=22`).

## 3. 디렉토리 구조

```
frontend/
├─ app/
│  ├─ layout.tsx              루트 레이아웃(AppShell 래핑, <html> 테마 속성)
│  ├─ page.tsx                / = 작업 홈(queue 스텁)
│  ├─ globals.css             검증된 :root 토큰(라이트/다크) + 리셋 + Pretendard + tabular-nums
│  ├─ theme-script.tsx        no-flash 초기 테마 주입(인라인)
│  ├─ styleguide/page.tsx     디자인 시스템 쇼케이스
│  ├─ detail/page.tsx         스텁
│  ├─ dashboard/page.tsx      스텁
│  ├─ action/page.tsx         스텁
│  └─ inspection/page.tsx     스텁
├─ components/
│  ├─ AppShell/               (AppShell.tsx, Tailwind 유틸리티)
│  ├─ TopBar/
│  ├─ ThemeToggle/            달/해 토글, localStorage 영속
│  ├─ StateBadge/             border+옅은배경+텍스트, 경보(고)만 색
│  └─ EvidenceShield/         shield-check / shield-half / 빈 방패 (단색·모양 구분)
├─ lib/                       (이번 컷 비움, 후속 API 클라이언트)
├─ public/
├─ package.json · tsconfig.json · next.config.ts · .eslintrc · .gitignore
```

## 4. 디자인 토큰 (globals.css, HANDOFF §3·§4에서 그대로)

- 라이트: `--canvas:#f3f5f8 --surface:#fff --navy:#1f2d44 --accent:#12509e`
- 시맨틱: `--crit:#c0392b --warn:#9a5b02 --ok:#1f7a44 --low:#5b6472`
- 다크: `[data-theme="dark"]`에서 재정의(`--accent:#5b9be8` 등).
- 차트 램프(참고용 변수로 정의): 라이트 `#12509e,#5b7bb0,#a4b6d0` / 다크 `#5b9be8,#4a7099,#3c5372` (CVD 검증 통과본).
- 전역: `font-family: Pretendard`, 숫자 `font-variant-numeric: tabular-nums`.
- **규칙:** 새 색·새 상태색 추가 금지(이번 컷). 필요 시 `dataviz` + `scripts/validate_palette` 통과 후, 승인받고 추가.

## 5. 테마 시스템

- 최초 렌더 전 인라인 스크립트로 `localStorage.theme` 또는 시스템(`prefers-color-scheme`) 값을 `<html data-theme>`에 주입 → **FOUC 방지**.
- ThemeToggle: 클릭 시 `data-theme` 토글 + localStorage 저장. 아이콘 달/해.

## 6. 컴포넌트 계약 (이번 컷)

- **StateBadge**: props `label`, `tone: 'crit' | 'muted'`(기본 muted). 경보(위해 고 등)만 `crit` 색, 그 외 회색. HANDOFF: "색은 주목에만".
- **EvidenceShield**: props `level: 'full' | 'half' | 'none'`. shield-check / shield-half / 빈 방패. 단색, 모양으로 구분(색 아님). 범례는 styleguide에 표시.
- **AppShell/TopBar/ThemeToggle**: 레이아웃·네비·테마. nav = 5경로 링크(평면). `/styleguide`는 개발/참고 링크.

## 7. 완료 기준 (Acceptance)

1. `cd frontend && npm run dev`로 앱이 뜨고 콘솔 에러 0.
2. `/` = queue 스텁, `/detail /dashboard /action /inspection` 스텁, `/styleguide` 쇼케이스가 라우팅됨.
3. 테마 토글이 라이트/다크 전환하고 새로고침 후에도 유지(FOUC 없음).
4. `/styleguide`에 토큰 색 스와치 + StateBadge + EvidenceShield가 라이트/다크 양쪽에서 정상.
5. 디자인 규칙 셀프체크 통과: 색이 주목에만 / border-left 굵게 없음 / 라이브러리 아이콘 / 상태는 모양·글자 / 숫자 tabular / 다크 대비 AA.
6. `npm run build` 성공, `npm run lint` 통과.

## 8. 리스크 / 메모

- Pretendard CDN 의존 → 후속 self-host(next/font 또는 `pretendard` 패키지).
- 토큰을 CSS 변수로 두면 TS 자동완성은 없음. 이번 컷 범위상 수용.
- git 미초기화 상태 → 이 스펙·frontend는 git init 시 함께 커밋.
