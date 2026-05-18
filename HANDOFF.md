# FridgeChef — 개발 인수인계 가이드 (HANDOFF)

> 본 문서는 MVP 코드 베이스를 신규 개발자 4명이 즉시 분담할 수 있도록 정리한 **상세 개발 가이드**입니다.
> 본문에 등장하는 모든 명령어·경로·파일명은 현 리포지토리(`fridge-chef/`) 기준 실측값입니다.

---

## 1. 프로젝트 개요

**FridgeChef** — 냉장고에 있는 재료를 입력하면 AI가 두 가지 레시피를 동시에 추천하는 웹앱.

- **메인 주제**: 한국어 식재료 기반 듀얼 추천 + Gemini 2.5 Flash 자연어 설명
- **페르소나 3종** (SRS §2)
  1. **자취생** — 적은 재료로 빠른 한 끼 (모델 A 강함)
  2. **주부/주말 요리사** — 마트 가기 전 "한두 개만 더 사면" 다양화 (모델 B 강함)
  3. **건강 관리자** — 알레르기·저칼로리 필터 신뢰성 (NFR-EVAL-001 알레르기 0%)
- **이중 추천**
  - **모델 A — 냉털 추천**: 코사인 유사도 5차원 벡터(맵기·난이도·저칼로리·나라·테마) → 상위 10건
  - **모델 B — 부족재료 추천**: 복합점수(선호 0.7 + 보유율 0.2 + 부족페널티 0.1) → Gemini가 3건 선별 + 한국어 이유
- **기술 스택**: FastAPI + SQLAlchemy(asyncpg) + Postgres 15 + Redis 7 + Next.js 14(App Router) + Tailwind + Gemini 2.5 Flash, Docker Compose 단일 명령 실행

---

## 2. 폴더 구조 + 각 파일 역할

