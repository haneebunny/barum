"""정답셋 jsonl을 로컬 SQLite로 통합하는 빌드 스크립트.

schema.sql(Postgres)의 로컬 검증용 미러다. 흩어진 학습 데이터를 한 파일(data/barum.db)로
모아 파편화를 없애고, 라벨 분포·split 무결성을 카운트로 확인한다.

지금 범위: listings + sentences + labels(vlm_hint)만 채운다.
  - 사람 라벨(human_initial)은 2026-08-08 라벨링 완료 후 워크북에서 추가한다.
  - 증거보존 메타(sellers·detail_images·products)는 11번가 매니페스트 연동 스텝에서 채운다.

재실행하면 DB를 새로 만든다(재생성 가능 = 재현성).
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "barum.db"

# 입력: (파일명, split). goldset=학습, holdout=평가.
SOURCES = [
    ("goldset_master.jsonl", "train"),
    ("holdout_master_v1.jsonl", "holdout"),
]

# 허용 라벨(호수 체계). hint가 이 집합 밖이면 스킵하고 경고.
VALID_LABELS = {
    "합법", "1호_질병표방", "2호_의약품오인", "3호_건기식오인",
    "4호_거짓과장", "5호_소비자기만", "대상외",
}

# schema.sql(Postgres)의 SQLite 미러. 구조 동일, 방언만 다름.
SQLITE_DDL = """
create table users (
    id integer primary key, name text not null,
    role text not null default 'reviewer' check (role in ('reviewer','admin')),
    auth_id text, created_at text default (datetime('now')));

create table sellers (
    id integer primary key, biz_name text not null, seller_no text,
    return_address text, biz_reg_no text, telesale_no text, biz_address text,
    created_at text default (datetime('now')));

create table products (
    id integer primary key, hf_report_no text, manufacturer text, brand text,
    name_raw text not null, name_norm text, primary_ingredient text,
    review_cert_no text, barcode text, created_at text default (datetime('now')));

create table listings (
    id integer primary key, platform text not null, platform_product_id text not null,
    seller_id integer references sellers(id), product_id integer references products(id),
    product_url text not null, product_type text, crawled_at text,
    first_seen_at text, last_seen_at text,
    status text not null default 'active' check (status in ('active','removed','changed')),
    status_checked_at text, takedown_requested_at text, takedown_confirmed_at text,
    created_at text default (datetime('now')),
    unique (platform, platform_product_id));

create table detail_images (
    id integer primary key, listing_id integer not null references listings(id),
    image_url text, local_path text, sha256 text not null unique,
    created_at text default (datetime('now')));

create table sentences (
    id integer primary key, listing_id integer not null references listings(id),
    image_id integer references detail_images(id), tile text, ord integer,
    text text not null, context_before text, context_after text, tile_text text,
    bbox text, meta text not null default '{}',
    split text not null default 'none' check (split in ('train','holdout','none')),
    source_batch text, created_at text default (datetime('now')));
create unique index sentences_natkey on sentences (image_id, tile, ord) where image_id is not null;
create index sentences_listing_idx on sentences (listing_id);
create index sentences_split_idx on sentences (split);

create table labels (
    id integer primary key, sentence_id integer not null references sentences(id),
    label text not null check (label in (
        '합법','1호_질병표방','2호_의약품오인','3호_건기식오인',
        '4호_거짓과장','5호_소비자기만','대상외')),
    label_source text not null check (label_source in ('vlm_hint','human_initial','staff_review')),
    labeler_id integer references users(id), confidence text, note text,
    is_cross_check integer not null default 0,
    approved_for_training integer,
    created_at text default (datetime('now')));
create index labels_sentence_idx on labels (sentence_id);
create index labels_source_idx on labels (label_source);
"""


def upsert_listing(con, cache, o):
    """prdNo 기준으로 리스팅을 한 번만 만들고 id를 돌려준다."""
    prd = str(o["product_id"])
    if prd in cache:
        return cache[prd]
    cur = con.execute(
        "insert into listings (platform, platform_product_id, product_url, product_type) "
        "values (?, ?, ?, ?)",
        ("11st", prd, o.get("product_url") or "", o.get("product_type")),
    )
    cache[prd] = cur.lastrowid
    return cache[prd]


def build():
    """정답셋 두 파일을 SQLite로 통합하고 카운트를 출력한다."""
    for fname, _ in SOURCES:
        if not (DATA / fname).exists():
            sys.exit(f"입력 파일 없음: {DATA / fname}")

    if DB.exists():
        DB.unlink()  # 재생성(재현성)
    con = sqlite3.connect(DB)
    con.executescript(SQLITE_DDL)

    listing_cache = {}
    n_sent = n_lab = n_skip = 0
    for fname, split in SOURCES:
        for line in (DATA / fname).open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            lid = upsert_listing(con, listing_cache, o)

            # 반정형 메타는 meta(jsonb)로 모은다
            meta = {k: o[k] for k in ("certified_function", "disclaimer")
                    if o.get(k)}
            cur = con.execute(
                "insert into sentences "
                "(listing_id, text, context_before, context_after, tile_text, meta, split, source_batch) "
                "values (?, ?, ?, ?, ?, ?, ?, ?)",
                (lid, o.get("sentence") or "", o.get("context_before"),
                 o.get("context_after"), o.get("tile_text"),
                 json.dumps(meta, ensure_ascii=False), split, fname),
            )
            sid = cur.lastrowid
            n_sent += 1

            # VLM 예비라벨(hint) → vlm_hint 라벨, 학습 제외(approved=0)
            hint = o.get("hint")
            if not hint:
                continue
            if hint not in VALID_LABELS:
                print(f"[스킵] 알 수 없는 hint '{hint}' (id={o.get('id')}, {fname})")
                n_skip += 1
                continue
            con.execute(
                "insert into labels "
                "(sentence_id, label, label_source, approved_for_training, is_cross_check) "
                "values (?, ?, 'vlm_hint', 0, ?)",
                (sid, hint, 1 if o.get("is_cross_check") == "Y" else 0),
            )
            n_lab += 1

    con.commit()
    _report(con, n_lab, n_skip)
    con.close()


def _report(con, n_lab, n_skip):
    """통합 결과를 카운트로 검증 출력한다."""
    q = lambda sql, *a: con.execute(sql, a).fetchone()[0]
    print("\n=== 통합 결과 ===")
    print(f"listings : {q('select count(*) from listings')}")
    print(f"sentences: {q('select count(*) from sentences')}")
    for s in ("train", "holdout"):
        print(f"  {s:8}: {q('select count(*) from sentences where split=?', s)}")
    print(f"labels(vlm_hint): {n_lab}  (스킵 {n_skip})")
    print("hint 라벨 분포:")
    for label, cnt in con.execute(
        "select label, count(*) from labels group by label order by count(*) desc"
    ):
        print(f"  {label:14}: {cnt}")


if __name__ == "__main__":
    build()
    print(f"\n완료: {DB}")
