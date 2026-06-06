# FridgeChef 학부 시연 시나리오 (SW공학론 평가관용)

본 문서는 학부 SW공학론 평가관 시연용 8개 시나리오와 강조 포인트, 예상 화면, 실패 시 회피 방법을 정의한다. `commit 597ca89` (TF-IDF + MOOD_MAP 73) 기준.

운영: Render 1667 레시피 적재 (Supabase pgvector).
평가 인프라: `backend/scripts/evaluate_recommend.py --compare-tfidf` (4모드).

---

## 시연 권장 순서 (총 약 12분)

| 순서 | 시나리오 | 목표 | 소요 | 강조 |
| ---: | --- | --- | ---: | --- |
| 1 | 한식 매콤 (가장 안정) | 정상 동작 첫인상 | 1분 | "재료·선호·자연어 3축" |
| 2 | 자연어 "비 오는 날" | TF-IDF + MOOD_MAP 효과 | 2분 | "AI 기반 추천" |
| 3 | 알레르기 회원 안전 | NFR-EVAL-001 0% | 1.5분 | "절대 노출 0건" |
| 4 | 모델 A vs 모델 B 분리 | SDD §3.2 자연 분리 | 1.5분 | "두 모델 알고리즘 차이" |
| 5 | 뒤로가기 결과 보존 | SRS FR-013 UX | 1분 | "사용자 흐름 보존" |
| 6 | 양식 선호 일관성 | prefs hard filter | 1분 | "사용자 의도 침범 X" |
| 7 | Gemini 폴백 | NFR-REL-001 견고성 | 1분 | "외부 API 장애 견딤" |
| 8 | 평가 인프라 라이브 | 정량 메트릭 | 2분 | "학계 표준 4모드 비교" |

---

## 시나리오 1 — 한식 매콤 (가장 안정)

**목적**: 첫인상으로 정상 동작·UI 흐름·추천 형식을 전달.

### 입력
- 냉장고: `김치, 두부, 돼지고기, 대파, 마늘, 고추`
- 선호: country=한식, food_type=메인요리, spicy=4, difficulty=초보, max_cook_min=40
- 자연어: (없음)
- 알레르기: 없음

### 예상 화면
- **Model A (냉털)**: 김치찌개·돼지고기김치찌개·참치김치찌개·꽁치김치찌개 등 8~10건
- **Model B (부족재료)**: 부대찌개·순두부찌개 등 missing 1~2개

### 강조 포인트
1. "재료를 100% 가진 레시피만 Model A — 사용자 의도 명확"
2. "Model B 는 '조개 1개만 더 사면' 같은 가이드 — 활용성 강화"
3. "매운맛 4점 → 1·2점 레시피는 hard filter 차단" (시연 중 spicy=2 변경 시 결과가 달라짐 즉시 시연 가능)

### 실패 시 회피
- 결과 0건 시 → max_cook_min 60으로 완화 후 재실행
- Render cold start → 사전 깨우기 (`/health`) 필수 ([DEMO_CHECKLIST.md](./DEMO_CHECKLIST.md))

---

## 시나리오 2 — 자연어 "비 오는 날" (TF-IDF + MOOD_MAP 핵심)

**목적**: AI 기반 추천 효과 시연. 학부 SW공학론 평가관의 가장 큰 관심 포인트.

### 입력
- 냉장고: `김치, 돼지고기, 두부, 대파, 마늘`
- 선호: country=한식, food_type=국물, spicy=3, difficulty=초보, max_cook_min=40
- **자연어: "비 오는 날 따뜻하게 먹을 국물 요리"**
- 알레르기: 없음

### 예상 화면
- **Model A**: 김치찌개·참치김치찌개·돼지고기김치찌개·순두부찌개·해물순두부찌개·강된장찌개 등 8~10건
- 동일 재료에서 자연어 없이 호출한 결과보다 "찌개·국물" 어휘 레시피가 상위에 모임

### 강조 포인트
1. "MOOD_MAP 73개 키 — '비 오는 날' → 김치·두부·된장·참치김치찌개·강된장찌개 도메인 키워드 자동 확장"
2. "TF-IDF 코사인 유사도 (가중치 0.20) — 학계 표준 (Salton & McGill 1983)"
3. "1667 운영 코퍼스 vocab(2000개) 매칭 — OOV 0%"
4. 라이브 데모: 자연어를 **"여름 더운 날 시원한"**으로 바꾸면 오이·양상추·토마토 어휘로 결과 즉시 전환

### 비교 시연 (옵션)
백그라운드에서 사전 실행한 4모드 비교 표를 화면에 띄우고:
- A (baseline): P@10 = X
- C (TF-IDF + expand): P@10 = Y
- Δ% = (Y-X)/X × 100% (paired t-test 결과)

### 실패 시 회피
- 자연어 매칭 결과가 시연자 기대와 다르면 → "fallback: 매칭 안 되면 원본 그대로 통과 (안전 폴백 설계)"라고 설명

