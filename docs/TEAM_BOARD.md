# FridgeChef 팀 분담 보드 — Sprint 1·2

> 작성일: 2026-05-18
> 기준: SRS v1.10 + 현재 `dev` 브랜치 코드 상태
> 팀: 김재원, 윤도훈, 홍록경, 홍화수 (4인)
> 가용: 1인당 주 8~12h · 2주 스프린트

---

## 0. 분담 원칙

- 1인 1트랙 (역할별 책임 명확화). 페어 작업 권장.
- 모든 작업은 `feat/<role>-<scope>` 브랜치 → `dev` PR → 1인 리뷰 + CI 통과 → squash merge.
- `main`은 릴리스 시에만 사용.
- 모든 PR에 `AI Usage` 섹션 필수 (`.github/PULL_REQUEST_TEMPLATE.md` 참고).

## 0.1 역할 매핑 (제안 — 변경 가능)

| 이름 | 역할 | 주 담당 |
|---|---|---|
| 김재원 | PM + Backend | RecommendService·Auth·인프라 |
| 윤도훈 | Frontend | 5화면 + 신규 UC 화면 (즐겨찾기·리뷰·검색) |
| 홍록경 | Data | 레시피 시드 50+건, SYNONYM_MAP 확장, 알레르기 골든셋 |
| 홍화수 | QA | 통합 테스트, NFR-EVAL 회귀 자동화, E2E |

---

## 1. Sprint 1 (Week 1-2) — "미구현 UC 화면 완성"

### Backend (김재원)

| ID | 제목 | 의존 | 예상 | 수용 기준 | 관련 |
|---|---|---|---|---|---|
| BE-101 | 평점·리뷰 라우터 (POST/GET/PATCH/DELETE /api/ratings) | Alembic baseline | 6h | 1유저-1레시피 unique, 1-5 점수 + 500자 코멘트, JWT 인증 | FR-024, UC-08 |
| BE-102 | 즐겨찾기 라우터 (POST/GET/DELETE /api/favorites) | - | 4h | 단일 사용자 즐겨찾기 CRUD, 중복 방지 | UC-07 |
| BE-103 | 레시피 검색·필터 (GET /api/recipes?q=&max_cook=&diff=&diet=) | - | 5h | 키워드(name·whole_ingredients), 시간·난이도·식이 필터 | UC-09 |
| BE-104 | 알레르기 수정 API (PATCH /api/auth/me/allergies) | - | 3h | SYNONYM_MAP 정규화, JWT 인증 | FR-007, UC-05 |
| BE-105 | 자동완성 라우터 (GET /api/ingredients/search?q=) | - | 3h | SYNONYM_MAP 기반 prefix 매칭 8개 | FR-FRIDGE-03 |

### Frontend (윤도훈)

| ID | 제목 | 의존 | 예상 | 수용 기준 | 관련 |
|---|---|---|---|---|---|
| FE-201 | 마이페이지 화면 (`app/mypage/page.tsx`) | BE-104 | 4h | 알레르기 멀티셀렉트, 토스트 피드백 | UC-05 |
| FE-202 | 평점·리뷰 UI (레시피 상세 하단) | BE-101 | 5h | 별점 1-5, 코멘트 500자, 본인 리뷰 수정·삭제 | UC-08 |
| FE-203 | 즐겨찾기 토글 + 목록 화면 (`app/favorites/`) | BE-102 | 4h | 상세 화면 토글, 목록 그리드 | UC-07 |
| FE-204 | 검색 화면 (`app/search/page.tsx`) | BE-103 | 4h | 검색바 + 필터 칩 + 결과 그리드 | UC-09 |

### Data (홍록경)

| ID | 제목 | 의존 | 예상 | 수용 기준 | 관련 |
|---|---|---|---|---|---|
| DA-301 | 레시피 시드 50+건 큐레이션 | - | 6h | `db/seeds/sample_recipes.json` + INSERT 스크립트, 한식/양식 비율 60/40 | FR-DATA, NFR-EVAL |
| DA-302 | SYNONYM_MAP 100→200쌍 확장 | - | 4h | `backend/app/core/synonym_map.py` + `db/seeds/synonym_map.json` 동기화 | FR-037 |
| DA-303 | 레시피 image_url 추가 (Unsplash CC 50건) | DA-301 | 3h | 라이선스 표기 docs/IMAGE_CREDITS.md | UC-05 |

### QA (홍화수)