```
fridge-chef/
├── backend/                              FastAPI 백엔드
│   ├── app/
│   │   ├── main.py                       FastAPI 엔트리·CORS·/health·라우터 등록
│   │   ├── api/
│   │   │   ├── auth.py                   POST /api/auth/signup·/login
│   │   │   ├── fridge.py                 GET/POST/DELETE /api/fridge
│   │   │   ├── recommend.py              POST /api/recommend (듀얼 추천)
│   │   │   └── recipes.py                GET /api/recipes/{id} 등 상세 조회
│   │   ├── services/
│   │   │   ├── auth_service.py           bcrypt(work=12) 해시 + JWT 발급
│   │   │   ├── fridge_service.py         재료 CRUD + 정규화
│   │   │   ├── recommend_service.py      asyncio.gather()로 A·B 병렬, 10s 타임아웃
│   │   │   ├── model_a.py                냉털 코사인 유사도 추천
│   │   │   ├── model_b.py                복합점수 + Gemini 선별 추천
│   │   │   └── gemini_client.py          Gemini SDK 호출·JSON 파서·8s 타임아웃
│   │   ├── models/
│   │   │   ├── orm.py                    SQLAlchemy 모델(User·FridgeItem·Recipe·Rating)
│   │   │   ├── recipe.py                 Recipe 도메인 데이터클래스
│   │   │   ├── recipe_repository.py      메모리 카탈로그 + 화이트리스트
│   │   │   ├── user.py                   User 도메인
│   │   │   └── fridge.py                 FridgeItem 도메인
│   │   ├── schemas/
│   │   │   ├── auth.py                   SignupRequest·LoginRequest·TokenResponse
│   │   │   ├── fridge.py                 IngredientCreate·IngredientResponse
│   │   │   └── recommend.py              RecommendRequest·RecommendResponse
│   │   └── core/
│   │       ├── config.py                 Settings 데이터클래스(환경변수 로드)
│   │       ├── db.py                     AsyncSession 의존성 주입
│   │       ├── security.py               bcrypt 헬퍼
│   │       ├── auth.py                   get_current_user 의존성
│   │       └── synonym_map.py            100쌍 한국어 식재료 동의어 정규화 맵
│   ├── alembic/                          DB 마이그레이션 환경
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/                     리비전 파일(현재 비어있음)
│   ├── tests/
│   │   ├── conftest.py                   FastAPI TestClient 픽스처
│   │   ├── test_health.py                /health·/ 스모크 테스트
│   │   └── test_recommend.py             동의어·모델A·모델B·Gemini 파서·골든셋 placeholder
│   ├── pyproject.toml                    의존성·ruff·pytest 설정
│   ├── alembic.ini                       Alembic 설정
│   └── Dockerfile                        python:3.11-slim + uvicorn
├── frontend/                             Next.js 14 App Router
│   ├── app/
│   │   ├── layout.tsx                    루트 레이아웃 + 폰트 변수
│   │   ├── page.tsx                      랜딩 페이지
│   │   ├── globals.css                   Tailwind base + 커스텀 CSS 변수
│   │   ├── auth/page.tsx                 로그인·회원가입 화면
│   │   ├── fridge/page.tsx               냉장고 재료 입력 화면
│   │   ├── recommend/page.tsx            듀얼 추천 결과 화면
│   │   └── recipe/[id]/page.tsx          레시피 상세·평점 화면
│   ├── components/
│   │   ├── Brand.tsx                     브랜드 로고
│   │   ├── Button.tsx                    버튼 컴포넌트
│   │   ├── FridgeChip.tsx                재료 칩
│   │   ├── Modal.tsx                     모달
│   │   ├── PreferenceWizard.tsx          선호도 위저드
│   │   ├── RecipeCard.tsx                레시피 카드
│   │   └── Toast.tsx                     토스트 알림
│   ├── lib/
│   │   ├── api.ts                        axios 기반 API 클라이언트
│   │   ├── synonyms.ts                   프론트 측 정규화 미러
│   │   └── cn.ts                         clsx 래퍼
│   ├── tailwind.config.ts                cream·clay·gochu·herb·mustard 팔레트
│   ├── next.config.js                    Next 설정
│   ├── package.json                      next 14.2.5·react 18·axios·framer-motion
│   └── Dockerfile                        Node 20 + next start
├── db/
│   ├── migrations/001_init.sql           users·fridge_items·recipes·ratings 초기 스키마
│   └── seeds/
│       ├── synonym_map.json              동의어 시드(프론트·QA 공유용)
│       └── sample_recipes.json           샘플 레시피 데이터(30+건 목표)
├── docs/
│   ├── SRS_v1.10_1차완성본.pdf            요구사항 명세
│   ├── SRS_v1.10_1차완성본.docx
│   ├── SDD_v1.0_공유용.pdf                설계 명세
│   └── SDD_v1.0_공유용.docx
├── .github/
│   ├── workflows/ci.yml                  pytest + ruff + tsc + lint
│   └── PULL_REQUEST_TEMPLATE.md          AI Usage 섹션 필수
├── docker-compose.yml                    4서비스(postgres·redis·backend·frontend)
├── .env.example                          환경변수 템플릿
├── CONTRIBUTING.md                       브랜치·커밋 컨벤션
├── LICENSE                               MIT
└── README.md                             프로젝트 개요
```

---

## 3. 로컬 실행 가이드 (단계별)

### 3.1 사전 요구사항

| 도구 | 최소 버전 | 비고 |
|---|---|---|
| Docker Desktop | 24+ | compose v2 내장 |
| Python | 3.11+ | `backend/.python-version` 참조 |
| Node.js | 20+ | `npm` 동봉 |
| Git | 2.40+ | LFS 미사용 |

### 3.2 Gemini API 키 발급

1. <https://aistudio.google.com/app/apikey> 접속 (구글 계정 로그인)
2. **Create API key** → **Create API key in new project** 클릭
3. 생성된 키 복사 (예: `AIzaSy...`)
4. Free tier로 모델 `gemini-2.5-flash` 호출 가능

### 3.3 환경변수 설정

```bash
cd fridge-chef
cp .env.example .env
```

`.env` 파일을 열어 다음 4개를 채우세요.

