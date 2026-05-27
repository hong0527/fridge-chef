# FridgeChef 테스트 명세서 (Test Specification)

> 작성일: 2026-05-27
> 버전: 1.0
> 기준 표준: IEEE 829-2008 (Test Documentation), ISO/IEC/IEEE 29119
> 참조 문서: SRS v1.10, SDD v1.0, SPEC_GAP_REPORT.md

---

## 1. 개요 (Introduction)

### 1.1 목적
본 명세서는 FridgeChef 추천 시스템의 품질 보증을 위한 테스트 전략·범위·수행 방법·합격 기준을 정의한다. 단위·통합·E2E·회귀·신뢰성 메트릭 평가까지 SW공학론 표준 테스트 레벨 5단계를 모두 포함한다.

### 1.2 범위
**대상**: 백엔드(FastAPI + SQLAlchemy + Gemini 2.5 Flash) + 프론트엔드(Next.js 14 App Router) + 인프라(Postgres + Redis + Mailpit)
**비대상**: 외부 Gemini API 실호출 정확도 (mock으로 격리), 운영 부하·스트레스 테스트, 보안 침투 테스트

### 1.3 참조 문서
- `docs/SRS_v1.10_1차완성본.pdf` — 기능·비기능 요구사항
- `docs/SDD_v1.0_공유용.pdf` — 4-Layer 아키텍처, 모델 A/B 시퀀스
- `docs/SPEC_GAP_REPORT.md` — 명세-구현 갭 분석

---

## 2. 테스트 전략 (Test Strategy)

### 2.1 V-모델 기반 테스트 레벨

| 레벨 | 대응 개발 단계 | 검증 대상 | 본 프로젝트 매핑 |
|---|---|---|---|
| L1 단위 (Unit) | 상세 설계 | 함수/클래스 | `tests/unit/` (7 파일) |
| L2 통합 (Integration) | 아키텍처 설계 | 모듈 간 상호작용 | `tests/services/`, `tests/api/` |
| L3 시스템 (System) | 요구사항 분석 | 전체 시스템 동작 | `tests/api/` (FastAPI 통합) |
| L4 인수 (Acceptance) | 요구사항 정의 | 사용자 시나리오 | `tests/e2e/`, `tests/regression/test_recommend_golden_set.py` |
| L5 비기능·신뢰성 | NFR 정의 | 메트릭·성능 | `tests/regression/test_quality_metrics.py`, `scripts/evaluate_recommend.py` |

### 2.2 테스트 유형 (Test Types)

| 유형 | 대상 NFR | 도구 |
|---|---|---|
| 기능 테스트 | FR-001~018 | pytest, httpx AsyncClient |
| 정적 분석 | NFR-MAINT-001 | ruff (Python), tsc --noEmit (TS) |
| 회귀 테스트 | 변경 차단 | pytest + xfail 결함 노출 마커 |
| 성능 테스트 | NFR-PERF-001 (≤10s) | asyncio.wait_for 측정, 평가 스크립트 p95 |
| 신뢰성 평가 | NFR-EVAL-001/002 | 학계 표준 메트릭 (Precision@K, MRR, NDCG, CSR) |
| 보안 테스트 | NFR-SEC-001/002/003 | bcrypt rounds 검증, JWT 부팅 가드, rate_limit |

### 2.3 학계 표준 평가 메트릭 (L5)

| 메트릭 | 정의 | 출처 |
|---|---|---|
| Precision@K | Top-K 추천 중 정답 비율 | Shani & Gunawardana (2011) |
| Recall@K | 정답 중 Top-K 포함 비율 | 동일 |
| MRR | 정답이 평균 몇 위에 등장하는지의 역수 평균 | Microsoft Recommenders |
| NDCG@K | 순위 가중 정확도 | Järvelin & Kekäläinen (2002) |
| CSR | Constraint Satisfaction Rate (알레르기 0%) | RecSys 2023 safety track |
| Catalog Coverage | 추천 풀 다양성 | Castells et al. (2022) |

---

## 3. 테스트 환경 (Test Environment)

