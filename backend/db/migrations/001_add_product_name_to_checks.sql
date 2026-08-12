-- 001: checks 테이블에 product_name 컬럼 추가
-- 배경: 광고 제목/상품명도 판정 대상에 포함(규정 반영).
--       이력 조회 시 상품명으로 검색할 수 있게 별도 컬럼으로 저장.
-- 적용: Supabase 대시보드 > SQL Editor에 붙여 실행.
-- 멱등: if not exists 대신 add column if not exists (Postgres 11+).

alter table checks
  add column if not exists product_name text;

comment on column checks.product_name is '상품명/광고 제목 (선택 입력, 판정 대상에 포함)';