```bash
GEMINI_API_KEY=AIzaSy_여기에_발급받은_키
JWT_SECRET=$(openssl rand -hex 32)   # 강력한 랜덤 문자열
DATABASE_URL=postgresql+asyncpg://fridgechef:fridgechef@localhost:5432/fridgechef
REDIS_URL=redis://localhost:6379/0
```

> `JWT_SECRET` 은 NFR-SEC-002 준수를 위해 32바이트 이상 권장.
> docker-compose 실행 시 `DATABASE_URL`/`REDIS_URL`은 컨테이너 내부에서 `postgres`/`redis` 호스트로 자동 오버라이드됩니다.

### 3.4 docker-compose 실행

```bash
docker-compose up --build
```

기동 순서: **postgres → redis (healthcheck) → backend → frontend**.
첫 빌드는 약 3~5분 (Python/Node 의존성 설치). 이후 캐시 적용으로 30초 내외.

### 3.5 첫 실행 검증

별도 터미널에서 아래 3개를 순서대로 실행하세요.

```bash
# (1) 백엔드 헬스체크
curl -s http://localhost:8000/health
# 기대: {"status":"ok","version":"1.0.0"}

# (2) 회원가입
curl -s -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@test.com","password":"Test1234!","nickname":"앨리스","allergies":[]}'
# 기대: 201 + {"id":1,"email":"alice@test.com",...}

# (3) 로그인 → JWT 받기
curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@test.com","password":"Test1234!"}'
# 기대: {"access_token":"eyJ...","expires_in":86400,"token_type":"bearer"}
```

프론트엔드는 <http://localhost:3000> 접속, Swagger UI는 <http://localhost:8000/docs>.

### 3.6 개별 개발 모드 (핫리로드)

```bash
# 백엔드
cd backend
pip install .[dev]
JWT_SECRET=dev-secret uvicorn app.main:app --reload

# 프론트엔드
cd frontend
npm install
npm run dev
```

---

## 4. 개발 워크플로우

### 4.1 브랜치 전략 (GitHub Flow + dev)

- `main` — 배포 가능 상태만. 직접 푸시 금지.
- `dev`  — 통합 브랜치. 모든 feature PR은 `dev` 로 머지.
- 작업 브랜치:
  - `feat/<scope>-<설명>` 예: `feat/recommend-model-a`
  - `fix/<scope>-<설명>`  예: `fix/fridge-normalize-bug`
  - `chore/<설명>`        예: `chore/ci-cache-pip`

### 4.2 커밋 컨벤션 (Conventional Commits)

```
<type>(<scope>): <subject>

[optional body]
[optional footer]
```

허용 type: `feat | fix | docs | refactor | test | chore | perf | ci | style`

```bash
git commit -m "feat(recommend): 모델 A 냉털 코사인 유사도 구현"
git commit -m "fix(fridge): 동의어 정규화에서 None 처리"
git commit -m "chore(ci): pip 캐시 추가로 CI 30% 단축"
```

### 4.3 PR 절차

1. 브랜치 작업 → 본인 원격으로 푸시
2. `gh pr create --base dev` 또는 GitHub UI 에서 PR 생성
3. **`.github/PULL_REQUEST_TEMPLATE.md`** 의 다음 섹션을 반드시 채울 것
   - 변경 요약 (1~3줄)
   - 관련 SRS/SDD 항목 (`FR-XXX`, `NFR-XXX-NNN`)
   - 체크리스트 (pytest, tsc, NFR 주석, .env.example 갱신)
   - **AI Usage** — 본 프로젝트 필수 정책
   - 테스트 결과 (명령어 + 결과)
   - 리스크 / 후속 작업
4. 리뷰어 1인 이상 승인 후 squash merge
5. `dev → main` 머지는 릴리스 시점에만 수동 진행

### 4.4 AI 활용 로그 (PR 마다 필수)

본 프로젝트는 학습 목적이며 다수의 AI 도구를 사용합니다. 모든 PR에서 다음을 명시하세요.

