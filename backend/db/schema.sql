-- barum 셀프체크 스키마 (Supabase / Postgres)
-- Phase2 (2026-08-11): 검사 이력·증거보존(Task2) + 사례 임베딩(Task1b).
--
-- ⚠ 기존 backend/schema.sql(식품/감독기관용 7테이블)과 별개다. 그건 재사용 안 함.
--   이건 로그인 없는 셀프체크 서비스용 최소 스키마.
--
-- 적용: Supabase 대시보드 → SQL Editor에 통째로 붙여 실행(하니).
-- 멱등(if not exists / create or replace)이라 재실행 안전.

-- pgvector 확장 (사례 유사검색용). Supabase는 기본 지원.
create extension if not exists vector;

-- ─────────────────────────────────────────────────────────────
-- checks: 검사 이력 (Task2). CheckReport를 통째로 저장, 나중에 다시 보기.
--   id는 추측불가 capability token(secrets.token_urlsafe) — 로그인 대신 이 URL이 접근권.
--   report는 JSON 통째라 CheckReport 모델이 바뀌어도 마이그레이션 최소.
-- ─────────────────────────────────────────────────────────────
create table if not exists checks (
  id           text primary key,       -- result_id (secrets.token_urlsafe(32))
  created_at   timestamptz not null default now(),
  region       text not null,
  report       jsonb not null,         -- CheckReport 통째
  image_sha256 text,                   -- 이미지 입력 시 원본 sha256(증거 보존, FR-1)
  image_path   text,                   -- Storage 버킷 내 경로(있으면)
  product_name text                    -- 상품명/광고 제목(선택, 판정 대상에 포함)
);

-- ─────────────────────────────────────────────────────────────
-- reference_cases: 실제 적발사례 임베딩 (Task1b, Phase3).
--   cases.md의 사례를 임베딩해 저장 → 새 문구와 유사한 사례를 검색해 판정 프롬프트에.
--   text-embedding-3-small = 1536차원.
-- ─────────────────────────────────────────────────────────────
create table if not exists reference_cases (
  id           bigserial primary key,
  text         text not null,          -- 적발 문구(임베딩 대상)
  violation    text,                   -- 위반유형(T1/T2/T5 등, 참고)
  disposition  text,                   -- 처분(광고업무정지 N개월 등)
  source       text,                   -- 출처·일자
  embedding    vector(1536)
);
-- 소량(수십 건)이면 순차 코사인 비교로 충분(PM2 확인). 데이터 커지면 인덱스 추가:
-- create index on reference_cases using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- 유사 사례 top-K 검색 (코사인). Phase3에서 호출.
--   <=> = pgvector 코사인 거리. similarity = 1 - 거리(클수록 비슷).
create or replace function match_reference_cases(
  query_embedding vector(1536),
  match_count int
)
returns table (
  id bigint, text text, violation text, disposition text, source text, similarity float
)
language sql stable as $$
  select id, text, violation, disposition, source,
         1 - (embedding <=> query_embedding) as similarity
  from reference_cases
  where embedding is not null
  order by embedding <=> query_embedding
  limit match_count;
$$;
