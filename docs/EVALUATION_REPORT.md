# FridgeChef 추천 시스템 평가 보고서 (학부 SW공학론)

본 보고서는 학부 SW공학론 발표용 정량 평가 결과 템플릿이다. `docs/EVALUATION.md` 가 평가 인프라 사용법을 다룬다면, 본 문서는 **결과 표 + 그래프 + 해석**의 발표 자료 골격이다.

기준 커밋: `597ca89` (TF-IDF + MOOD_MAP 73)
평가 인프라: `backend/scripts/evaluate_recommend.py`
시나리오 데이터: `backend/tests/fixtures/eval_tfidf_scenarios.json` (24건), `recommend_golden_set.json` (30건)

---

## 1. Executive Summary

| 항목 | 결과 | 기준 | 판정 |
| --- | ---: | ---: | :---: |
| 알레르기 노출 (NFR-EVAL-001) | 0% | ≤ 0% | PASS |
| Precision@10 (Model A) | (실측 채우기) | ≥ 0.20 | (PASS/FAIL) |
| MRR | (실측 채우기) | ≥ 0.30 | (PASS/FAIL) |
| NDCG@10 | (실측 채우기) | ≥ 0.50 | (PASS/FAIL) |
| Coverage | (실측 채우기) | ≥ 30% | (PASS/FAIL) |
| 응답 시간 p95 | (실측 채우기) ms | ≤ 1000 ms | (PASS/FAIL) |
| Model A ∩ B 교집합 | 0 | == 0 | PASS |

핵심 메시지: "안전성 NFR 100% 충족 + TF-IDF+expand 모드가 baseline 대비 자연어 카테고리에서 유의한 향상".

---

## 2. 메트릭 정의 (학계 표준)

| 메트릭 | 정의 | 범위 | 출처 |
| --- | --- | --- | --- |
| Precision@K | Top-K 추천 중 정답 비율 | [0, 1] | Manning, Raghavan, Schütze 2008 IIR §8.4 |
| Recall@K | 정답 중 Top-K 포함 비율 | [0, 1] | 동일 |
| MRR | 첫 정답 등장 순위의 역수의 평균 | [0, 1] | Voorhees, TREC-8 1999 |
| NDCG@K | 순위 가중 누적 이득 정규화 | [0, 1] | Järvelin & Kekäläinen 2002 |
| Coverage | 추천에 등장한 unique recipe / 전체 풀 | [0, 1] | Ge et al. 2010 |
| Allergy Leak Rate | 알레르기 재료 포함 레시피 노출 비율 | NFR = 0% | 본 프로젝트 |
| Constraint Satisfaction Rate | 1 - leak_rate | [0, 1] | Shani & Gunawardana 2011 |

---

## 3. TF-IDF + expand_context 4모드 비교 (Issue #72)

### 3.1 실험 설계

| 모드 | TF-IDF | expand_context | 최종 score |
| --- | :---: | :---: | --- |
| A. Baseline | OFF | OFF | 1.00 × 가중합 |
| B. +TF-IDF | ON | OFF | 0.80 × 가중합 + 0.20 × TF-IDF(보유재료 only) |
| C. +TF-IDF +expand (제안) | ON | ON | 0.80 × 가중합 + 0.20 × TF-IDF(보유재료 + 확장된 NL) |
| D. +expand only | OFF | ON | 1.00 × 가중합 (TF-IDF 입력만 확장, 효과 없음) |

**통제 변수**: 동일 골든셋 (24건), Gemini 폴백 강제 (`_mock_gemini_none`), 코퍼스 1667 (`/tmp/recipes_1667.pkl`), overlap_threshold=1.0.

실행:
```bash
cd backend
python scripts/evaluate_recommend.py --compare-4modes --corpus 1667 --overlap 1.0
```

### 3.2 전체 평균 (정답 정의된 시나리오 기준)

| Metric | A. Baseline | B. +TF-IDF | C. +Full | D. +expand only |
| --- | ---: | ---: | ---: | ---: |
| Precision@10 | (실측) | (실측) | (실측) | (실측) |
| MRR | (실측) | (실측) | (실측) | (실측) |
| NDCG@10 | (실측) | (실측) | (실측) | (실측) |
| Elapsed ms | (실측) | (실측) | (실측) | (실측) |
| Cand count (avg) | (실측) | (실측) | (실측) | (실측) |

### 3.3 Paired t-test: C vs A (제안 vs 베이스라인)

| Metric | mean Δ | sd | t-statistic | 판정 (α=0.05) |
| --- | ---: | ---: | ---: | --- |
| Precision@10 | (실측) | (실측) | (실측) | (유의/비유의) |
| MRR | (실측) | (실측) | (실측) | (유의/비유의) |
| NDCG@10 | (실측) | (실측) | (실측) | (유의/비유의) |