```markdown
## AI Usage
- 도구: Claude Code (Opus 4.7)
- 모델/버전 + 사용 일자
- 무엇을 생성·수정했는가 (예: model_a.py 초안 + pytest 케이스 3건)
- 사람이 직접 검증한 범위 (예: 모든 pytest 결과·docker compose up 실행 본인 확인)
```

> 미기재 PR 은 머지 거부 사유입니다.

---

## 5. 코드 컨벤션

### 5.1 Python (backend)

```bash
cd backend
ruff check .          # lint (E·F·I·W·UP·B 규칙, line-length 100)
pytest -q             # 단위 테스트 (asyncio_mode=auto)
```

- `pyproject.toml` 에 정의된 ruff 규칙 통과 필수
- 타입힌트 권장 (`from __future__ import annotations` 사용 중)
- 공개 함수에는 한국어 docstring 허용
- NFR 추적 주석: `# NFR-PERF-001`, `# NFR-EVAL-001` 형태로 표시
- 변수·함수명은 영문 snake_case, 주석은 한국어 OK

> `black` 은 본 리포에 명시 설치되지 않았습니다. `ruff format` 사용 시 팀 합의 후 도입.

### 5.2 TypeScript (frontend)

```bash
cd frontend
npm run lint          # next lint (eslint-config-next)
npx tsc --noEmit      # 타입체크
```

- ESLint 위반 0 + tsc 에러 0 필수
- 컴포넌트는 함수형·camelCase, 파일명은 PascalCase
- `lib/cn.ts` 의 `cn()` 사용해 클래스 합성

> Prettier·Vitest 는 본 리포에 아직 미설치 상태입니다. 도입 시 `package.json` devDependencies 와 CI 워크플로우(`.github/workflows/ci.yml`) 동시 갱신 필요.

---

## 6. 핵심 모듈 가이드

### 6.1 `backend/app/services/model_a.py` — 냉털 추천

SDD §3.2 시퀀스에 따른 6단계:

1. `normalize_list()` — SYNONYM_MAP 정규화
2. **알레르기 하드컷** — `r.allergens ∩ allergies ≠ ∅` 이면 즉시 제외 (NFR-EVAL-001)
3. **재료 포함 필터** — `_contains_all(fridge ⊇ recipe)` — 모든 재료 보유해야 통과
4. **조리시간 필터** — `r.cook_min > preferences.max_cook_min` 제외
5. **코사인 유사도** — 5차원 벡터 `[맵기/5, 난이도/3, 저칼로리, 나라코드, 테마코드]`
6. **상위 K 반환** — 점수 desc, 동점 시 `cook_min` asc, `TOP_K_MODEL_A=10`

### 6.2 `backend/app/services/model_b.py` — 부족재료 + Gemini

1~2. 정규화 + 알레르기·조리시간 필터 (모델 A와 동일)
3. **`_analyze_ingredients()`** — 보유/부족 재료 분류
4. **소프트 필터** — `len(missing) ≤ MISSING_INGREDIENTS_MAX(기본 5)`
5. **복합 점수** — `pref_sim×0.7 + have_ratio×0.2 + missing_penalty×0.1`
6. **상위 10건 사전선별** → `gemini_select_top3()` 호출
7. **citation_id 화이트리스트 검증** (NFR-EVAL-002)
8. **폴백** — Gemini 실패·타임아웃·검증 실패 시 `final_score` 기반 Top-3, `reason=""`

`gemini_client.py` 동작:

- `temperature=0.0`, `response_mime_type="application/json"` 으로 결정론 호출
- `asyncio.wait_for(..., timeout=GEMINI_TIMEOUT_S=8.0)` 타임아웃 가드
- 응답 파서가 코드펜스(```json ... ```) 제거 + `{...}` 추출 + 키 보정

### 6.3 `backend/app/core/synonym_map.py` — 100쌍 동의어 정규화

`SYNONYM_MAP: dict[str, str]` 에 약 100개 한국어 식재료 별칭이 등록되어 있습니다.
대표 카테고리: 파/양파·고추·마늘·생강·치즈·두부·계란·고기(닭/돼지/소)·해산물·잎채소·뿌리·버섯·면·쌀·장류·기름·유제품.

