# barum 디자인 마스터 (매 디자인 세션 필참)

> **이 문서 하나면 스킬을 안 켜도 이어서 디자인할 수 있다.** 스킬이 있으면 §2 "적재적소"대로 켜서 쓴다.
> **색·대비·CVD·em-dash는 눈으로 판단하지 않는다. 매번 §3의 검증기를 실제로 돌려 통과한 값만 쓴다.**
> 대상: `design/mockups/barum.html` (신 방향). 옛 네이비 KRDS 5장은 폐기.

---

## 0. 절대 원칙 (CLAUDE.md 재확인)

1. 색·대비·CVD는 검증기(스크립트)로 통과시킨 값만 커밋. 눈 판단 금지.
2. 새 색·상태색·컴포넌트, 또는 이 문서에서 벗어나는 예외가 필요하면 **혼자 정하지 말고 멈춰서 선택지 제시 후 승인**.
3. em-dash(—) 금지. 채팅·문서·주석·커밋 전부. 대체는 하이픈(-)·가운뎃점(·)·줄바꿈.

---

## 1. 확정 방향 (되돌리지 말 것)

- **제품:** 셀러(화장품 브랜드)용 규제 사전검수 SaaS. 셀프서비스. (식약처 내부용 네이비 KRDS 톤은 폐기)
- **비주얼:** 터미널/로그 감성 + 그린-블랙. 전부 샤프(radius 0).
- **타이포 분리 (가독성 핵심 규칙):**
  - 사람 계층 = **Pretendard** (한글 제목·본문·판단이유·광고 원문·버튼)
  - 기계 계층 = **JetBrains Mono** (로그·타임스탬프·수치·태그·코드·상태바·`01/02` 번호)
  - "터미널이니까 전부 모노"는 **금지** (그게 가독성 문제의 원인). 숫자는 tabular.
- **기본 테마 light.** 시스템 다크 자동추종 안 함. 다크는 토글(localStorage 키 `barum-theme`, `s||'light'`).
- **심각도/상태 표현:**
  - 색은 "지금 급한 것"에만. **빨강 = 위반·검토 필요.** 통과 = 그린. 나머지 상태(작성중 등) = 회색.
  - **그린·빨강은 색 단독으로 구분시키지 않는다. 항상 색 + 아이콘 모양 + 글자 라벨 삼중.** (색만 금지, 아이콘만도 부족 = 셋 다)
  - 상태 아이콘 모양: 통과=체크 / 위반·검토필요=경고삼각 / 작성중=연필.
- **정보 구조(IA):** 홈은 **국내 검증 / 해외 수출 검증 2입구**만. 출시 전/후는 사용자에게 **묻지 않고** 시스템이 내부 처리(올린 자료로 판단). 사용자 입력은 최소(이미지·문구·제품정보, 해외는 +대상국). **초안 생성(수정안대로 상세페이지 만들기)은 리포트 뒤 선택 액션**으로 둔다. 되돌려서 출시전/후를 다시 묻지 말 것.

---

## 2. 스킬 적재적소 (있으면 켜고, 없으면 이 문서로 대체)

| 상황 | 켤 스킬 | 쓰는 법 / 주의 |
|---|---|---|
| 새 화면·비주얼 방향·타이포·레이아웃 설계 | **frontend-design** | 안티-디폴트. 시그니처 요소 하나에 힘, 나머지는 절제. |
| AI-tell 점검 (마감 전) | **taste-skill** | 이건 랜딩용이라 제품 UI엔 **히어로 규칙 등은 무시**. em-dash·손그림아이콘·장식·색 규율만 취함. |
| 차트·심각도색·stat 타일·색 만들거나 바꾸기 전 | **dataviz** (필수) | `validate_palette.js`로 CVD 검증. §3.2. |
| 스타일·팔레트·폰트페어링·차트·스택 탐색 | **ui-ux-pro-max** | `python3 .claude/skills/ui-ux-pro-max/scripts/search.py "<쿼리>" --design-system`. **단 잠긴 방향(터미널 그린) 우선.** DB 추천 중 글래스모피즘·앰비언트블롭·전면모노·다크기본은 이 프로젝트에선 오버라이드. |

