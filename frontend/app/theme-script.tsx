/**
 * FOUC 방지용 인라인 테마 스크립트.
 * <head>에서 body 렌더 전에 동기 실행되어, 첫 페인트 전에 <html data-theme>를 확정한다.
 * 우선순위: localStorage.theme > 시스템(prefers-color-scheme). 저장값 없으면 시스템을 따른다.
 * next/script가 아니라 원시 <script>를 쓰는 이유: beforeInteractive보다도 먼저,
 * 마크업 순서상 즉시 실행돼야 깜빡임이 없다.
 */
const script = `(function(){try{var t=localStorage.getItem('theme');if(t!=='light'&&t!=='dark'){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}document.documentElement.setAttribute('data-theme',t);}catch(e){}})();`;

export function ThemeScript() {
  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
