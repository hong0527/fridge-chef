# 학부 SW공학론 시연 운영 체크리스트

`docs/DEMO_SCENARIOS.md` 의 8개 시나리오를 무사히 시연하기 위한 운영 절차.
**평가 30분 전 시작 권장.**

기준: 운영 = Render Free Tier + Supabase Free Tier (Free Tier 콜드스타트 대응 핵심).

---

## T-30분: 인프라 깨우기 (가장 중요)

### 1. Render 깨우기 (Free Tier 15분 idle → cold sleep)

```bash
# health 엔드포인트 호출 — JSON 응답 확인
curl -s https://fridge-chef.onrender.com/health | jq

# 기대 응답:
# {
#   "status": "healthy",
#   "db": "ok",
#   "embedding_ready": true,
#   "vocab_size": 2000
# }
```

- `embedding_ready=false` 면 TF-IDF fit 미완료 → 30초 대기 후 재호출
- `db=error` 면 Supabase 도 깨우기 (다음 단계)

### 2. Supabase 깨우기 (Free Tier 7일 idle → pause)

- 대시보드 접속: https://supabase.com/dashboard/project/{PROJECT_ID}
- "Database" → "Connection pooling" 페이지 로드되면 깨어남
- 또는 SQL Editor 에서 `SELECT count(*) FROM recipes;` 실행 (1667 확인)

### 3. 프론트엔드 헬스 체크

- Vercel: https://fridge-chef.vercel.app/ 접속 → 첫 화면 1초 이내 로드
- 로컬 dev: `npm run dev` (이미 실행 중이면 reload 금지)

---

## T-20분: 시연 데이터 사전 캐시 (콜드스타트 회피)

### 각 시나리오를 1회씩 사전 실행

```bash
# 시나리오 1 — 한식 매콤
curl -X POST https://fridge-chef.onrender.com/api/recommend \
  -H "Authorization: Bearer $DEMO_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fridge_ingredients": ["김치","두부","돼지고기","대파","마늘","고추"],
    "preferences": {"country":"한식","food_type":"메인요리","spicy":4,"difficulty":"초보","max_cook_min":40,"diet":false,"use_saved_allergies":false}
  }' | jq '.model_a | length'
# 기대: 5~10

# 시나리오 2 — 자연어 비 오는 날
curl -X POST https://fridge-chef.onrender.com/api/recommend \
  -H "Authorization: Bearer $DEMO_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fridge_ingredients": ["김치","돼지고기","두부","대파","마늘"],
    "preferences": {"country":"한식","food_type":"국물","spicy":3,"difficulty":"초보","max_cook_min":40,"diet":false,"use_saved_allergies":false},
    "user_context": "비 오는 날 따뜻하게 먹을 국물 요리"
  }' | jq '.model_a[0].name'
# 기대: "김치찌개" 또는 그 변형

# 시나리오 3 — 알레르기 회원 (use_saved_allergies=true)
# ... (DEMO_TOKEN 은 알레르기 ["조개","땅콩"] 회원 토큰)

# 시나리오 5 — 뒤로가기 보존: 프론트엔드 수동 시연
```

### 사전 캐시 자동 스크립트 (옵션)

```bash
bash docs/scripts/demo_warmup.sh
# (스크립트가 없으면 위 curl 들을 묶어 작성)
```

---

## T-15분: 평가 인프라 사전 실행 (라이브 실패 회피)

### 시나리오 8 (4모드 비교) 사전 실행 + 출력 저장

```bash
cd /Users/honghwasu/softwareTeamProject/fridge-chef/backend
python scripts/evaluate_recommend.py --compare-4modes --corpus 1667 --overlap 1.0 \
  | tee /tmp/demo_4mode_output.txt
```

- 출력 길이가 길어 라이브 실행 시 시간 지연 → **사전 저장 후 cat 으로 표시**
- 그래프 4종 사전 export:
  - `.omc/scientist/figures/metric_comparison.png`
  - `.omc/scientist/figures/mood_map_vocab_coverage.png`
  - `.omc/scientist/figures/mrr_delta_heatmap.png`
  - `.omc/scientist/figures/pool_size_hist.png`
- 슬라이드에 image-embed

---

## T-10분: 회귀 테스트 패스 확인

```bash
cd /Users/honghwasu/softwareTeamProject/fridge-chef/backend

# 1. 단위 테스트 (NL 매칭)
pytest tests/unit/test_nl_matching.py tests/unit/test_context_expander.py -v --tb=short

# 2. 통합 테스트 (NL 추천)
pytest tests/integration/test_nl_recommendation.py -v --tb=short

# 3. 핵심 불변식 회귀
pytest tests/regression/test_recommend_invariants.py -v --tb=short

# 4. 품질 메트릭 (NFR 임계값)
pytest tests/regression/test_quality_metrics.py -v --tb=short
```