---

## 3. 매번 돌리는 검증 (커밋 전 필수) ← "검증은 매번 확인"

### 3.1 대비 (WCAG AA) — `contrast.mjs`

임계값: **본문/작은 글자 4.5:1 이상**, 큰 글자(18px+ 또는 14px+ 굵게) 3:1 이상. 미달이면 본문에 안 씀.

아래를 `contrast.mjs`로 저장하고 `node contrast.mjs "#글자" "#배경"`:

```js
function lin(c){c/=255;return c<=0.03928?c/12.92:Math.pow((c+0.055)/1.055,2.4);}
function lum(hex){const h=hex.replace('#','');const r=parseInt(h.slice(0,2),16),g=parseInt(h.slice(2,4),16),b=parseInt(h.slice(4,6),16);return 0.2126*lin(r)+0.7152*lin(g)+0.0722*lin(b);}
export function ratio(fg,bg){const L1=lum(fg),L2=lum(bg);const hi=Math.max(L1,L2),lo=Math.min(L1,L2);return (hi+0.05)/(lo+0.05);}
if(process.argv[2]&&process.argv[3]){const r=ratio(process.argv[2],process.argv[3]);console.log(`${process.argv[2]} on ${process.argv[3]} = ${r.toFixed(2)}:1  ${r>=4.5?'PASS':r>=3?'LARGE-only':'FAIL'}`);}
```

검사쌍: `ink`/`ink-2`/`ink-3` × `surface`·`surface-sub`·`canvas` (라이트·다크 각각), 시맨틱 텍스트 × 같은 계열 bg(`crit` on `crit-bg`), `brand-ink` on `surface`.

### 3.2 색약(CVD) — dataviz `validate_palette.js`

새 색·인접색·램프를 넣거나 바꾸기 전 반드시 통과. 스크립트는 dataviz 스킬 안에 있음. 위치 찾기:

```bash
find / -name validate_palette.js -path '*dataviz*' 2>/dev/null | head -1
```

핵심 인접쌍 = **그린(통과) ↔ 빨강(위반)**. 목표 **deutan ΔE ≥ 8**. 6~8은 보조 인코딩(아이콘+글자)이 있어야 합법이지만, **이 프로젝트는 색으로도 통과시킨다(≥8).**

```bash
node <경로>/validate_palette.js "#0E9F6E,#C0392B" --mode light   # 라이트 그린↔빨강
node <경로>/validate_palette.js "#3EE08A,#FF5252" --mode dark    # 다크 그린↔빨강
```

**검증 완료 기록:** 라이트 deutan ΔE **9.3 PASS** / 다크 **11.7 PASS**. (다크 위반색은 살몬 `#F08A80`가 그린과 5.6로 뭉개져서 순빨강 `#FF5252`로 교체함. 되돌리지 말 것.)

### 3.3 em-dash 0

```bash
grep -c "—" design/mockups/barum.html   # 0 이어야 함
```

### 3.4 기본 라이트 초기화 스크립트 (모든 화면 `<head>` 최상단 동일)

```html
<script>(function(){try{var s=localStorage.getItem('barum-theme');document.documentElement.setAttribute('data-theme',s||'light');}catch(e){document.documentElement.setAttribute('data-theme','light');}})();</script>
```

### 3.5 토큰 규율

- 모든 색은 CSS 변수(`:root`)로만. 하드코딩 hex 흩뿌리기 금지.
- 화면이 여러 개가 되면 `:root` 토큰 100% 동일하게 동기화.

### 커밋 전 체크리스트

- [ ] 신규/변경 텍스트색 대비 4.5:1 (라이트·다크)
- [ ] 신규/변경 색 CVD 검증 PASS (그린↔빨강 deutan ≥ 8)
- [ ] 상태·심각도가 색 단독이 아니라 색+아이콘+글자
- [ ] em-dash 0
- [ ] 기본 라이트 초기화 스크립트 동일
- [ ] 색은 CSS 변수, 하드코딩 없음
- [ ] taste-skill AI-tell 훑기 (손그림 장식·전면모노 등)

