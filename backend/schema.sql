-- barum 학습·운영 데이터 스키마 (Postgres / Supabase)
-- 확정: 2026-08-07 인터뷰 (PROJECT.md §3.5, 필드 명세 docs/metadata_spec.md)
--
-- 개체 3층: product(제품 identity) / listing(셀러 판매글) / detail_image(광고물=판정단위)
-- 판정 단위 = 이미지(sha256), 학습·판정 기본 단위 = 문장(sentence)
-- 라벨은 append-only, 사람 승인 라벨만 학습(vlm_hint 제외)
--
-- 지금은 DDL 파일만 확정(로컬 검증용). Supabase 프로젝트에는 웹 검토(B) 붙일 때 적용.
-- 향후: pgvector 확장으로 sentences.embedding 추가 예정(유사 위반문구·near-dup 검색).

-- ─────────────────────────────────────────────────────────────
-- users: 라벨러·실무자·관리자
-- ─────────────────────────────────────────────────────────────
create table users (
    id          bigserial primary key,
    name        text not null,
    role        text not null default 'reviewer'
                check (role in ('reviewer', 'admin')),
    auth_id     uuid,                         -- Supabase auth 연결(나중)
    created_at  timestamptz not null default now()
);

-- ─────────────────────────────────────────────────────────────
-- sellers: 판매업체(누가 광고했나). biz_name만 지금 수집, 나머지 슬롯.
-- ─────────────────────────────────────────────────────────────
create table sellers (
    id              bigserial primary key,
    biz_name        text not null,            -- 상호 (Open API)
    seller_no       text,                     -- 판매자 식별자 (웹)
    return_address  text,                     -- 반품/교환지 주소 = 소재지 근사 (웹, 미수집 슬롯)
    biz_reg_no      text,                     -- 사업자등록번호 (미수집 슬롯)
    telesale_no     text,                     -- 통신판매업신고번호 (미수집 슬롯)
    biz_address     text,                     -- 사업장 소재지 (미수집 슬롯)
    created_at      timestamptz not null default now()
    -- 대표자명(개인정보)은 의도적으로 두지 않음
);
-- 같은 판매자 식별자는 하나로 (null은 중복 허용)
create unique index sellers_seller_no_uidx on sellers (seller_no) where seller_no is not null;

-- ─────────────────────────────────────────────────────────────
-- products: 제품 identity(무슨 제품). 중복식별의 주어.
-- ─────────────────────────────────────────────────────────────
create table products (
    id                  bigserial primary key,
    hf_report_no        text,                 -- 품목제조신고번호 = 제품 고유키 (OCR, 있으면 최강 중복키)
    manufacturer        text,                 -- 제조사 (OCR)
    brand               text,                 -- 브랜드 (OCR)
    name_raw            text not null,        -- 원본 제품명, 셀러 표기 (Open API)
    name_norm           text,                 -- 정규화 제품명 (생성)
    primary_ingredient  text,                 -- 지표성분/주요 원료 (OCR, reference 매칭)
    review_cert_no      text,                 -- 광고심의필 번호 (OCR)
    barcode             text,                 -- 바코드/GTIN (OCR, 옵션)
    created_at          timestamptz not null default now()
);
-- 품목제조신고번호 같으면 같은 제품(크로스플랫폼 중복키)
create unique index products_hf_report_no_uidx on products (hf_report_no) where hf_report_no is not null;

-- ─────────────────────────────────────────────────────────────
-- listings: 셀러 판매글(증거·출처·상태). 조치(상품 내림)의 단위.
-- ─────────────────────────────────────────────────────────────
create table listings (
    id                      bigserial primary key,
    platform                text not null,            -- 11st / coupang …
    platform_product_id     text not null,            -- 상품번호(11st prdNo)
    seller_id               bigint references sellers (id),
    product_id              bigint references products (id),   -- 제품 매칭되면 채움
    product_url             text not null,            -- 원본 상품 URL (사라져도 기록)
    product_type            text,                     -- 상품 유형(건강기능식품 등)
    -- 증거보존 시점/상태
    crawled_at              timestamptz,              -- 수집 시각("이 시점에 이랬다"). 크롤 수집분은 필수, 레거시 정답셋 임포트는 null
    first_seen_at           timestamptz,
    last_seen_at            timestamptz,
    status                  text not null default 'active'
                            check (status in ('active', 'removed', 'changed')),
    status_checked_at       timestamptz,
    takedown_requested_at   timestamptz,
    takedown_confirmed_at   timestamptz,
    created_at              timestamptz not null default now(),
    -- 같은 플랫폼 같은 상품번호 = 한 리스팅
    unique (platform, platform_product_id)
);
create index listings_seller_idx  on listings (seller_id);
create index listings_product_idx on listings (product_id);

