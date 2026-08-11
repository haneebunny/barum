# 핸드오프: Frontend 앱 격 + 디자인 시스템 (Next.js)

> **받는 사람:** 프론트엔드 개발자 Claude
> **주는 사람:** PM
> **날짜:** 2026-08-07
> **이 문서 하나 + 아래 참조 파일만으로 착수 가능하게 작성됨.** 이 대화 맥락은 필요 없다.

---

## 0. 착수 전 반드시 읽을 것 (순서대로)

1. **`CLAUDE.md`** (repo 루트): 작업 규칙. 특히 §A(코드보다 인터뷰 먼저·안 정한 결정은 대신 정하지 말고 선택지 제시)·§B(단계별 계획 먼저, "진행" 전엔 코드 X)·**§F(디자인·색 규칙 = 구속력 있음)**.
2. **`docs/superpowers/specs/2026-08-07-frontend-skeleton-design-system.md`**: 이 작업의 **정식 스펙**. 구조·컴포넌트 계약·완료기준의 근거.
3. **`design/mockups/HANDOFF.md`**: 디자인 시스템 원본. **§3(안티-슬롭 5규칙)·§4(색각이상 검증)는 참고가 아니라 지킬 규칙.**
4. 목업 5장 실물: `design/mockups/*.html`이 토큰·컴포넌트의 **진실 소스**. 실행:
   ```bash
   cd <repo루트>
   backend/venv/bin/python3 -m http.server 4321 --directory design/mockups
   # http://localhost:4321/review-queue.html
   ```

---

## 1. 미션 (이번 컷의 범위)

barum 모노레포의 `frontend/`에 **Next.js 앱의 골격 + 디자인 시스템만** 세운다. 화면 콘텐츠·데이터·API·auth는 **이번 컷 밖**.

**할 것:**
- `frontend/`에 Next.js 스캐폴딩 (App Router · TypeScript · npm · ESLint, create-next-app 기본 관례대로).
- 검증된 디자인 토큰을 **`app/globals.css` 단일 소스**로 이식 (목업은 5파일에 토큰을 복제해 둠 → 1소스로 통합).
- 앱 셸: 상단바(브랜드 + nav + 테마 토글), 다크/라이트 테마(시스템 기본 + localStorage + **FOUC 방지 인라인 스크립트**).
- 공용 컴포넌트 이식: **StateBadge**, **EvidenceShield**.
- 5개 화면 경로를 **자리표시 스텁**으로 생성.
- **`/styleguide`** = 토큰·컴포넌트를 렌더하는 살아있는 쇼케이스(디자인 시스템 검증용).

**하지 말 것 (후속 컷, YAGNI):**
- 화면별 실제 콘텐츠/레이아웃(큐 목록·검토 상세 원문 재현·대시보드 차트·조치·점검 로직).
- mock/실데이터, 백엔드 API, Supabase 연결.
- 인증·역할(reviewer/admin) 게이팅.
- 차트 구현.
- **새 색·새 상태색·새 컴포넌트**를 임의로 추가하는 것. (필요하면 §5 참조: 멈추고 PM에게.)

## 2. 확정된 결정 (이미 정해짐, 되돌리지 말 것)

| 항목 | 결정 |
|---|---|
| 리포 | 모노레포. 이 작업은 전부 `frontend/` 안. backend(Python)는 건드리지 않음 |
| 프레임워크 | Next.js **App Router** + **TypeScript** |
| 패키지매니저 | **npm** |
| 스타일링 | **globals.css의 CSS 변수 = 토큰 단일 소스** + **Tailwind v4 (CSS-first, `@theme`로 변수 매핑) 유틸리티 우선**. CSS-in-JS·CSS Modules 미사용. (2026-08-07 PM 결정으로 기존 'Tailwind 미사용'을 번복) |
| 런타임 | **Node 22 LTS** (`frontend/.nvmrc=22`). npm 11이 node 20.11을 지원 안 해 22로 고정 |
| 아이콘 | **Phosphor** (`@phosphor-icons/react`). 손그림 SVG 금지 |
| 폰트 | **Pretendard**. 우선 CDN(목업 패리티), self-host는 후속 |
| 라우팅 | `/` = 작업 홈(**queue 스텁**), `/detail /dashboard /action /inspection` 스텁, `/styleguide` 쇼케이스. 평면 nav |
| 공개범위 | repo는 **public**. 하드코딩 secret 금지 |

## 3. 목표 디렉토리 구조

```
frontend/
├─ app/
│  ├─ layout.tsx              루트 레이아웃(AppShell 래핑, <html> 테마 속성, 폰트)
│  ├─ page.tsx                / = 작업 홈(queue 스텁)
│  ├─ globals.css             검증 :root 토큰(라이트/다크) + 리셋 + Pretendard + tabular-nums
│  ├─ theme-script.tsx        no-flash 초기 테마 주입(인라인)
│  ├─ styleguide/page.tsx     디자인 시스템 쇼케이스
│  ├─ detail/page.tsx         스텁
│  ├─ dashboard/page.tsx      스텁
│  ├─ action/page.tsx         스텁
│  └─ inspection/page.tsx     스텁
├─ components/
│  ├─ AppShell/  TopBar/  ThemeToggle/     (각 .tsx, Tailwind 유틸리티)
│  ├─ StateBadge/
│  └─ EvidenceShield/
├─ lib/                       (이번 컷 비움)
└─ (package.json · tsconfig.json · next.config.ts · eslint 설정 · public/)
```