### 3.1 인프라
| 항목 | 사양 |
|---|---|
| OS | Darwin 24.6.0 (개발), Ubuntu 22.04 (CI - GitHub Actions) |
| Python | 3.11+ |
| Node.js | 20+ |
| 컨테이너 | Docker 28.3.3, docker-compose |
| DB | Postgres 15 (운영), SQLite in-memory (테스트 격리) |

### 3.2 테스트용 환경변수
```
JWT_SECRET=test-secret-do-not-use-in-prod-padding-1234567890abcdef (32자+)
DATABASE_URL=sqlite+aiosqlite:///:memory:
GEMINI_API_KEY=  (빈 키 → 폴백 강제, 외부 호출 차단)
BCRYPT_ROUNDS=4  (테스트 속도 — 운영 12)
```

### 3.3 픽스처 (Fixtures)
| 픽스처 | 위치 | 용도 |
|---|---|---|
| `db_engine` | conftest.py:63 | aiosqlite 인메모리 엔진 |
| `db_session` | conftest.py:87 | 트랜잭션 격리 세션 |
| `app` | conftest.py:100 | DI override된 FastAPI 인스턴스 |
| `async_client` | conftest.py:119 | httpx ASGITransport AsyncClient |
| `test_user` / `verified_signup` | conftest.py:142 | 회원가입 + 이메일 인증 우회 |
| `test_jwt_token` | conftest.py:158 | Bearer 헤더 |
| `mock_gemini_success` / `mock_gemini_fail` | conftest.py:188 | Gemini 결정론 mock |
| `recipe_repo` | conftest.py:220 | 7건 결정론 카탈로그 |

---

## 4. 테스트 케이스 인벤토리 (Test Inventory)

**총 테스트 함수: 182개 / 19개 파일 / 5개 디렉토리**

### 4.1 단위 테스트 (L1) — `tests/unit/` + `tests/services/`

| 파일 | 함수 수 | 검증 대상 | FR/NFR 매핑 |
|---|---|---|---|
| `unit/test_allergy_map.py` | 9 | `expand_allergies()` 카테고리 확장 | NFR-EVAL-001 |
| `unit/test_synonym_map.py` | 10 | 동의어 정규화 | FR-002, SDD §3.2 |
| `unit/test_synonym_map_edge.py` | 10 | 엣지 케이스·잘못된 매핑 (xfail) | NFR-EVAL-001 |
| `unit/test_model_a.py` | 18 | 5차원 벡터, 코사인, contains_all | FR-011 |
| `unit/test_model_b.py` | 10 | 복합점수, 부족재료, Gemini 폴백 | FR-014~016 |
| `unit/test_schemas_auth.py` | 9 | Pydantic 검증·model_validator | FR-001 |
| `unit/test_rate_limit.py` | 6 | 로그인 5회 잠금 | NFR-SEC-003 |
| `services/test_model_a_filters.py` | 8 | contains_all, 알레르기 확장, 조리시간 | NFR-EVAL-001 |
| `services/test_model_b_scoring.py` | 5 | Gemini 폴백, citation, missing_max | NFR-EVAL-002 |
| **소계** | **85** | | |

### 4.2 통합·API 테스트 (L2~L3) — `tests/api/`

| 파일 | 함수 수 | 검증 대상 | FR/NFR 매핑 |
|---|---|---|---|
| `api/test_auth_api.py` | 13 | /signup, /login (이메일 인증 포함) | FR-001, FR-002 |
| `api/test_auth_me_api.py` | 13 | /me GET·PATCH, 알레르기 수정 | FR-007 |
| `api/test_fridge_api.py` | 14 | CRUD, 자동완성, 동의어 정규화 | FR-008~010 |
| `api/test_recipes_api.py` | 5 | /recipes/{id} 상세 조회 | FR-017 |
| `api/test_recommend_api.py` | 13 | /api/recommend 통합 (모델 A·B 동시) | FR-005, FR-011~018 |
| **소계** | **58** | | |

### 4.3 E2E 테스트 (L4) — `tests/e2e/`