```python
from app.core.synonym_map import normalize, normalize_list

normalize("쪽파")          # → "대파"
normalize("청양고추")       # → "고추"
normalize("당근")           # → "당근"  (매핑 없으면 원본)
normalize_list(["쪽파", "대파", "양파"])  # → ["대파", "양파"]  (중복 제거·순서 보존)
```

**알레르기 비교 전에 반드시 같은 정규화를 거쳐야** NFR-EVAL-001(알레르기 노출 0%) 가 보장됩니다.

---

## 7. 테스트 실행 가이드

### 7.1 백엔드 단위 테스트

```bash
cd backend
pytest -q                       # 전체 실행
pytest tests/test_recommend.py -q
pytest -k "allergy" -v          # 알레르기 관련만
```

현재 커버 범위: 동의어 정규화 3건, 모델 A 3건, 모델 B 3건(Gemini 모킹·폴백·화이트리스트), 듀얼 동시실행 1건, Gemini 파서 3건, 골든셋 placeholder 1건.

### 7.2 프론트엔드 검증

```bash
cd frontend
npm run lint
npx tsc --noEmit
```

### 7.3 E2E 시나리오 (수동)

```bash
# 1. 회원가입
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"e2e@test.com","password":"E2eTest1!","nickname":"테스터","allergies":["계란"]}'

# 2. 로그인 → TOKEN 변수 보관
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"e2e@test.com","password":"E2eTest1!"}' | jq -r .access_token)

# 3. 냉장고 재료 추가
curl -X POST http://localhost:8000/api/fridge \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"raw_name":"두부","quantity":"1모"}'

# 4. 듀얼 추천
curl -X POST http://localhost:8000/api/recommend \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "fridge_ingredients":["두부","간장","마늘"],
    "preferences":{
      "spicy":2,"difficulty":"초보","max_cook_min":30,
      "country":"한식","food_type":"메인요리",
      "use_saved_allergies":true,"user_context":"퇴근 후 빠르게"
    }
  }'
```

기대: `model_a` 0~10건, `model_b` 0~3건. 알레르기 `계란` 포함 레시피는 두 리스트 모두 0건이어야 함.

---

## 8. 디버깅 가이드

### 8.1 FastAPI Swagger UI

- <http://localhost:8000/docs> — 모든 라우터·스키마 인터랙티브 호출
- 좌측 상단 **Authorize** 버튼에 `Bearer <JWT>` 넣으면 인증 라우터 직접 시험 가능
- ReDoc 버전은 <http://localhost:8000/redoc>

### 8.2 DB 직접 조회

```bash
# Postgres (docker-compose 실행 중)
docker exec -it fridgechef-postgres psql -U fridgechef -d fridgechef

# 주요 조회
SELECT id, email, nickname, allergies FROM users LIMIT 10;
SELECT user_id, raw_name, normalized_name FROM fridge_items ORDER BY id DESC LIMIT 20;
SELECT recipe_id, name, allergens FROM recipes LIMIT 10;
```

### 8.3 Gemini 응답 로깅

`backend/app/services/gemini_client.py` 의 `_logger` 가 `app.services.gemini_client` 채널로 경고를 남깁니다.

```bash
# 백엔드 로그 실시간
docker logs -f fridgechef-backend

# 또는 개발 모드에서 디버그 레벨 활성화
LOG_LEVEL=DEBUG uvicorn app.main:app --reload --log-level debug
```

수동 확인:

```python
# python REPL 에서
import asyncio
from app.services.gemini_client import gemini_select_top3
asyncio.run(gemini_select_top3([
    {"recipe_id":"t001","name":"간장계란밥","cook_min":10,"have":["밥"],"missing":["계란"],"final_score":0.7}
], user_context="비오는 날"))
```

---

## 9. 배포 가이드 (1차 완성 시)

### 9.1 Docker 빌드 (단일 이미지)

```bash
# 백엔드
docker build -t fridgechef-backend:1.0.0 ./backend

# 프론트엔드
docker build -t fridgechef-frontend:0.1.0 ./frontend
```

### 9.2 환경별 .env 분리