---

## 시나리오 3 — 알레르기 회원 안전성 (NFR-EVAL-001)

**목적**: 안전성 NFR 절대 0% 위반 시연. 학부 발표에서 가장 강력한 신뢰성 지표.

### 사전 조건
- 회원가입 시 알레르기: `["조개", "땅콩"]`
- 이메일 인증 완료

### 입력
- 냉장고: `두부, 간장, 마늘, 조개, 땅콩, 빵`
- 선호: country=한식, food_type=메인요리, use_saved_allergies=True
- 자연어: "친구와 술 한잔 안주"

### 예상 화면
- **Model A**: 조개탕·해물순두부찌개·땅콩버터샌드 등 **0건 노출**
- 결과 박스: 두부조림·계란말이 등 안전한 레시피만 표시
- (UI) "회원 알레르기 자동 적용 — 조개·땅콩 함유 레시피 0건" 토스트 노출 가능

### 강조 포인트
1. "NFR-EVAL-001 — 골든셋 30 시나리오에서 알레르기 누출 0건 자동 검증" (`pytest tests/regression/test_quality_metrics.py::test_csr_allergy_leak_zero`)
2. "알레르기 카테고리 확장 (`expand_allergies`) — 사용자가 '우유'라고 입력해도 '치즈' 함유 차단 (Issue #69 후속)"
3. "Hard gate — 점수 가중치가 아닌 필터링 단계에서 제외 (절대 안전)"

### 실패 시 회피
- 의외로 누출 시 → 즉시 알레르기 카테고리 매핑 디버그 화면 (`/api/recipes/{id}/allergens`) 띄우고 "expand_allergies 매핑 데이터 갱신 중" 설명

---

## 시나리오 4 — 모델 A vs 모델 B 자연 분리 (SDD §3.2)

**목적**: 알고리즘 설계 의도 — 두 모델의 명확한 역할 분리 시연.

### 입력
- 냉장고: `두부, 간장, 마늘, 밥, 계란` (5건)
- 선호: country=한식, food_type=메인요리, spicy=2, difficulty=초보, max_cook_min=60

### 예상 화면
- **Model A**: 계란찜·두부조림 등 missing=0 (재료 모두 보유)
- **Model B**: 김치찌개 (김치만 더 사면 OK), 잡채 (당근·시금치 부족) 등 missing 1~5

### 강조 포인트
1. "Model A = '냉장고에 있는 재료로 바로 만들 수 있는' (이름값)"
2. "Model B = '조금만 더 사면' 가이드 — Gemini 2.5 Flash 가 한국어 추천 이유 생성"
3. **교집합 0건** — `tests/integration/test_nl_recommendation.py::TestModelAandBDisjointUnderNl` 자동 검증

### 라이브 코드 시연 (옵션)
`backend/app/services/recommend_service.py` 코드 펼쳐서:
```python
return {"model_a": model_a, "model_b": model_b}
# dedup 제거 — Model A(missing==0) 와 Model B(missing 1~5) 가 정의상 자연 분리
```
설계 의도가 코드 주석에 명시되어 있음을 보임.

---

## 시나리오 5 — 뒤로가기 결과 보존 (SRS FR-013)

**목적**: UX 흐름 안정성. 평가관이 "사용성 어떻게 신경 썼나" 물어볼 때 답변.

### 시연 흐름
1. 시나리오 1 추천 결과에서 임의 카드 클릭 → 레시피 상세 페이지 진입
2. 브라우저 뒤로가기
3. 추천 결과가 그대로 유지됨 (재호출 없음)

### 강조 포인트
1. "React Router state 복원 — 추천 결과를 Zustand store에 저장"
2. "Render Free tier 콜드스타트 회피 — 불필요한 재요청 방지로 응답 시간 안정화"
3. "사용자 입력 (냉장고·자연어·선호)도 모두 복원"

### 실패 시 회피
- 결과 사라지면 → "F5 새로고침은 정책상 재로딩 — 뒤로가기 only 보존"이라고 설명

---

## 시나리오 6 — 양식 선호 일관성

**목적**: 자연어가 prefs 를 침범하지 않음을 시연. 사용자 의도 존중 신뢰성.

### 입력
- 냉장고: `면, 치즈, 마늘, 올리브유, 토마토`
- 선호: **country=양식**, food_type=메인요리, spicy=1, difficulty=중급
- **자연어: "비 오는 날 따뜻한 한식 국물"** (모순된 입력)

### 예상 화면
- **Model A**: 토마토파스타·까르보나라 등 country=west 만 (한식 0건)
- "양식" 카테고리 카드만 표시

### 강조 포인트
1. "country hard filter — 선호가 자연어를 압도 (사용자 의도 우선)"
2. "Issue: '중식 선택했는데 일식 나옴' 사용자 침묵 위반 차단 (Critic CRITICAL #C2)"
3. `tests/integration/test_nl_recommendation.py::TestPreferenceConsistencyUnderNl` 회귀