| 파일 | 함수 수 | 검증 대상 |
|---|---|---|
| `e2e/test_user_journey.py` | 3 | 가입→인증→로그인→냉장고→추천→상세 전체 흐름 (페르소나 3종) |

### 4.4 회귀·신뢰성 테스트 (L4~L5) — `tests/regression/`

| 파일 | 함수 수 | 검증 대상 | NFR 매핑 |
|---|---|---|---|
| `regression/test_recommend_golden_set.py` | 7 | 5+1 사용자 시나리오 (한식 매운/양식 알레르기/저칼로리/country/빈입력) | FR-011~018 |
| `regression/test_quality_metrics.py` | 8 | **6가지 학계 메트릭 임계값 회귀** (CSR, P@10, MRR, NDCG, Country, Coverage) | NFR-EVAL-001/002 |
| **소계** | **15** | | |

### 4.5 평가 보고서 — `scripts/`

| 스크립트 | 용도 |
|---|---|
| `scripts/evaluate_recommend.py` | 30개 골든셋 시나리오로 6+1 메트릭 보고서 출력 (CI exit code) |
| `scripts/experiment_recommend.py` | 7개 실험으로 model A/B 동작·country 변경·알레르기 차단 실증 |

### 4.6 기타 — `tests/`

| 파일 | 함수 수 | 검증 대상 |
|---|---|---|
| `test_health.py` | 2 | /health 엔드포인트 (NFR-OPS-001) |
| `test_recommend.py` (legacy) | 14 | 추천 시스템 기본 동작 (구버전, 신규 회귀로 대체 가능) |

---

## 5. 합격 기준 (Pass/Fail Criteria)

### 5.1 Hard Gate (반드시 통과)
| 기준 | 임계값 | 검증 위치 |
|---|---|---|
| **CSR (알레르기 누출)** | **= 0건** | `test_quality_metrics::test_csr_allergy_leak_zero` |
| pytest 전체 통과율 | ≥ 99% (회귀 0) | CI |
| ruff check | 0 errors | CI |
| tsc --noEmit | 0 errors | CI |
| /health | 200 OK | CI HEALTHCHECK |

### 5.2 품질 임계값 (학계 표준)
| 메트릭 | 임계값 | 측정 결과 (2026-05-27) |
|---|---|---|
| Precision@10 (model A) | ≥ 0.20 | **0.628** ✅ |
| MRR | ≥ 0.30 | **0.983** ✅ |
| NDCG@10 | ≥ 0.50 | **0.898** ✅ |
| Recall@10 | (참고) | 0.878 |
| Coverage | ≥ 0.30 | **1.000** ✅ |
| Country Top-1 일치율 | ≥ 0.60 | **0.955** ✅ |
| 응답 p95 (단일 추천) | ≤ 1000ms | **0.09ms** ✅ |

### 5.3 알려진 결함 (xfail, 회귀 안전망)
- `test_yubu_should_not_map_to_dubu` — synonym_map 데이터 수정 후 xpass 전환 예정
- `test_jjukkumi_maps_to_nakji_check` — 동일
- `test_soy_milk_should_not_map_to_milk` — 동일

xfail로 마킹된 테스트는 PASS이지만 **결함을 추적**하는 안전망. 결함 수정 시 자동으로 xpass→실패로 전환되어 알림.

---

## 6. 트레이서빌리티 매트릭스 (Traceability Matrix)

### 6.1 FR ↔ 테스트