-- ─────────────────────────────────────────────────────────────
-- detail_images: 광고물(증거 본체 = 판정 단위). sha256으로 dedup.
-- 같은 이미지를 여러 리스팅이 재사용하면 재삽입하지 않고 재사용(판정 1회).
-- listing_id = 최초 수집 리스팅(대표). 다대다 추적은 향후.
-- ─────────────────────────────────────────────────────────────
create table detail_images (
    id          bigserial primary key,
    listing_id  bigint not null references listings (id),
    image_url   text,                         -- 원본 이미지 URL(외부호스트 포함)
    local_path  text,                         -- 보관한 원본 파일 위치
    sha256      text not null unique,         -- 무결성 + 판정단위(dedup 스킵 키)
    created_at  timestamptz not null default now()
);
create index detail_images_listing_idx on detail_images (listing_id);

-- ─────────────────────────────────────────────────────────────
-- sentences: OCR 문장(학습·판정 기본 단위). 최소한 리스팅에 연결.
-- 정답셋 문장은 image/tile 연결이 없어 nullable. OCR·크롤 연동 시 채움.
-- ─────────────────────────────────────────────────────────────
create table sentences (
    id              bigserial primary key,
    listing_id      bigint not null references listings (id),   -- 문장은 최소한 리스팅(판매글)에 연결
    image_id        bigint references detail_images (id),       -- OCR/크롤 연동 시 채움(정답셋은 null)
    tile            text,                     -- 타일 파일명(정답셋은 null)
    ord             int,                      -- 타일 내 순서(정답셋은 null)
    text            text not null,            -- 판정의 주어 = "근거 N건"으로 출력
    context_before  text,                     -- 앞 문맥 윈도우
    context_after   text,                     -- 뒤 문맥 윈도우
    tile_text       text,                     -- 원 타일 전체 텍스트(참고)
    bbox            jsonb,                     -- 하이라이팅 좌표 슬롯(OCR/DL 붙으면 채움)
    meta            jsonb not null default '{}',  -- 반정형(certified_function·disclaimer 등)
    split           text not null default 'none'
                    check (split in ('train', 'holdout', 'none')),
    source_batch    text,                     -- 출신 배치/파일(추적)
    created_at      timestamptz not null default now()
);
-- 이미지·타일이 있을 때만 자연키 유효(정답셋은 image_id null이라 제외)
create unique index sentences_natkey_uidx on sentences (image_id, tile, ord) where image_id is not null;
create index sentences_listing_idx on sentences (listing_id);
create index sentences_image_idx   on sentences (image_id);
create index sentences_split_idx   on sentences (split);

-- ─────────────────────────────────────────────────────────────
-- labels: 문장별 라벨(append-only, 출처 여럿). 이력 전부 보존.
-- ─────────────────────────────────────────────────────────────
create table labels (
    id              bigserial primary key,
    sentence_id     bigint not null references sentences (id),
    label           text not null
                    check (label in (
                        '합법',
                        '1호_질병표방', '2호_의약품오인', '3호_건기식오인',
                        '4호_거짓과장', '5호_소비자기만',
                        '대상외')),
    label_source    text not null
                    check (label_source in ('vlm_hint', 'human_initial', 'staff_review')),
    labeler_id      bigint references users (id),   -- vlm_hint면 null
    confidence      text,                            -- xlsx 자유값 수용(유연)
    note            text,
    is_cross_check  boolean not null default false,
    -- 학습 사용 가능: vlm_hint만 제외(사람 승인 라벨만). 승인 워크플로 생기면 일반 컬럼 전환.
    approved_for_training boolean
                    generated always as (label_source <> 'vlm_hint') stored,
    created_at      timestamptz not null default now()
);
create index labels_sentence_idx  on labels (sentence_id);
create index labels_source_idx    on labels (label_source);
create index labels_training_idx  on labels (approved_for_training);

-- ─────────────────────────────────────────────────────────────
-- current_labels: 문장별 '최신 유효 사람 라벨'(append-only에서 승인 라벨만)
-- 주요 광고문구도 이 뷰 ⨝ sentences 조인으로 렌더(별도 저장 없음).
-- ─────────────────────────────────────────────────────────────
create view current_labels as
select distinct on (sentence_id)
    sentence_id, label, label_source, labeler_id, confidence, created_at
from labels
where label_source in ('human_initial', 'staff_review')
order by sentence_id, created_at desc;
