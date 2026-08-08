# frontend — vericops 웹 (Next.js)

식약처 사이버조사팀 허위·과대광고 사후 모니터링 콘솔의 실무자 UI(reviewer/admin).
이번 컷은 **앱 골격 + 디자인 시스템**만 세운 상태다. 화면별 실제 콘텐츠·데이터·API·auth는 후속 컷.

- 디자인 진실 소스: 루트 [`design/mockups/`](../design/mockups/) 5장. 토큰은 `app/globals.css` 단일 소스로 통합됨.
- 백엔드 API: [`../backend/`](../backend/) (Python/FastAPI 예정).

## 스택

- Next.js 16 App Router · TypeScript · **Node 22 LTS**(`.nvmrc`).
- 스타일: `app/globals.css`의 CSS 변수 = 토큰 단일 소스 + **Tailwind v4(CSS-first) 유틸리티**.
- 다크/라이트: `<html data-theme>` + localStorage + FOUC 방지 인라인 스크립트(`app/theme-script.tsx`).
- 아이콘: Phosphor(`@phosphor-icons/react`). 폰트: Pretendard(CDN).

## 실행

```bash
nvm use          # Node 22
npm run dev      # http://localhost:3000
```

- `/` 검토 큐 · `/detail` · `/dashboard` · `/action` · `/inspection` (스텁)
- `/styleguide` 디자인 시스템 쇼케이스(토큰 스와치 · StateBadge · EvidenceShield)

## 디자인 규칙 (구속력, 어기면 반려)

`design/mockups/HANDOFF.md` §3·§4를 따른다. 요지:

1. 색은 '주목'에만. 빨강만 경보, 나머지는 회색.
2. border-left 굵게 강조 금지. 사방 균일 테두리.
3. 라이브러리 아이콘(Phosphor)만. em-dash 금지.
4. 상태는 색이 아니라 모양·글자로(색각이상 대응).
5. 새 색·새 상태색 추가 금지. 필요하면 멈추고 PM 승인 + `scripts/validate_palette` 통과.