```
.env.local       # 개발자 PC (Git ignore)
.env.staging     # 스테이징 환경 변수
.env.production  # 운영 환경 (Secret Manager 권장)
```

`docker-compose.yml` 의 `${VAR:-default}` 패턴이 미설정 시 기본값으로 폴백합니다. 운영 배포 시 `JWT_SECRET`/`GEMINI_API_KEY` 는 **반드시 빈 기본값을 거부**하도록 진입점에서 가드 추가 필요.

### 9.3 Fly.io 배포 (백엔드 예시)

```bash
fly launch --name fridgechef-api --no-deploy
fly secrets set JWT_SECRET=<rand> GEMINI_API_KEY=<key> DATABASE_URL=<managed-pg-url>
fly deploy
```

### 9.4 Vercel 배포 (프론트엔드)

```bash
cd frontend
vercel link
vercel env add NEXT_PUBLIC_API_URL production   # https://fridgechef-api.fly.dev
vercel deploy --prod
```

---

## 10. 알려진 한계 + TODO

### 10.1 미구현 FR / 한계

- **레시피 시드 데이터 부족** — `db/seeds/sample_recipes.json` 30+건 큐레이션 필요
- **골든셋 미완성** — `tests/test_recommend.py::GOLDEN_SAMPLES_50` 현재 5건 placeholder (목표 50건)
- **Alembic 리비전 부재** — `backend/alembic/versions/` 비어 있음. 첫 리비전 생성 후 CI 연결 필요
- **`black` / Prettier / Vitest 미설치** — 도입 시 CI 파이프라인 동시 갱신
- **CORS** — 개발용 `allow_origins=["*"]` → 운영 전 도메인 화이트리스트로 좁힐 것
- **레시피 화이트리스트 캐싱** — 매 추천마다 `repo.list_all()` 전수 순회. 100+건 확장 시 인덱싱 검토
- **레이팅(평점) 라우터** — `db/migrations/001_init.sql` 의 `ratings` 테이블만 존재, 라우터/서비스 미구현

### 10.2 후속 작업 우선순위

| P | 작업 | 담당 후보 |
|---|---|---|
| P0 | 레시피 시드 30+건 큐레이션 + 화이트리스트 ID 부여 | Data |
| P0 | 골든셋 50샘플 완성 + CI 회귀 가드 | QA |
| P1 | 평점 라우터(`POST /api/ratings`) + 서비스 + 테스트 | Backend |
| P1 | 프론트 5화면 폴리싱 + 토스트·에러 핸들링 | Frontend |
| P2 | Alembic 리비전 생성 + CI 단계 추가 | Backend |
| P2 | Redis 캐싱(추천 결과 TTL 5분) — `RECOMMEND_TIMEOUT_S` 압박 완화 | Backend |
| P3 | Fly.io/Vercel 배포 자동화 + `.github/workflows/deploy.yml` | DevOps |

### 10.3 학부 SE 단계 일정 (가이드)

- **1단계 (현재 ~ +2주)** — MVP 1차 완성: 레시피 시드·골든셋·평점 라우터·프론트 5화면
- **2단계 (+4주)** — 통합 테스트·성능 측정(NFR-PERF-001 ≤10s 실측)·Gemini 인용 검증 ≥95%
- **3단계 (+6주)** — 배포·운영 모니터링·발표 데모 / 최종 보고서

---

## 11. FAQ (자주 묻는 10가지)

**Q1. Gemini API 키는 어디서 받나요?**
A. <https://aistudio.google.com/app/apikey> 에서 무료 발급. `.env` 의 `GEMINI_API_KEY` 에 붙여 넣고 컨테이너 재기동(`docker-compose up`).

**Q2. DB 마이그레이션은 어떻게 진행하나요?**
A. 1차 완성까지는 `db/migrations/001_init.sql` 을 `docker-compose up` 시 자동 적용. 이후 변경은 Alembic 리비전 생성으로 전환합니다.

```bash
cd backend
alembic revision --autogenerate -m "add ratings index"
alembic upgrade head
```