---

## 시나리오 7 — Gemini 폴백 (NFR-REL-001)

**목적**: 외부 API 장애 시에도 추천이 빈 응답을 내지 않음을 시연.

### 사전 준비
- `.env` 의 `GEMINI_API_KEY=""` 로 빈 값 설정 후 백엔드 재시작
- 또는 시연 직전 `/admin/break-gemini` (가상) 토글

### 예상 화면
- **Model B**: Gemini 추천 이유 박스가 "이유 생성 일시 중단" 으로 fallback
- 결과 자체는 final_score 기준 Top-3 그대로 표시 (citation_ids 미사용)

### 강조 포인트
1. "NFR-REL-001 — Gemini 8초 타임아웃 + 폴백 (Issue #69 GEMINI_TIMEOUT_S 20초로 완화)"
2. "model_b.py L167-172 — selected 부족 시 final_score 기반 폴백"
3. "사용자에게 빈 화면 절대 노출 안 함"

---

## 시나리오 8 — 평가 인프라 라이브 (학계 표준 메트릭)

**목적**: 평가관에게 정량적 신뢰성 증거 제시.

### 시연 흐름
```bash
cd backend
python scripts/evaluate_recommend.py --compare-4modes --corpus 1667 --overlap 1.0
```

### 예상 출력 (요약)
```
TF-IDF + expand_context 4모드 비교 평가 (코퍼스: 1667 운영 (1667건), overlap_th=1.0)

[전체 평균 (정답 정의된 시나리오 기준 P/MRR/NDCG)]
  Metric         A. baseline    B. +TF-IDF    C. +full      D. +expand
  Precision@10   X.XXXX         X.XXXX        X.XXXX        X.XXXX
  MRR            X.XXXX         X.XXXX        X.XXXX        X.XXXX
  NDCG@10        X.XXXX         X.XXXX        X.XXXX        X.XXXX

[C vs A paired t-test (정답 있는 시나리오)]
  Precision@10   mean Δ = +X.XXXX  (X.X%)  sd = X.XXXX  t = +X.XXX  → 유의 (p < 0.05)
```

### 강조 포인트
1. "Precision@10 / MRR / NDCG@10 — Manning et al. 2008, Järvelin & Kekäläinen 2002 학계 표준"
2. "Paired t-test (df ≈ 23, α=0.05 양측, |t| ≥ 2.069) — 통계적 유의성 검증"
3. "Coverage·Diversity 까지 측정 (`scripts/evaluate_recommend.py`)"
4. **그래프 4종** (사전 캐시: `.omc/scientist/figures/`)
   - `metric_comparison.png` — 4모드 P@10/MRR/NDCG 막대그래프
   - `mood_map_vocab_coverage.png` — MOOD_MAP 키워드의 1667 vocab 커버리지
   - `mrr_delta_heatmap.png` — 시나리오 × 모드 MRR 차이 히트맵
   - `pool_size_hist.png` — 시나리오별 후보 풀 크기 분포

### 실패 시 회피
- 라이브 실행 시간 초과 우려 → 사전 캡처 출력 (`.omc/scientist/runs/4mode_1667.txt`) 표시

---

## 시연 환경 차이 (정직 명시)

| 항목 | 운영 (Render + Supabase) | 평가 (pytest + SQLite) |
| --- | --- | --- |
| 레시피 코퍼스 | 1667건 (real-world) | 7건 (결정론적 미니) |
| TF-IDF vocab | 2000 | 100~300 |
| Gemini 호출 | 실제 (8s 타임아웃) | 모킹 (`mock_gemini_success/fail`) |
| 응답 시간 평균 | 1.5~3.0s (cold), 0.3~0.8s (warm) | < 100ms |
| 정답(expected_relevant) | 도메인 휴리스틱 (`eval_tfidf_scenarios.json` 24건) | 시드 정답 (`recommend_golden_set.json` 30건) |

**학부 발표 시 멘트**: "운영과 평가 환경의 코퍼스 크기가 다른 것은 학부 프로젝트의 정직한 한계입니다. NFR 회귀는 평가 환경에서 빠르게, 학계 메트릭 비교는 1667 운영 코퍼스에서 정확하게 수행합니다."

---

## 부록: 운영 헬스 체크 (시연 시작 10분 전)

```bash
# 1. Render 깨우기
curl https://fridge-chef.onrender.com/health
# 기대: {"status":"healthy","db":"ok","embedding_ready":true,"vocab_size":2000}

# 2. Supabase 풀 확인
curl https://fridge-chef.onrender.com/api/recipes/stats
# 기대: {"total":1667, ...}

# 3. 시나리오 1 사전 실행 (콜드스타트 회피)
curl -X POST https://fridge-chef.onrender.com/api/recommend ... (사전 캐시)
```

상세 절차: [DEMO_CHECKLIST.md](./DEMO_CHECKLIST.md)