**전 항목 PASS 확인 후 시연 시작**. 실패 시 [긴급 대응](#긴급-대응-시연-중-장애) 절차.

---

## T-5분: 화면·툴 정돈

- [ ] 브라우저 탭 정리: 시연용 1개, README/SDD 1개, 슬라이드 1개
- [ ] 터미널 폰트 크게 (16pt+), 다크 테마 (가독성)
- [ ] 알림 OFF (Slack/Discord/카카오)
- [ ] 네트워크: 학교 와이파이 vs 휴대폰 핫스팟 둘 다 준비
- [ ] 발표자 노트: `docs/DEMO_SCENARIOS.md` 사전 인쇄 또는 보조 화면
- [ ] 4모드 비교 출력: `/tmp/demo_4mode_output.txt` 미리 열어두기

---

## T-0: 시연 시작

[DEMO_SCENARIOS.md](./DEMO_SCENARIOS.md) 의 8개 시나리오 순서대로 진행.

### 시나리오 간 전환 시 체크
- [ ] 이전 결과 화면 캡처 (실패 시 증거)
- [ ] 자연어 입력 박스 비우기 (다음 시나리오 오염 방지)
- [ ] 알레르기 회원 시나리오 후 로그아웃 → 일반 회원 재로그인

---

## 긴급 대응 (시연 중 장애)

### 케이스 A: Render 5xx (cold sleep 재발)

```bash
# 1) 즉시 health 호출 → 30초 대기
curl https://fridge-chef.onrender.com/health

# 2) 그래도 안 되면 로컬 docker fallback
cd /Users/honghwasu/softwareTeamProject/fridge-chef
docker compose up -d backend
# 프론트엔드의 API_BASE 를 로컬로 임시 변경 (.env.local)
# VITE_API_BASE=http://localhost:8000
```

**평가관 멘트**: "Free Tier 콜드스타트로 cold sleep 발생, 로컬 인스턴스로 즉시 전환합니다. 운영 배포 시에는 keep-alive cron job 으로 회피합니다."

### 케이스 B: Gemini 타임아웃 (이유 박스 비어있음)

- 즉시 시나리오 7 ("Gemini 폴백") 으로 전환
- "NFR-REL-001 설계대로 final_score 기반 폴백이 동작 중입니다" 멘트
- 평가관에게 오히려 견고성 강점으로 활용

### 케이스 C: 자연어 매칭 결과 의외

- "MOOD_MAP 73개 키 중 매칭되지 않으면 원본 그대로 사용하는 안전 폴백입니다" 설명
- 즉시 시나리오 2 의 "비 오는 날" 입력으로 회귀

### 케이스 D: 알레르기 누출 (절대 발생 불가지만)

- 즉시 시연 중단, "NFR-EVAL-001 회귀 테스트 결과 0건이며, 본 케이스는 추후 분석 후 수정 보고드리겠습니다" 정직 멘트
- pytest 회귀 결과 화면 띄워 평소 0건 입증
- 시나리오 3을 시나리오 1로 대체 진행

### 케이스 E: 네트워크 끊김

- 휴대폰 핫스팟 전환 (사전 준비)
- 그래도 안 되면 로컬 docker + 사전 캡처 화면으로 시연 (사진 + 멘트)

---

## 시연 종료 후 체크

- [ ] 평가관 질문 답변 노트
- [ ] 결과 화면 캡처 폴더 정리 (`docs/demo_captures/{date}/`)
- [ ] 발견된 결함 → GitHub Issue 생성
- [ ] Render·Supabase 사용량 확인 (Free Tier 한도 초과 여부)
- [ ] 평가 후 자동 cron 깨우기 OFF (필요 시)

---

## 부록 1: 운영 vs 평가 환경 차이 멘트 (정직성)

평가관이 "운영과 시연 환경이 다른가?" 물어보면:

> "네, 정직하게 차이가 있습니다. 운영은 Supabase 1667 레시피와 실제 Gemini 호출을 사용하고, pytest 단위·통합 테스트는 SQLite 인메모리와 7건 결정론적 카탈로그를 사용합니다. 학계 메트릭 (Precision@10, MRR, NDCG) 은 운영 코퍼스에서, 회귀 테스트는 평가 환경에서 측정합니다. 이 차이는 `docs/EVALUATION_REPORT.md` §7 에 명시했습니다."

## 부록 2: 시연 사전 회귀 단일 명령

```bash
cd /Users/honghwasu/softwareTeamProject/fridge-chef/backend && \
  pytest \
    tests/unit/test_nl_matching.py \
    tests/unit/test_context_expander.py \
    tests/integration/test_nl_recommendation.py \
    tests/regression/test_recommend_invariants.py \
    tests/regression/test_quality_metrics.py \
    -v --tb=short
```

전 항목 PASS = 시연 안전.

## 부록 3: 운영 keep-alive (시연 1시간 전부터)

```bash
# 1분마다 /health 호출하여 cold sleep 방지
while true; do
  curl -s https://fridge-chef.onrender.com/health > /dev/null
  sleep 60
done
```

(시연 종료 후 Ctrl+C 로 중지)