**Q3. 모델 A · B 알고리즘을 수정하려면 어디를 봐야 하나요?**
A. `backend/app/services/model_a.py` 와 `model_b.py`. 가중치 변경 시 `_composite_score()` 의 `0.7 / 0.2 / 0.1` 상수를 수정하고 반드시 `tests/test_recommend.py` 의 관련 케이스(특히 `test_model_a_allergy_zero_exposure`)를 재실행하세요.

**Q4. 알레르기 동의어를 추가하려면?**
A. `backend/app/core/synonym_map.py` 의 `SYNONYM_MAP` 딕셔너리에 `"별칭": "대표키워드"` 한 줄 추가. 동시에 `db/seeds/synonym_map.json` 도 갱신(프론트·QA 공유용). 추가 후 `pytest -k synonym -q` 로 회귀 확인.

**Q5. 디자인 시스템 컬러를 변경하려면?**
A. `frontend/tailwind.config.ts` 의 `theme.extend.colors` 에서 5종 팔레트(`cream` / `clay` / `gochu` / `herb` / `mustard`) 수정. 변경 후 `npm run dev` 자동 핫리로드.

**Q6. JWT 토큰 만료 시간을 늘리려면?**
A. `.env` 의 `JWT_EXPIRE_MIN`(분 단위, 기본 1440=24시간) 수정 후 백엔드 재기동. `backend/app/services/auth_service.py::issue_token()` 에서 사용됩니다.

**Q7. 추천 응답이 자꾸 빈 배열로 옵니다.**
A. 세 가지 점검: (1) `repo.list_all()` 에 레시피가 있는가 (현재 메모리 카탈로그) (2) 알레르기 필터에 모두 걸리진 않았는가 (3) `max_cook_min` 이 너무 짧지 않은가. 백엔드 로그에 `recommend_dual 타임아웃` 이 보이면 Gemini 호출 지연이 원인일 가능성 — `GEMINI_TIMEOUT_S` 를 5초로 낮춰 폴백을 빠르게 유도하세요.

**Q8. 프론트엔드에서 CORS 에러가 납니다.**
A. `backend/app/main.py` 의 CORS 설정이 개발용으로 `allow_origins=["*"]` 입니다. 운영 배포 후 막혔다면 운영 프론트 도메인을 화이트리스트에 추가하세요. 개발 중에는 `NEXT_PUBLIC_API_URL` 이 `http://localhost:8000` 인지 확인.

**Q9. CI 가 ruff 또는 pytest 에서 실패합니다.**
A. 로컬에서 동일 명령으로 재현하세요.

```bash
cd backend && ruff check . && pytest -q
cd frontend && npx tsc --noEmit && npm run lint
```

ruff 자동수정은 `ruff check . --fix` 로 일부 해결 가능. CI 환경변수(`JWT_SECRET=ci-test-secret`, `GEMINI_API_KEY=""`)와 동일하게 맞춰 시험.

**Q10. AI Usage 섹션에는 정확히 무엇을 적나요?**
A. 최소 4개 항목: (1) 도구·모델·버전 (2) 어떤 파일·함수를 AI 가 생성/수정 (3) 사람이 직접 검증한 범위(테스트 실행·코드 리뷰) (4) AI 한계로 직접 작성한 부분. 예시는 `.github/PULL_REQUEST_TEMPLATE.md` 참조.

---

## 12. 빠른 참조 카드

```bash
# 풀스택 한 줄 실행
docker-compose up --build

# 백엔드 단위 테스트 + 린트
cd backend && pytest -q && ruff check .

# 프론트엔드 타입체크 + 린트
cd frontend && npx tsc --noEmit && npm run lint

# 헬스체크
curl http://localhost:8000/health

# Swagger UI
open http://localhost:8000/docs

# Postgres 접속
docker exec -it fridgechef-postgres psql -U fridgechef -d fridgechef

# 백엔드 로그 추적
docker logs -f fridgechef-backend
```

> 작성: 인수인계 시점 기준. 문서 갱신 시 본 파일 헤더에 `> 최종 수정: YYYY-MM-DD by <name>` 한 줄 추가하세요.