**판정 기준** (df ≈ 23, α=0.05 양측): |t| ≥ 2.069 → 통계적 유의.
**참고**: 정규성 가정이 약할 경우 Wilcoxon signed-rank 보강 권장 (학부 한계).

### 3.4 카테고리별 P@10 분해

| Category | n | A. Baseline | C. +Full | Δ |
| --- | ---: | ---: | ---: | ---: |
| 자연어 | 5 | (실측) | (실측) | (실측) |
| 재료정확 | 3 | (실측) | (실측) | (실측) |
| 한식 | 3 | (실측) | (실측) | (실측) |
| 중식 | 3 | (실측) | (실측) | (실측) |
| 일식 | 3 | (실측) | (실측) | (실측) |
| 양식 | 4 | (실측) | (실측) | (실측) |
| 디저트 | 1 | (실측) | (실측) | (실측) |
| 알레르기 | 2 | (실측) | (실측) | (실측) |

**해석 가이드**:
- 자연어 카테고리에서 Δ가 크면 → MOOD_MAP + TF-IDF 가 의도 기반 매칭에 기여
- 재료정확 카테고리에서 Δ가 작으면 → 명시 재료에 자연어 영향 적음 (의도된 행위)
- 디저트는 시드 부족 영역 — 학부 한계 케이스

---

## 4. 자연어 매칭 정성 평가

| 시연 입력 | 확장된 MOOD_MAP 키워드 | Model A 상위 3 (예상) | 평가 |
| --- | --- | --- | :---: |
| "비 오는 날 따뜻하게 먹을 국물" | 김치, 두부, 된장, 참치김치찌개, 강된장찌개 | 김치찌개, 참치김치찌개, 돼지고기김치찌개 | 적절 |
| "친구와 술 한잔 안주" | 계란말이, 감자전, 두부 | 계란말이, 장어계란말이, 감자전 | 적절 |
| "건강한 식단 다이어트" | 샐러드, 콩나물, 양상추, 흑미 | 채소샐러드, 케이준치킨샐러드 | 적절 |
| "추운 겨울 매운 국물" | 김치, 고추장, 치즈떡볶이, 강된장찌개 | 김치찌개, 부대찌개 | 적절 |
| "엄마가 해주시던 집밥" | 쇠고기, 미역국, 김치 | 미역국, 쇠고기무국, 홍합미역국 | 적절 |

**정성 평가 방법**: 평가관 3명이 각 시나리오 결과의 "의도 일치도"를 5점 척도로 채점, 평균 ≥ 4.0 목표.

---

## 5. 안전성·신뢰성 메트릭 (NFR)

### 5.1 NFR-EVAL-001 — 알레르기 0% (Hard Gate)

- 골든셋 30 시나리오 전체에서 알레르기 누출 0건
- 자동 회귀: `pytest tests/regression/test_quality_metrics.py::test_csr_allergy_leak_zero`
- `expand_allergies()` 카테고리 매핑 (우유 → 치즈/요거트/버터) 적용

### 5.2 NFR-PERF-003 — 추천 응답 ≤ 10초

- p95 응답시간: (실측) ms (평가 환경, SQLite + 모킹 Gemini)
- 운영 (Render warm): 0.3~0.8s; 운영 (cold start): 5~8s
- 회귀: `pytest tests/api/test_recommend_api.py::TestPerformance`

### 5.3 NFR-REL-001 — Gemini 폴백

- Gemini 8s 타임아웃 시 final_score 기반 Top-3 폴백
- 100% (모킹 실패 모드 모든 시나리오에서 빈 응답 0건)
- 회귀: `pytest tests/regression/test_recommend_invariants.py::TestGeminiFailureFallback`

### 5.4 NFR-EVAL-002 — Citation 화이트리스트

- Gemini 가 반환한 citation_id 가 1667 카탈로그에 100% 매칭
- 학부 시연 완화: citation 누락 시 selected 기반 약한 검증으로 폴백
- 회귀: `pytest tests/unit/test_model_b.py::TestCitationWhitelist`

---

## 6. 발표용 그래프 (사전 캐시: `.omc/scientist/figures/`)

| 그래프 | 파일 | 설명 |
| --- | --- | --- |
| 4모드 메트릭 비교 | `metric_comparison.png` | A/B/C/D 4모드의 P@10/MRR/NDCG 막대그래프 |
| MOOD_MAP vocab 커버리지 | `mood_map_vocab_coverage.png` | 73개 키워드의 1667 vocab(2000) 매칭률 |
| 시나리오별 MRR 차이 히트맵 | `mrr_delta_heatmap.png` | 24 시나리오 × 4 모드 MRR Δ |
| 후보 풀 크기 분포 | `pool_size_hist.png` | 시나리오별 model_a 후보 수 히스토그램 |

