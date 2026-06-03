# 추천 시스템 평가 가이드 (학부 SW공학론)

본 문서는 fridge-chef 추천 시스템의 신뢰성·성능·AI 효과를 정량적으로 측정하기 위한 평가 인프라를 설명한다. 발표·보고서 자료로 사용.

## 1. 메트릭 정의 (학계 표준)

| 메트릭 | 정의 | 범위 | 출처 |
| --- | --- | --- | --- |
| **Precision@K** | Top-K 추천 중 정답(expected_relevant) 비율 | [0, 1] | Manning et al., *Introduction to IR* (2008) §8.4 |
| **Recall@K** | 정답 중 Top-K에 포함된 비율 | [0, 1] | 동일 |
| **MRR** (Mean Reciprocal Rank) | 첫 정답이 등장한 순위의 역수의 평균 — 첫 hit이 빠를수록 1에 가까움 | [0, 1] | Voorhees, TREC-8 (1999) |
| **NDCG@K** | Discounted Cumulative Gain의 정규화 — 상위 순위에 가중 | [0, 1] | Järvelin & Kekäläinen (2002) |
| **Coverage** | 추천에 등장한 unique recipe / 전체 풀 | [0, 1] | Ge et al. (2010) |
| **Allergy Leak Rate** | 알레르기 재료 포함 레시피 노출 비율 | NFR-EVAL-001 = 0% | 본 프로젝트 NFR |

## 2. 실행 방법

### 2.1 기본 평가 (전체 NFR 회귀)

```bash
cd backend
python scripts/evaluate_recommend.py
```

- 골든셋 30 시나리오(`backend/tests/fixtures/recommend_golden_set.json`)에 대해 model_a / model_b 호출
- Precision@10, Recall@10, MRR, NDCG@10, Coverage, Allergy Leak Rate, 응답시간 p95 계산
- NFR-EVAL-001(알레르기 0%), country 일치율 ≥ 60%, P@10 ≥ 0.20, MRR ≥ 0.30, p95 ≤ 1000ms 검증
- 미충족 시 exit code 1 (CI 회귀 게이트로 사용 가능)

### 2.2 TF-IDF on/off 비교 평가 (Issue #72 — AI 기반 추천 효과 측정)

```bash
cd backend
python scripts/evaluate_recommend.py --compare-tfidf
```

- 24 시나리오(`backend/tests/fixtures/eval_tfidf_scenarios.json`)에 대해 두 가지 모드로 추천 실행
  - **A. TF-IDF OFF** — 최종 score = `1.00 × 가중합(선호 + 재료 overlap)`
  - **B. TF-IDF ON (0.20)** — 최종 score = `0.80 × 가중합 + 0.20 × TF-IDF cosine(보유재료 + user_context vs 1667 코퍼스)`
- 동일 골든셋 입력 → 두 결과의 Precision@10 / MRR / NDCG@10 차이를 paired t-test로 비교
- 카테고리별(자연어·재료정확·한식·중식·일식·양식·디저트·알레르기) 평균 P@10 분해

### 2.3 실험 모드 (가중치 sweep — 옵션)

`backend/scripts/experiment_recommend.py`에서 다양한 가중치 조합 실험 가능. 본 평가 스크립트와 별개.

## 3. 시나리오 구성 — `eval_tfidf_scenarios.json`

24개 시나리오, 8개 카테고리:

| 카테고리 | 개수 | 특성 |
| --- | --- | --- |
| 자연어 | 5 | `"비 오는 날 따뜻하게"`, `"친구와 술 한잔 안주"`, `"건강한 식단"` 등 의도 강조 |
| 재료정확 | 3 | `"계란 1개로 가능한"`, 비빔밥 정확 재료 |
| 한식 | 3 | 집밥·분식·고급 한식 |
| 중식 | 3 | 짜장·마파두부·탕수육 |
| 일식 | 3 | 라멘·덮밥·초밥 |
| 양식 | 4 | 토마토파스타·카르보나라·스테이크·샐러드 |
| 알레르기 | 2 | 복합 알레르기 회귀 (정답 비어있어도 안전성 검증) |
| 디저트 | 1 | 시드 부족 영역 — 학부 한계 케이스 |

각 시나리오:

```json
{
  "scenario_id": "S001",
  "category": "자연어",
  "user_context": "비 오는 날 따뜻하게 먹을 국물 요리",
  "preferences": {"country":"한식","food_type":"국물","spicy":3,"difficulty":"초보","max_cook_min":40,"diet":false},
  "fridge_ingredients": ["김치","돼지고기","두부","대파","마늘"],
  "user_allergies": [],
  "expected_relevant": ["김치찌개","순두부찌개","된장찌개"],
  "notes": "비 오는 날 → 국물·찌개 우선"
}
```

`expected_relevant`는 레시피 이름(한글) 또는 recipe_id(`rNNN`) 둘 다 허용. 평가 스크립트가 자동으로 이름 → ID 매핑.

## 4. 발표용 결과 표 템플릿

### 4.1 전체 평균 비교

| Metric | A. TF-IDF OFF | B. TF-IDF 0.20 | Δ (B-A) | Δ% |
| --- | ---: | ---: | ---: | ---: |
| Precision@10 |  |  |  |  |
| MRR |  |  |  |  |
| NDCG@10 |  |  |  |  |
| Elapsed ms |  |  |  |  |

### 4.2 Paired t-test (정답 정의 시나리오 N건)

| Metric | mean Δ | sd | t-statistic | 결론 |
| --- | ---: | ---: | ---: | --- |
| Precision@10 |  |  |  | 유의 / 비유의 (α=0.05) |
| MRR |  |  |  |  |
| NDCG@10 |  |  |  |  |

**판정 기준 (df ≈ 23, α=0.05 양측):** |t| ≥ 2.069 → 통계적으로 유의한 차이.

### 4.3 카테고리별 P@10

| Category | n | A OFF | B ON | Δ |
| --- | ---: | ---: | ---: | ---: |
| 자연어 |  |  |  |  |
| 재료정확 |  |  |  |  |
| 한식 |  |  |  |  |
| 중식 |  |  |  |  |
| 일식 |  |  |  |  |
| 양식 |  |  |  |  |
| 디저트 |  |  |  |  |
| 알레르기 |  |  |  |  |

### 4.4 발표 멘트 가이드 (예시)

- **가설**: TF-IDF 코사인 유사도를 가중합 score에 0.20 가중치로 결합하면, 자연어 `user_context`가 강한 시나리오에서 Precision@10이 향상될 것이다.
- **검증**: 24개 시나리오를 동일 입력으로 두 번 평가 (모듈 monkey-patch로 score_query만 교체, 알고리즘 코드 변경 없음 → 통제 변수 확보).
- **결과**: 위 표의 Δ 값과 t-test 결과 인용.
- **해석**: 자연어 카테고리에서 Δ가 크고 재료정확 카테고리에서 Δ가 작으면 → TF-IDF는 의도 기반 매칭에 기여한다고 결론.

## 5. 통제 변수 보장

평가 스크립트는 다음 항목을 고정해 두 모드 간 차이가 **TF-IDF 가중치 변화에만 기인**하도록 보장:

1. **Gemini 폴백 강제** — `_mock_gemini_none`로 model_b의 Gemini 호출을 None 반환으로 우회 → 결정론
2. **동일 골든셋 입력** — `eval_tfidf_scenarios.json` 한 파일을 두 번 순회
3. **monkey-patch만 사용** — `emb_mod.score_query`를 빈 dict 반환 함수로 교체. model_a/model_b 알고리즘 코드는 한 줄도 수정하지 않음
4. **동일 코퍼스 / 동일 정규화** — repo·synonym_map·allergy_map 모두 공유

## 6. 한계 (학부 프로젝트)

- 시드 데이터 1667 레시피(시연용) — 산업 수준(수십만)에 비해 작음
- 정답(expected_relevant)은 도메인 휴리스틱 기반 — 사용자 클릭 로그 부재
- t-test는 정규성 가정 — n=24에서 단순 t 근사 사용 (Wilcoxon signed-rank가 더 robust)
- Coverage·Diversity 등 다양성 메트릭은 NFR 회귀에만 포함, 비교 모드에서는 제외

## 7. 참고 문헌

- Manning, Raghavan, Schütze. *Introduction to Information Retrieval*, Cambridge UP, 2008.
- Salton & McGill. *Introduction to Modern Information Retrieval*, McGraw-Hill, 1983 — TF-IDF.
- Järvelin & Kekäläinen. "Cumulated gain-based evaluation of IR techniques." *TOIS* 20(4), 2002 — NDCG.
- Aggarwal. *Recommender Systems: The Textbook*, Springer, 2016 — §4.4 weighted hybrid.
- Gunawardana & Shani. "A Survey of Accuracy Evaluation Metrics of Recommendation Tasks." *JMLR* 10, 2009.