| FR | 요구사항 요약 | 검증 파일 | 테스트 함수 |
|---|---|---|---|
| FR-001 | 회원가입 (이메일+비번+닉네임) | `api/test_auth_api.py` | TestSignup (4건) |
| FR-002 | 로그인/로그아웃 + JWT | `api/test_auth_api.py` | TestLogin (5건) |
| FR-007 | 알레르기 영구 저장·수정 | `api/test_auth_me_api.py` | TestPatchMeAllergies (4건) |
| FR-008~010 | 냉장고 CRUD + 동의어 정규화 | `api/test_fridge_api.py` | TestFridgeCRUD (전체) |
| FR-011 | 모델 A 냉털 코사인 Top-10 | `unit/test_model_a.py`, `services/test_model_a_filters.py` | 26건 |
| FR-012 | 알레르기 0% 보장 | `unit/test_allergy_map.py`, `regression/test_quality_metrics::test_csr_allergy_leak_zero` | CSR Hard Gate |
| FR-014 | 모델 B 부족재료 (≤5개) | `unit/test_model_b.py`, `services/test_model_b_scoring.py` | 15건 |
| FR-015 | Gemini 선별 + citation | `services/test_model_b_scoring.py::test_gemini_*` | 3건 |
| FR-017~018 | 모델 A·B 동시 표시 | `api/test_recommend_api.py` | TestRecommendDual |

### 6.2 NFR ↔ 테스트

| NFR | 요구사항 | 검증 |
|---|---|---|
| NFR-PERF-001 | 추천 응답 ≤ 10s | `recommend_service.py:53` wait_for + `test_quality_metrics::test_elapsed_p95` |
| NFR-PERF-002 | 모델 A·B 동시 호출 | `recommend_service.py:_safe` + `test_recommend_dual_concurrent` |
| NFR-PERF-003 | Gemini 8s 타임아웃 | `gemini_client.py:114` wait_for |
| NFR-EVAL-001 | 알레르기 노출 0% | `test_csr_allergy_leak_zero` (Hard Gate) + 골든셋 30건 |
| NFR-EVAL-002 | Gemini citation ≥ 95% | `test_gemini_hallucinated_ids_blocked` + `gemini_client.py:128` |
| NFR-SEC-001 | API 키 환경변수 격리 | `core/security.py:14-22` 부팅 가드 + .env.example |
| NFR-SEC-002 | bcrypt rounds=12 + JWT 32자+ | `core/security.py:23` 부팅 가드 + `BCRYPT_ROUNDS=12` 운영 |
| NFR-SEC-003 | 로그인 5회 실패 잠금 | `unit/test_rate_limit.py` (6건) |
| NFR-OPS-001 | /health 헬스체크 | `tests/test_health.py` + Docker HEALTHCHECK |
| NFR-MAINT-001 | 모델 A·B 독립 모듈 | services/ 분리 + ruff lint |

---

## 7. 결과 보고 형식 (Reporting)

### 7.1 CI 자동 보고
```
GitHub Actions:
  - backend: pytest -q + ruff check
  - frontend: npx tsc --noEmit
  → 실패 시 PR 머지 차단
```

### 7.2 평가 보고서 형식 (`scripts/evaluate_recommend.py` 출력)
```
==============================================================================
추천 시스템 신뢰성·성능 평가 보고서
==============================================================================
시나리오: 30건  (정답 정의된 시나리오: 30)

[정확도 메트릭] (학계 표준)
  Precision@10 (model A) : 0.628
  ...

[안전성·일관성 (NFR)]
  알레르기 누출 (NFR-EVAL-001) : 0건 (0.0%)
  ...

[NFR 임계값 검증]
  ✅ allergy_leak_rate: 0.000 ≤ 0.0
  ...

[종합] ✅ 전체 통과
```

### 7.3 시나리오별 상세 표 (CI 아티팩트)
시나리오 ID · 설명 · P@10 · MRR · NDCG · leak 여부 · 응답 ms

---

## 8. 위험 및 완화 (Risk & Mitigation)

| 위험 | 영향 | 완화 방안 |
|---|---|---|
| Gemini API 외부 의존성 (네트워크·할당량) | 추천 이유 미제공 | mock으로 격리 + 8s 타임아웃 + final_score 폴백 |
| 시드 35건 → 알레르기 필터 후 후보 고갈 | 빈 추천 | Sprint 1 DA-301 (50+ 확장), `test_empty_response` 안내 |
| BCRYPT_ROUNDS=4 (테스트) vs 12 (운영) 차이 | 테스트가 실 보안 미반영 | 운영 .env에서 12 강제 + 부팅 가드 |
| 동의어 매핑 오류 (두유→우유 등) | 의미 충돌 가능 | `test_synonym_map_edge.py` xfail 추적 |
| Gemini 환각 ID | 화이트리스트 위반 | `citation_ids` 검증 (NFR-EVAL-002) |

