/**
 * 홈 화면에서 붙여넣거나 끌어다 놓은 초안을 /inspect로 한 번만 넘기는 통로.
 * URL로는 File을 못 넘기고, 세션스토리지엔 File을 그대로 못 넣어서 모듈 스코프 변수로 들고 있는다.
 * 클라이언트 라우팅(next/link, router.push)은 새로고침이 아니라 같은 JS 런타임을 유지하므로 동작한다.
 * 하드 리프레시(주소창 직접 입력·새로고침)로 /inspect에 들어오면 당연히 비어 있다 — 그게 맞는 동작이다.
 */

export interface InspectDraft {
  ad_text?: string;
  files?: File[];
}

let pending_draft: InspectDraft | null = null;

export function setDraft(draft: InspectDraft) {
  pending_draft = draft;
}

/** 한 번 읽으면 비운다. /inspect 마운트 시 1회만 소비하려는 용도. */
export function takeDraft(): InspectDraft | null {
  const draft = pending_draft;
  pending_draft = null;
  return draft;
}