## 4. 디자인 토큰 (진실 소스 = 목업 `:root`)

**목업 `.html`의 `:root` 블록 전체를 authoritative로 삼아 그대로 옮긴다.** 아래는 헤드라인 값(검증 완료, HANDOFF §3·§4). 목업과 불일치하면 목업이 이긴다.

- 라이트: `--canvas:#f3f5f8  --surface:#fff  --navy:#1f2d44  --accent:#12509e`
- 시맨틱: `--crit:#c0392b  --warn:#9a5b02  --ok:#1f7a44  --low:#5b6472`
- 다크: `[data-theme="dark"]`에서 재정의(`--accent:#5b9be8` 등, 목업 다크 블록 그대로).
- 차트 램프(변수로 정의만, 이번 컷 사용 안 함): 라이트 `#12509e,#5b7bb0,#a4b6d0` / 다크 `#5b9be8,#4a7099,#3c5372` (CVD 통과본).
- 전역: `font-family: Pretendard`, 숫자 `font-variant-numeric: tabular-nums`.

## 5. 🔴 구속력 있는 디자인 규칙 (어기면 반려)

HANDOFF §3.1의 안티-슬롭 5규칙 + §4 색각이상 절차:
1. **색은 '주목'에만.** 위해 고·기한 초과·미탐 등 "지금 급한 것"만 색. 나머지 상태·라벨은 회색 텍스트.
2. **왼쪽 border 굵게 금지**(`border-left:3px` 류). 강조는 사방 균일 테두리 + 헤더 태그.
3. **손그림 SVG 아이콘 금지** → Phosphor. em-dash(—) 금지 → 하이픈.
4. **상태는 색이 아니라 모양·글자로**(색각이상 대응).
5. **점수 아니라 근거.** "위험 0.94" ✗ → "확인 필요 · 근거 3건" ○.
- **앰버(`--warn`)를 심각도 색으로 쓰지 말 것** (빨강과 CVD 구분 불가). 시스템은 "빨강만 경보, 나머지 회색".
- **새 색·새 상태색을 추가하지 말 것.** 정말 필요하면 **멈추고 PM에게**: `dataviz` 스킬 + `scripts/validate_palette` 통과 + 승인 후에만. (CLAUDE.md §F·§A)

## 6. 컴포넌트 계약

- **StateBadge**: props `label: string`, `tone?: 'crit' | 'muted'`(기본 `muted`). border + 옅은 배경 + 텍스트. `crit`만 빨강, 그 외 회색. 큐·대시보드가 공유하는 컴포넌트.
- **EvidenceShield**: props `level: 'full' | 'half' | 'none'`. shield-check / shield-half(반쪽) / 빈 방패. **단색, 모양으로 구분(색 아님).** 범례는 styleguide에.
- **AppShell / TopBar / ThemeToggle**: 레이아웃·nav·테마. ThemeToggle은 달/해 아이콘, 클릭 시 `<html data-theme>` 토글 + localStorage 저장. 최초엔 시스템 설정.

## 7. 완료 기준 (Acceptance)

1. `cd frontend && npm run dev` → 앱 뜨고 콘솔 에러 0.
2. `/`(queue 스텁), `/detail /dashboard /action /inspection`(스텁), `/styleguide`(쇼케이스) 라우팅됨.
3. 테마 토글이 라이트↔다크 전환, 새로고침 후 유지, **FOUC 없음**.
4. `/styleguide`에 토큰 색 스와치 + StateBadge + EvidenceShield가 라이트·다크 양쪽 정상.
5. 안티-슬롭 셀프체크 통과: 색이 주목에만 / border-left 굵게 없음 / 라이브러리 아이콘 / 상태는 모양·글자 / 숫자 tabular / 다크 대비 AA.
6. `npm run build` 성공, `npm run lint` 통과.

## 8. 작업 방식 (CLAUDE.md 준수)

- 착수 전 **단계별 구현 계획을 먼저 제시**하고 승인받은 뒤 코드(§B). 스펙에서 안 정한 게 나오면 추측하지 말고 **멈추고 PM에게 선택지 제시**(§A).
- 커밋: repo가 **아직 git 미초기화**. 커밋하지 말고, 완료 후 PM에게 알린다(PM이 git init 시 함께 커밋).
- secret 하드코딩 금지(public repo).

## 9. PM 확인 대기 항목 (열린 것)

- 없음. 이번 컷의 결정은 모두 확정됨. 새 결정이 필요해지면 진행 말고 PM에게.

---

## 부록: 프론트 개발자 Claude에게 붙여넣을 착수 프롬프트(예시)

> barum 모노레포에서 프론트엔드 골격을 세우는 작업이야. 먼저 `docs/handoffs/2026-08-07-frontend-skeleton-handoff.md`를 읽고, 거기 §0의 참조 파일들(`CLAUDE.md`, 스펙, `design/mockups/HANDOFF.md`, 목업 html)을 확인해. 그런 다음 CLAUDE.md §B대로 단계별 구현 계획을 나에게 먼저 제시하고, 승인 전엔 코드를 쓰지 마.