---

## 9. 실행 명령 (Quick Reference)

```bash
# 전체 백엔드 테스트
cd backend && python -m pytest tests/ -q

# 단위 테스트만
python -m pytest tests/unit tests/services -q

# 통합 (API) 테스트
python -m pytest tests/api -q

# E2E
python -m pytest tests/e2e -q

# 회귀·메트릭
python -m pytest tests/regression -q

# 평가 보고서 (사람용)
python scripts/evaluate_recommend.py

# 실험 (model A/B 비교)
python scripts/experiment_recommend.py

# 정적 분석
ruff check .
cd ../frontend && npx tsc --noEmit
```

---

## 10. 변경 이력 (Change Log)

| 버전 | 일자 | 내용 |
|---|---|---|
| 1.0 | 2026-05-27 | 초안 작성 — 182 테스트 함수 / 5 디렉토리 / IEEE 829 표준 적용 |

---

## 부록 A. 학계 출처 (References)

- Shani, G. & Gunawardana, A. (2011). "Evaluating Recommendation Systems." *Recommender Systems Handbook*, Springer.
- Järvelin, K. & Kekäläinen, J. (2002). "Cumulated gain-based evaluation of IR techniques." *ACM Trans. on Information Systems*.
- Castells, P., Hurley, N.J., & Vargas, S. (2022). "Novelty and Diversity in Recommender Systems." *Recommender Systems Handbook* 3rd ed.
- Microsoft Recommenders: https://github.com/microsoft/recommenders
- IEEE Std 829-2008 — Standard for Software and System Test Documentation
- ISO/IEC/IEEE 29119 — Software Testing standards

## 부록 B. 결함 발견 & 수정 추적 (Defect History)

| ID | 발견일 | 위치 | 심각도 | 상태 | 수정 commit |
|---|---|---|---|---|---|
| D-01 | 2026-05-22 | model_a/b expand_allergies 미연결 | CRITICAL | ✅ 해결 | ab6b6bf |
| D-02 | 2026-05-22 | contains_all 양념 비일관 | CRITICAL | ✅ 해결 | ab6b6bf |
| D-03 | 2026-05-22 | 코사인 country/theme ordinal 왜곡 | CRITICAL | ✅ 해결 | ab6b6bf |
| D-04 | 2026-05-22 | Gemini citation 자기인용 폴백 | CRITICAL | ✅ 해결 | ab6b6bf |
| D-05 | 2026-05-22 | gather 한쪽 실패 양쪽 폐기 | CRITICAL | ✅ 해결 | ab6b6bf |
| D-06 | 2026-05-22 | model_b 빈 냉장고 부족재료 반환 | HIGH | ✅ 해결 | ab6b6bf |
| D-07 | 2026-05-22 | PreferenceWizard 라벨 백엔드 불일치 | CRITICAL | ✅ 해결 | 428d700 |
| D-08 | 2026-05-22 | /api/ingredients/search 라우터 부재 | CRITICAL | ✅ 해결 | 428d700 |
| D-09 | 2026-05-22 | "어류" 알레르기 카테고리 미정의 | MAJOR | ✅ 해결 | 428d700 |
| D-10 | 2026-05-22 | 가짜 이메일 인증 모달 | MAJOR | ✅ 해결 (PR #8 jaewon) | 05b48e2 |
| D-11 | 2026-05-22 | Wizard 다중→단일 전송 미스리딩 | HIGH | ✅ 해결 | 0c4c6eb |
| D-12 | 2026-05-22 | Wizard Step 2 입력 검증 부재 | MEDIUM | ✅ 해결 | 0c4c6eb |
| D-13 | 2026-05-22 | 추천 0개 결과 안내 미흡 | MEDIUM | ✅ 해결 | 0c4c6eb |
