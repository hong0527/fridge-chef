# FridgeChef 명세-코드 갭 리포트

> 작성일: 2026-05-18
> 기준: SRS v1.10 (pdf/SRS_레시피추천시스템_v1.10 - 공유용.docx)
> 코드: `dev` 브랜치 (커밋 9ca5f11)

---

## 요약

핵심 추천 엔진(모델 A·B + Gemini citation 검증 + 알레르기 하드컷)은 동작 가능 상태입니다. 단, SRS v1.10이 명세한 부가 기능(즐겨찾기·리뷰·검색·관리자·알레르기 수정 화면) 5개 UC가 화면·라우터 모두 없습니다. 학부 7주 일정 기준 SRS 약 50% 충족이며, Sprint 1·2로 보강 시 90%대 도달 가능합니다.

---

## 1. FR 정합 현황 (SRS v1.10 §5)

| FR 코드 | 명세 요구 | 현재 코드 상태 | 위치 | 판정 |
|---|---|---|---|---|
| FR-001 | 회원가입 (이메일 + 소셜) | 이메일+비번+nickname+JWT | `backend/app/api/auth.py` `frontend/app/auth/page.tsx` | ⚠️ 부분 (소셜 미구현) |
| FR-002 | 로그인/로그아웃 | bcrypt 검증 + JWT | `backend/app/services/auth_service.py` | ✅ |
| FR-007 | 알레르기 영구 저장 + 수정 화면 | 회원가입 시점 저장만, 수정 API/화면 없음 | - | ⚠️ Sprint 1 보강 (BE-104, FE-201) |
| FR-008~010 | 냉장고 CRUD + SYNONYM_MAP | 추가/삭제/조회 동작, SYNONYM_MAP 100쌍 정규화 | `backend/app/api/fridge.py` | ✅ |
| FR-011 | 모델 A 냉털 (코사인 유사도, 상위 10) | 5차원 벡터 코사인, Top-K=10 | `backend/app/services/model_a.py` | ✅ |
| FR-012 | 모델 A 알레르기 0% 보장 | 알레르기 하드컷 + signup 정규화 | `model_a.py`, `auth_service.py` | ✅ |
| FR-013 | 모델 A 결과 형식 | RecipeBrief + score | `schemas/recommend.py` | ✅ |
| FR-014 | 모델 B 부족재료 (≤5개) | 소프트 필터 + 복합점수 0.7/0.2/0.1 | `backend/app/services/model_b.py` | ✅ |
| FR-015 | 모델 B Gemini 선별 (3개) + citation 검증 | Gemini 2.5 Flash + 화이트리스트 검증, 자기 인용 폴백 제거 | `services/gemini_client.py` + `model_b.py:100` | ✅ |
| FR-016 | 모델 B Gemini 한국어 이유 | reason 필드, 폴백 시 빈 문자열 | `model_b.py:124` | ✅ |
| FR-017~018 | 모델 A·B 결과 동시 표시 | 한 화면에 model_a + model_b 섹션 | `frontend/app/recommend/page.tsx` | ✅ |
| **UC-05** | 알레르기 마이페이지 별도 수정 | 화면·API 없음 | - | ❌ Sprint 1 (BE-104, FE-201) |
| **UC-07** | 즐겨찾기 추가·삭제·목록 | 화면 비활성화, 라우터 없음 | `recipe/[id]/page.tsx:24` `FAVORITE_ENABLED=false` | ❌ Sprint 1 (BE-102, FE-203) |
| **UC-08** | 리뷰·별점 작성·수정·삭제 | DB 테이블만 존재, 라우터·화면 없음 | `models/orm.py` Rating | ❌ Sprint 1 (BE-101, FE-202) |
| **UC-09** | 키워드 검색 + 필터 | 단건 조회만 존재 | `api/recipes.py` | ❌ Sprint 1 (BE-103, FE-204) |
| - | 관리자 레시피 관리 | 없음 | - | ❌ Sprint 2 검토 |
| - | 이메일 인증 (FR-001 보강) | UI 모달만, 백엔드 인증 없음 | `auth/page.tsx:213` | ⚠️ 시연용 우회 |
| - | 자동완성 (FR-FRIDGE-03) | 프론트 호출만, 백엔드 라우터 없음 | `lib/api.ts:searchIngredients` | ⚠️ Sprint 1 (BE-105) |

---

## 2. NFR 정합 현황 (SDD + SRS §6)

