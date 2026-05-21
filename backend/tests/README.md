# FridgeChef Backend — Test Suite

엄밀한 통합 + API 기능 + 단위 + E2E 테스트.
SRS v1.10 (FR-001~016) + SDD v1.0 (UC-01~04) 정합 기준.

## 디렉토리 구조

```
tests/
├── conftest.py              # 공유 fixture (db_engine, async_client, test_user, test_jwt_token, test_fridge, mock_gemini_*)
├── api/                     # FastAPI 엔드포인트 통합 테스트 (httpx AsyncClient)
│   ├── test_auth_api.py     # FR-001~003, NFR-SEC-002·003
│   ├── test_fridge_api.py   # FR-008~010, SDD §3.2
│   ├── test_recommend_api.py# FR-011·014·016, NFR-PERF-002·003, NFR-EVAL-001·002, NFR-REL-001
│   └── test_recipes_api.py  # UC-04
├── unit/                    # 순수 알고리즘/유틸 단위 테스트
│   ├── test_synonym_map.py  # SDD §3.2 SYNONYM_MAP 100쌍
│   ├── test_model_a.py      # 모델 A 벡터/코사인/하드필터
│   └── test_model_b.py      # 모델 B 복합점수/Gemini 화이트리스트/폴백
├── e2e/                     # 페르소나 시나리오
│   └── test_user_journey.py # P1/P2/P3 페르소나
├── fixtures/
│   └── allergy_golden_set.json  # NFR-EVAL-001 골든셋 (10건 작성·40건 TODO)
└── README.md                # ← 본 문서
```

## 의존성 설치

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install aiosqlite        # SQLite 비동기 드라이버 (DB 테스트)
pip install email-validator  # Pydantic EmailStr 검증
```

## 실행 명령

### 전체 스위트
```bash
cd backend
pytest -v
```

### 레이어별 실행
```bash
# 단위 테스트만 (DB 불요, 가장 빠름)
pytest tests/unit/ -v

# API 통합 테스트 (SQLite 인메모리 DB)
pytest tests/api/ -v

# E2E 페르소나
pytest tests/e2e/ -v
```

### 특정 NFR/FR 마커로 필터링
```bash
# NFR-EVAL-001 알레르기 0% 검증만
pytest -v -k "allergy"

# NFR-PERF 성능 게이트만
pytest -v -k "PERF or performance or _under_"

# FR-011 모델 A 만
pytest -v tests/unit/test_model_a.py tests/api/test_recommend_api.py::TestRecommendBasic
```

### 커버리지
```bash
pip install pytest-cov
pytest --cov=app --cov-report=term-missing --cov-report=html
```

### 미구현 영역 확인
```bash
# xfail (구현 후 활성화 대기) 목록
pytest -v -rx | grep XFAIL
```

## NFR/FR ↔ 테스트 매핑표

| 요구사항       | 파일                              | 클래스/함수 |
|---------------|-----------------------------------|-------------|
| FR-001 회원가입| `api/test_auth_api.py`            | `TestSignup` |
| FR-002 로그인  | `api/test_auth_api.py`            | `TestLogin` |
| FR-003 비번재설정| `api/test_auth_api.py`         | `TestPasswordReset` (xfail) |
| FR-004~007 선호도| `api/test_recommend_api.py`    | `TestAllergyToggle` |
| FR-008~010 냉장고| `api/test_fridge_api.py`        | `TestFridgeCRUD` |
| FR-011 모델 A | `unit/test_model_a.py` + `api/test_recommend_api.py::TestRecommendBasic` | - |
| FR-014 모델 B | `unit/test_model_b.py` + `api/test_recommend_api.py` | - |
| FR-016 Gemini | `unit/test_model_b.py::TestGeminiFallback` | - |
| NFR-PERF-002 ≤3s| `api/test_recommend_api.py::TestPerformance` | `_under_3s_NFR_PERF_002` |
| NFR-PERF-003 ≤10s| `api/test_recommend_api.py::TestPerformance` | `_under_10s_NFR_PERF_003` |
| NFR-REL-001 Gemini 8s| `unit/test_model_b.py::TestGeminiFallback` + `api/test_recommend_api.py::TestGeminiFallback` | - |
| NFR-EVAL-001 알레르기 0%| `unit/test_model_a.py::test_golden_set_50_samples_allergy_zero` (10/50 채움) | + `e2e/test_user_journey.py::TestPersonaP2_Lee` |
| NFR-EVAL-002 citation 95%| `unit/test_model_b.py::TestCitationWhitelist` + `api/test_recommend_api.py::TestCitationWhitelist` | - |
| NFR-SEC-002 bcrypt+JWT| `api/test_auth_api.py::test_signup_stores_bcrypt_hash_not_plain` + `test_jwt_*` | - |
| NFR-SEC-003 5회 잠금| `api/test_auth_api.py::test_login_brute_force_lockout` (xfail) | - |
| SDD §3.2 정규화 | `unit/test_synonym_map.py` + `api/test_fridge_api.py::test_create_normalizes_synonym` | - |
| UC-01 회원가입 | `e2e/test_user_journey.py::TestPersonaP1_Kim` | - |
| UC-02 냉장고  | `e2e/test_user_journey.py::TestPersonaP1_Kim` | - |
| UC-03 추천    | `e2e/test_user_journey.py::TestPersonaP1_Kim` + `P2_Lee` + `P3_Park` | - |
| UC-04 레시피 상세| `api/test_recipes_api.py::TestRecipeDetail` | - |

## 미커버 / 후속 작업

- **golden set 40건 추가 채움**: `fixtures/allergy_golden_set.json` (현재 10건). 큐레이션 작업으로 50건 완성.
- **NFR-SEC-003 잠금 정책**: `auth_service` 에 Redis/DB 카운터 + TTL 30분 추가 후 xfail 해제.
- **FR-003 비밀번호 재설정**: 이메일 토큰 발송 라우터 추가 필요.
- **냉장고 중복/50개 정책**: `fridge_service` 정책 결정 후 xfail 해제.
- **recipes 라우터 warning 필드**: 사용자 알레르기 일치 시 warning 응답 스키마 확장.
- **NFR-EVAL-002 95% 정량 측정**: golden set 50건 채움 후 % 측정 로직 추가.

## Gemini 모킹 패턴

```python
# 성공 모킹
def my_test(mock_gemini_success): ...  # 자동 Top-3 그대로 반환

# 실패 모킹
def my_test(mock_gemini_fail): ...     # None 반환 → 폴백 트리거

# 커스텀
def my_test(monkeypatch):
    from app.services import model_b as mb_mod
    async def custom(candidates, ctx):
        return {"selected": [...], "reasons": [...], "citation_ids": [...]}
    monkeypatch.setattr(mb_mod, "gemini_select_top3", custom)
```