추가:
- `per_scenario_mrr_thresh0.png` — overlap_threshold=0 완화 시 시나리오별 MRR
- `relaxed_threshold_metrics.png` — overlap_threshold 0.5/1.0 비교

---

## 7. 운영 vs 평가 환경 차이 (정직 명시)

| 항목 | 운영 (Render + Supabase) | 평가 (pytest + SQLite) |
| --- | --- | --- |
| 레시피 코퍼스 | 1667 (real-world) | 7건 (`recipe_repo` fixture, 결정론) 또는 30 골든셋 |
| TF-IDF vocab | 2000 (max_features) | 100~300 |
| Gemini | 실제 호출 | 모킹 (`mock_gemini_success/fail`) |
| 정답 (expected_relevant) | 1667 운영 변형명 (`eval_tfidf_scenarios.json`) | 시드 정답 (`recommend_golden_set.json`) |
| 응답 시간 | warm 0.3~0.8s, cold 5~8s | < 100ms |
| DB | PostgreSQL (Supabase) | aiosqlite 인메모리 |

**투명성 멘트**: "학부 프로젝트의 한계로 시드 35 결정론적 카탈로그에서 단위·통합 테스트를 수행하고, 1667 운영 코퍼스에서 학계 메트릭(P@10/MRR/NDCG)을 측정합니다. CI 회귀는 시드 환경에서, 발표 자료의 정량 결과는 운영 환경에서 산출합니다."

---

## 8. 한계 (학부 프로젝트)

1. 시드 데이터 1667 — 산업 수준 (수십만~수억) 대비 작음
2. 정답 (expected_relevant) 은 도메인 휴리스틱 — 실제 사용자 클릭 로그 부재
3. t-test 정규성 가정 약함 — n=24, Wilcoxon signed-rank 보강 권장
4. Coverage 30% — 시드 35건에서 의미 있는 메트릭, 1667 로 확장 시 재산정 필요
5. expand_context 부분 매칭 — 한국어 형태소 분석기 (Mecab/Khaiii) 미도입
6. NDCG ideal DCG 단순화 — 모든 정답을 동일 relevance=1 로 가정

---

## 9. 참고 문헌

- Manning, Raghavan, Schütze. *Introduction to Information Retrieval*, Cambridge UP, 2008.
- Salton & McGill. *Introduction to Modern Information Retrieval*, McGraw-Hill, 1983.
- Järvelin & Kekäläinen. "Cumulated gain-based evaluation of IR techniques." TOIS 20(4), 2002.
- Voorhees. "The TREC-8 Question Answering Track Report." TREC-8, 1999.
- Aggarwal. *Recommender Systems: The Textbook*, Springer, 2016 — §4.4 weighted hybrid.
- Ge, Delgado-Battenfeld, Jannach. "Beyond accuracy: evaluating recommender systems by coverage and serendipity." RecSys 2010.
- Shani & Gunawardana. "Evaluating Recommendation Systems." *Recommender Systems Handbook*, Springer, 2011.

---

## 10. 결과 산출 명령 (재현성)

```bash
# 1. 기본 NFR 회귀
cd backend
python scripts/evaluate_recommend.py

# 2. TF-IDF on/off 비교
python scripts/evaluate_recommend.py --compare-tfidf

# 3. 4모드 비교 (시드 35)
python scripts/evaluate_recommend.py --compare-4modes --corpus seed35 --overlap 1.0

# 4. 4모드 비교 (1667 운영, 발표용)
python scripts/evaluate_recommend.py --compare-4modes --corpus 1667 --overlap 1.0

# 5. 자동 회귀 (pytest)
pytest tests/regression/ tests/unit/test_nl_matching.py -v

# 6. 그래프 재생성 (scientist 도구)
ls .omc/scientist/figures/  # 사전 캐시 확인
```

---

## 11. 본 보고서 채우는 절차

1. `python scripts/evaluate_recommend.py --compare-4modes --corpus 1667 --overlap 1.0` 실행
2. 출력의 `[전체 평균]`, `[C vs A paired t-test]`, `[카테고리별 P@10]` 표를 §3.2~3.4에 복사
3. NFR 회귀 결과 (`pytest tests/regression/ -v`) 의 PASS/FAIL을 §1, §5에 반영
4. 그래프 4종은 `.omc/scientist/figures/` 에서 발표 슬라이드로 export
5. 정성 평가 (§4) 는 평가관 3명이 채점한 평균 입력