| NFR | 측정치 | 현재 | 위치 | 판정 |
|---|---|---|---|---|
| NFR-PERF-001 | 추천 응답 ≤ 10초 | asyncio.wait_for(10s) | `services/recommend_service.py:53` | ✅ |
| NFR-PERF-002 | 모델 A·B 동시 호출 | asyncio.gather | `services/recommend_service.py` | ✅ |
| NFR-PERF-003 | Gemini 8s 타임아웃 | wait_for 8s + 폴백 | `services/gemini_client.py:_call_gemini` | ✅ |
| NFR-EVAL-001 | 알레르기 위반 0% (50샘플) | 정규화 + 하드컷 + 골든셋 10건 | `model_a.py:111`, `model_b.py:58`, `auth_service.py:27` | ⚠️ 골든셋 5/50 placeholder, Sprint 1 (QA-401) |
| NFR-EVAL-002 | citation ≥95% 화이트리스트 | citation_ids 누락 시 검증 실패 처리 | `model_b.py:100` | ✅ |
| NFR-SEC-001 | API 키 환경변수 + CORS 화이트리스트 | env 격리, 운영 도메인 화이트리스트 (CORS_ORIGINS env) | `main.py:30` `.env.example` | ✅ |
| NFR-SEC-002 | bcrypt rounds=12, JWT 32자+ 강제 | bcrypt(12), JWT_SECRET 부팅 가드 | `core/security.py:19` | ✅ |
| NFR-OPS-001 | /health 헬스체크 + 컨테이너 | /health, Dockerfile HEALTHCHECK | `main.py:51`, `Dockerfile:28` | ✅ |
| NFR-OPS-002 | DB pool 10 + overflow 20 | 환경별 분기 | `core/db.py:27` | ✅ |
| NFR-MAINT-001 | 모델 A·B 독립 모듈 | services/model_a, model_b 분리 | - | ✅ |
| NFR-SCL-001 | 무상태 API | JWT stateless | - | ✅ |

---

## 3. Top 5 모순 / 결정 권고

### M1. 이메일 인증 (FR-001 vs 코드)
- **명세**: 이메일 인증 메일 발송 → 링크 클릭 → 활성화
- **코드**: 모달만 표시, 실제 인증 없이 즉시 `/fridge`로 이동
- **권고**: 학부 시연 일정상 **이메일 인증은 v2로 격리**. SRS v1.11 에 명시. 또는 SendGrid 무료 티어로 Sprint 2 보강.

### M2. 소셜 로그인 (FR-001 대안 흐름 vs 코드)
- **명세**: Google/Kakao 소셜 가입
- **코드**: 미구현
- **권고**: 학부 7주에 비현실. SRS v1.11에서 "v2 격리"로 다운스코프.

### M3. 관리자 화면 (SRS §1.1 vs 코드)
- **명세**: 관리자 레시피 CRUD
- **코드**: 없음
- **권고**: 학부 과제 범위 외. Sprint 2 검토.

### M4. UC-09 검색·필터 (vs 코드)
- **명세**: 키워드 + 시간·난이도·식이 필터
- **코드**: 단건 조회만
- **권고**: Sprint 1 BE-103 + FE-204로 구현 (8-9h)

### M5. 인메모리 vs DB 출처 (FIX 완료)
- **이전**: 추천 인메모리(35건), 상세 DB → 추천 후 상세 404 가능
- **현재**: startup lifespan에서 SEED_RECIPES → DB idempotent 적재
- **권고**: ✅ 해소. Sprint 1 DA-301로 50건 확장 후 SEED_RECIPES 비대화 검토.

---

## 4. 시드 데이터 (정확한 건수)

| 항목 | 현재 | 권장 |
|---|---|---|
| `db/seeds/sample_recipes.json` | 3건 | 50+건 (Sprint 1 DA-301) |
| `backend/app/models/recipe_repository.py` SEED_RECIPES | 35건 | startup 시 DB 적재됨 |
| `db/seeds/synonym_map.json` | 20쌍 | 100+ (Sprint 1 DA-302) |
| `backend/app/core/synonym_map.py` SYNONYM_MAP | 100쌍 | 200+ |
| `backend/tests/fixtures/allergy_golden_set.json` | 10건 | 50건 (Sprint 1 QA-401) |

---

## 5. 보안·테스트 보강

| 항목 | 상태 |
|---|---|
| JWT_SECRET 32자+ 강제 | ✅ 부팅 가드 적용 |
| CORS_ORIGINS env 화이트리스트 | ✅ docker-compose 주입 |
| bcrypt rounds=12 | ✅ |
| .env .gitignore | ✅ 푸시 차단 확인 |
| signup 알레르기 SYNONYM_MAP 정규화 | ✅ NFR-EVAL-001 누출 방지 |
| Gemini citation_ids 자기 인용 제거 | ✅ NFR-EVAL-002 환각 차단 |
| /api/fridge 인증 단일화 (get_current_user) | ✅ |
| pytest fixture JWT 32자+ | ✅ |
| ruff check (B008 ignore: FastAPI 표준) | ✅ All checks passed |
| pytest 통합 테스트 (X-User-Allergies → JWT) | ⚠️ Sprint 1 (QA-403) |
| 50샘플 골든셋 회귀 | ⚠️ 10/50 |
| Alembic baseline 리비전 | ⚠️ Sprint 2 (BE-201) |

---

## 6. 다음 24시간 To-Do (Day 0)

1. **PM**: GitHub Issue 라벨 + Sprint 1 14개 카드 등록
2. **전원**: 클론 + `.env` 설정 + `docker-compose up --build` 본인 PC 확인
3. **PM**: 첫 분담 회의 30분 (역할 매핑 합의)
4. **Backend**: BE-101 (평점 라우터) 첫 PR 시작
5. **Data**: DA-301 (레시피 시드 50건) 데이터 큐레이션 시작

각자 첫 PR을 Sprint 1 첫 주에 머지하는 것이 목표.