---

## 4. 확정 팔레트 (전부 검증 통과값, `barum.html` 기준)

### 라이트 `:root`
```
--canvas:#E7ECEB; --surface:#FFFFFF; --surface-sub:#F0F3F2;   /* 시원한 워크벤치 톤(패널 부양). 옛 따뜻한 #ECEFEA는 페이퍼감이 강해 콘솔감을 깎아서 교체 */
--line:#DDE4E2; --line-2:#CDD6D3;
--ink:#14231B; --ink-2:#33413A; --ink-3:#5C6B62;
--brand:#0E9F6E;       /* 채움/마크 */
--brand-ink:#0B7350;   /* 라이트에서 그린 '텍스트' (대비 5.86) */
--brand-deep:#0F5132;  /* 인버스 배경(활성 nav·마크) */
--on-brand:#FFFFFF;
--crit:#C0392B; --crit-bg:#FBECE9; --crit-bd:#EEC9C2;   /* 경보 = 빨강만 */
--nav-hover:#FFFFFF; --nav-active-bg:#E9F2ED;           /* 사이드바 hover/선택 (옅은 틴트, Notion식 고스트) */
```

### 다크 `:root[data-theme="dark"]`
```
--canvas:#070B08; --surface:#0B100C; --surface-sub:#0E140F;
--line:#1C2A21; --line-2:#2C4133;
--ink:#E8F5EC; --ink-2:#B7D6C4; --ink-3:#86A594;
--brand:#3EE08A; --brand-ink:#3EE08A; --brand-deep:#3EE08A;
--on-brand:#04140B;
--crit:#FF5252; --crit-bg:#241614; --crit-bd:#4A2B27;   /* 그린과 deutan ΔE 11.7 */
--nav-hover:#151E18; --nav-active-bg:#1B2822;           /* 사이드바 hover/선택 (옅은 틴트) */
```

### 타입
```
--sans:"Pretendard Variable",Pretendard,-apple-system,system-ui,sans-serif;  /* 사람 계층 */
--mono:"JetBrains Mono","SF Mono",ui-monospace,Menlo,monospace;              /* 기계 계층 */
```

---

## 5. 아이콘·모양

- **목업은 인라인 SVG 라인 아이콘**(stroke 1.8~2.0, `stroke-linecap:square`로 각지게, 터미널 톤). **실앱 구현 시 Phosphor로 교체.**
- 이모지 아이콘 금지. 손그림 장식 SVG 금지.
- 상태 아이콘은 §1대로 모양으로도 구분(체크·경고삼각·연필).
- 모양 스케일: radius 0 고정(전부 샤프).
- **사이드바·메뉴는 고스트(ghost) 스타일.** 박스(테두리)·채움 버튼 지양. 액션·토글은 투명 배경 + hover 옅은 틴트(`--nav-hover`), 활성은 옅은 선택 틴트(`--nav-active-bg`) + 굵게. **무거운 초록 채움 블록 금지**(Notion식 경량). 사이드바엔 상단바·하단 문구와 중복되는 것(브랜드 전환·기준 배지 등) 넣지 않기.
- **모달·다이얼로그는 JetBrains Mono(터미널 다이얼로그).** 타이틀은 브래킷 `[ ... ]`, 항목은 `›` 프롬프트, 샤프(radius 0). 백드롭 `rgba(7,11,8,.5)`. Esc·백드롭 클릭으로 닫기, 포커스 복원. 진입 모션은 `translateY(6px)+opacity` 짧게(reduced-motion이면 정지).
- **콘솔감은 색이 아니라 구조에서.** 캔버스는 패널보다 살짝 눌러 흰 패널이 뜨게(워크벤치), 크롬(라벨·상태바·태그)은 모노, 커서 유지. 배경을 따뜻하게 깔면 "웰니스 브랜드"로 읽혀 콘솔감이 깎인다.
