// 심사위원 데모(유어베리 세럼)의 단일 소스. 검사·개선·신규생성 3종을 전부
// 커밋된 고정 픽스처로 렌더한다(백엔드 호출 없음, 페이월 우회). 백엔드 bake
// 스크립트(backend/scripts/bake_demo.py)가 아래 픽스처를 굽고, 이 파일의 상수와
// 반드시 값이 같아야 한다.

// 검사 리포트의 데모 result_id. report/[id] 라우트가 이 값이면 백엔드 대신
// 커밋된 픽스처를 로드한다.
export const DEMO_RESULT_ID = "demo-yourberry-serum";

// 신규 생성(create) 데모 진입에 쓰는 가상 id(검사 리포트가 없는 흐름).
export const DEMO_CREATE_ID = "demo-yourberry-create";

export const DEMO_PRODUCT_NAME = "유어베리 글로우 리제너레이션 세럼";

// 검사 입력으로 자동 첨부하는 상세페이지 이미지(public/demo에 bake가 복사).
export const DEMO_DETAIL_IMAGE = "/demo/yourberry_serum_detail.png";

/** report/content 라우트에서 데모 픽스처를 써야 하는 id인지. */
export function isDemoReportId(id: string): boolean {
  return id === DEMO_RESULT_ID;
}

export function isDemoCreateId(id: string): boolean {
  return id === DEMO_CREATE_ID;
}
