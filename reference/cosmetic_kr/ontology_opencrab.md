# 화장품 표시광고 판정 온톨로지 (OpenCrab)

> 무엇: `prohibited_expressions.md`·`functional_ingredients.md`·`cases.md`·`violation_types/`를 온톨로지 그래프로 변환해 OpenCrab에 적재한 것. 백엔드가 판정 로직 짤 때 "이 표현이 위반인지, 어느 조항 근거인지"를 MCP로 질의하는 용도.
> 저장 위치: 이 저장소가 아니라 OpenCrab(워크스페이스 `e76b27ac-4f0a-497b-9b3b-fd47c7920d4d`)에 있다. 이 문서는 팀 추적용 포인터일 뿐, 실제 그래프는 여기 없다.
> 담당: DB 2. 구축일 [ 2026-08-12 ].

## 질의 방법
Claude Code 세션에서 opencrab MCP 도구로 직접 질의한다(코드 import 아님).

    opencrab_query(query: "질문 내용", pack_query: "barum_ontology")

## 팩 4개
| 팩 이름 | package_id | 내용 |
|---|---|---|
| barum 위반유형 체계 (호수·T코드·법령근거) | `05f43f10-95e4-4466-832a-92ad119824f8` | ViolationType(1호/2호/5호/대상외/합법) ↔ RuleTag(T1~T6) 매핑, Statute(법령근거) 6종. T5·T6 분리 함정 반영 |
| barum 금지표현 판정 (Expression 3분류) | `d99ca841-fe0b-4d0a-a587-1a3529a02d09` | Expression 위반/검토필요/합법 3분류, T1~T6 경계표현 예시. 검토필요≠미판정 함정, 일반 수식어 5호 미확정 쟁점 반영 |
| barum 기능성 고시원료 온톨로지 (Ingredient) | `0d46484f-3cf8-41e1-bb38-0c664e0d4a53` | Ingredient ↔ 기능·기준함량 관계, 이명(異名) 매칭 주의 |
| barum 적발사례 온톨로지 (Case) | `64607081-fd13-43b0-9cd4-c17c5b6c9e85` | Case ↔ 문구/위반유형/처분 관계, `cases.md` 예시 4건 |

전부 category `barum_ontology`, visibility `private`.

## 갱신
소스 문서(`prohibited_expressions.md` 등)가 바뀌면 이 4개 팩도 `opencrab_ingest_text`로 다시 적재해야 한다. 지금은 수동이고 자동 동기화는 없다.

## 알려진 제약
- `opencrab_project_manage`(팩을 프로젝트로 묶는 기능)는 이 워크스페이스 티어(pro)에서 막혀 있다(Expert/Enterprise 전용). 그래서 4개 팩은 프로젝트로 안 묶이고 개별로 존재한다. 검색·질의는 category/tag(`barum_ontology`)로 묶여서 되니 실사용에는 문제없다.
- 적발사례(Case) 팩은 구조 예시일 뿐, `cases.md`의 전체 사례가 반영된 게 아니다. 전체 사례 임베딩·적재는 Supabase `reference_cases` pgvector 쪽(별도 작업)이 정본이다.
