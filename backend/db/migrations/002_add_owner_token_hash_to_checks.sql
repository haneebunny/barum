-- 002: 로그인 전 익명 브라우저별 검사 이력 소유권
-- 원문 토큰은 브라우저에만 두고 서버에는 SHA-256 해시만 저장한다.

alter table checks
  add column if not exists owner_token_hash text;

create index if not exists checks_owner_created_idx
  on checks (owner_token_hash, created_at desc);

comment on column checks.owner_token_hash is
  '익명 브라우저 history token의 SHA-256. NULL인 기존 개발 데이터는 사용자 이력에서 제외';