| ID | 제목 | 의존 | 예상 | 수용 기준 | 관련 |
|---|---|---|---|---|---|
| QA-401 | 알레르기 골든셋 50샘플 완성 | DA-301 | 6h | `tests/fixtures/allergy_golden_set.json` 50건, recall@10, NFR-EVAL-001 위반율 측정 자동화 | NFR-EVAL-001 |
| QA-402 | citation_id 화이트리스트 통합 테스트 | BE seed | 3h | model_b citation 검증 ≥95% 회귀 케이스 | NFR-EVAL-002 |
| QA-403 | 통합 테스트 JWT 헤더 재작성 | - | 4h | `test_recommend_api.py` 의 폐기된 X-User-Allergies 4건을 `test_jwt_token` 픽스처로 | - |
| QA-404 | docker-compose e2e 스모크 | DA-301 | 3h | `docker-compose up --build` → curl 회원가입~추천~상세 100% 통과 스크립트 | NFR-OPS-001 |

---

## 2. Sprint 2 (Week 3-4) — "통합·평가·릴리스 준비"

### Backend

| ID | 제목 | 의존 | 예상 |
|---|---|---|---|
| BE-201 | Alembic baseline 리비전 생성 + CI 단계 추가 | BE-101 머지 | 3h |
| BE-202 | Redis 캐싱 (추천 결과 TTL 600s) | - | 5h |
| BE-203 | /api/auth/me 엔드포인트 (프로필 조회) | - | 2h |
| BE-204 | 통합 로그 (구조화 JSON, request_id) | - | 3h |

### Frontend

| ID | 제목 | 의존 | 예상 |
|---|---|---|---|
| FE-301 | 토스트·에러 핸들링 통일 | - | 3h |
| FE-302 | 접근성 패스 (WCAG AA 4.5:1, 키보드 100%) | - | 5h |
| FE-303 | 반응형 360~1920px 검수 | - | 4h |
| FE-304 | 메인 랜딩 페이지 디자인 보강 | - | 4h |

### Data

| ID | 제목 | 의존 | 예상 |
|---|---|---|---|
| DA-401 | 레시피 100건 확장 (Sprint 1의 50건 추가) | - | 6h |
| DA-402 | 검수 — 알레르기 누락 0건, image_url 100% | DA-401 | 4h |

### QA

| ID | 제목 | 의존 | 예상 |
|---|---|---|---|
| QA-501 | Playwright E2E 3 시나리오 (가입→냉장고→추천→상세) | - | 8h |
| QA-502 | k6 부하 테스트 (50 RPS, p95 < 3s) | - | 4h |
| QA-503 | 데모 시연 스크립트 + 5분 영상 | 전 작업 | 4h |

---

## 3. 공통 규칙

### 3.1 브랜치
- `dev` ← `feat/<role>-<scope>` (예: `feat/be-ratings-router`)
- `main` ← `dev` (릴리스 시점만)

### 3.2 커밋 (Conventional Commits)
```
feat(be): 평점 라우터 추가
fix(fe): 즐겨찾기 토글 낙관적 업데이트 롤백 버그
test(qa): 알레르기 골든셋 50샘플 회귀 추가
docs: README 팀원 클론 가이드 보강
chore(ci): pip 캐시 추가
```

### 3.3 PR 체크리스트
1. CI 통과 (ruff + pytest + tsc + lint)
2. 관련 FR/NFR 코드 명시 (PR 본문)
3. AI Usage 섹션 작성
4. 리뷰어 1인 승인
5. squash merge

### 3.4 로컬 빠른 검증 (CI 동일)
```bash
# backend
cd backend && ruff check . && pytest -q

# frontend
cd frontend && npm install && npx tsc --noEmit && npm run lint
```

---

## 4. Day 0 즉시 액션 (각 1인)

| 액션 | 담당 | 소요 | 결과 |
|---|---|---|---|
| 클론 + .env 설정 + docker-compose up 확인 | 전원 | 30분 | http://localhost:3000 접속 확인 |
| Issue 라벨 생성 (bug/feat/chore/docs, area:be/fe/data/qa, prio:P0/P1/P2) | PM | 10분 | GitHub 라벨 |
| 위 티켓 14개(Sprint 1) Issue 등록 | PM | 20분 | 분담 가시화 |
| Sprint 1 첫 PR 환영 (각자 본인 트랙 1개 시작) | 전원 | 1h | dev로 PR |

---

## 5. 진척도 추적

GitHub Projects (또는 Issue 라벨) 활용. 각 카드:
- `Todo` → `In Progress` → `In Review` → `Done`
- 의존성 있는 카드는 GitHub Issue의 `closes #N` 표기

매주 금요일 30분 동기화 회의 권장 (디스코드/zoom).
