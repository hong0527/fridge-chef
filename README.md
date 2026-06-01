# fridge-chef

> 냉장고 재료 기반 AI 레시피 추천 웹앱 — 이중 추천 모델(냉털/부족재료) + Gemini 2.5 Flash 자연어 설명

소프트웨어공학팀 프로젝트. 사용자가 냉장고에 있는 재료를 입력하면 두 가지 추천을 동시에 제공합니다.
- **모델 A — 냉털 추천** : 현재 재료만으로 즉시 만들 수 있는 레시피 (코사인 유사도, 상위 10건)
- **모델 B — 부족 재료 추천** : "이 재료 N개만 더 사면" 만들 수 있는 레시피 (복합 점수 → Gemini 자연어 이유, 상위 3건)
- **Gemini 2.5 Flash** : 추천 이유를 한국어 1–2문장으로 친근하게 설명

자세한 요구사항은 `docs/SRS_v1.10_1차완성본.pdf`, 설계는 `docs/SDD_v1.0_공유용.pdf`.

## 아키텍처 (SDD §1.3 4-Layer)

```
┌──────────────────────────────┐
│ Frontend  Next.js 14 + Tailwind (5 화면)
└──────────────┬───────────────┘
               │ HTTPS / JSON
┌──────────────▼───────────────┐
│ Presentation  FastAPI 라우터 (/api/*)
├──────────────────────────────┤
│ Service       AuthService · EmailService · FridgeService · RecommendService
│               + Model A · Model B · GeminiClient
├──────────────────────────────┤
│ Data          SQLAlchemy ORM (User · FridgeIngredient · Recipe · Rating)
└──────────────┬───────────────┘
               │
       Postgres 15 ──── Redis 7 (캐시·세션) ──── Mailpit (로컬 메일)
```

## 빠른 시작

### 1. 사전 준비
- Docker Desktop / Docker Engine
- Python 3.11+ (로컬 백엔드 개발 시)
- Node 20+ (로컬 프론트 개발 시)
- Gemini API 키 ([Google AI Studio](https://aistudio.google.com/app/apikey))

### 2. 환경변수 설정
```bash
cp .env.local.example .env
# .env 파일을 열어 GEMINI_API_KEY, JWT_SECRET 을 채워주세요
```

### 3. 전체 스택 실행 (로컬)
```bash
docker compose up --build
# 백엔드:  http://localhost:8000/docs
# 프론트:  http://localhost:3000
# Mailpit: http://localhost:8025  ← 이메일 인증 메일 확인
```

> `docker-compose.override.yml` 이 자동 적용되어 Mailpit이 함께 실행됩니다.

### 3-1. 운영 서버 배포 (VPS)
```bash
cp .env.prod.example .env
# .env 파일에서 JWT_SECRET, SMTP_*, CORS_ORIGINS, FRONTEND_URL 등 실제 값 채우기

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

> 운영 환경에서는 `docker-compose.override.yml` 이 적용되지 않으므로 Mailpit이 실행되지 않습니다.
> 실제 SMTP 서비스(SendGrid, AWS SES 등) 설정이 필요합니다.

### 3-2. 대규모 레시피 데이터셋 적재 (1667건 + 이미지 1667장)
기본 부팅 시 DB에는 SEED 35건만 들어있습니다.
실제 시연·평가용 데이터셋(1667 레시피 + 이미지)은 별도 ETL로 적재해야 합니다.

```bash
# 1) 데이터셋 위치 지정 (env 또는 기본 경로 사용)
export RECIPE_CSV_PATH=/path/to/preprocessed_recipe.csv
export RECIPE_IMG_DIR=/path/to/images
# 기본값 사용 시: <repo>/data/preprocessed_recipe.csv, <repo>/data/images/

# 2) ETL 실행 (DB 적재 + 이미지 복사 + 인덱스 생성)
cd backend
python scripts/import_real_recipes.py

# 3) 백엔드 재기동으로 인메모리 repo 갱신
docker compose restart backend

# 4) 적재 확인 (recipe_count=1667+ 이어야 정상)
curl http://localhost:8000/health
```

> **주의**: CSV·이미지 원본은 저장소(.gitignore)에 포함되지 않습니다.
> 학부 평가용 데이터셋 파일은 팀 공유 드라이브에서 받으세요.

### 이메일 인증 (로컬)
회원가입 시 인증 메일이 **Mailpit**(로컬 메일 캐처)으로 발송됩니다.
`http://localhost:8025` 에서 메일을 확인하고 인증 링크를 클릭하면 로그인 가능합니다.

### 4. 개별 실행 (개발 모드)

**백엔드**
```bash
cd backend
pip install .[dev]
uvicorn app.main:app --reload
```

**프론트엔드**
```bash
cd frontend
npm install
npm run dev
```

## 테스트

```bash
# 백엔드 단위 테스트 + lint
cd backend
pytest -q
ruff check .

# 프론트엔드 타입체크
cd frontend
npx tsc --noEmit
```

## 디렉토리 구조

```
fridge-chef/
├── backend/                 # FastAPI 백엔드
│   ├── app/
│   │   ├── api/             # 라우터 (auth · fridge · recommend · recipes)
│   │   ├── services/        # 비즈니스 로직 (auth_service · email_service · fridge_service · recommend_service · model_a · model_b · gemini_client)
│   │   ├── models/          # SQLAlchemy ORM + Recipe 도메인 + RecipeRepository
│   │   ├── schemas/         # Pydantic 요청·응답 DTO
│   │   └── core/            # config · db · security · synonym_map · auth
│   ├── alembic/             # DB 마이그레이션
│   ├── tests/               # pytest
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                # Next.js 14 (App Router) + Tailwind
│   ├── app/                 # 라우트 (layout · page · ...)
│   ├── components/          # UI 컴포넌트
│   ├── lib/                 # API 클라이언트
│   └── Dockerfile
├── db/
│   ├── migrations/          # 001_init.sql (psql 일회 적용)
│   └── seeds/               # synonym_map.json · sample_recipes.json
├── docs/                    # SRS · SDD
├── .github/
│   ├── workflows/ci.yml     # pytest + ruff + tsc
│   └── PULL_REQUEST_TEMPLATE.md
├── docker-compose.yml           # 공통 base
├── docker-compose.override.yml  # 로컬 자동 적용 (Mailpit 포함)
├── docker-compose.prod.yml      # 운영 오버라이드
├── .env.local.example           # 로컬 환경변수 템플릿
├── .env.prod.example            # 운영 환경변수 템플릿
└── README.md
```

## 핵심 비기능 요구 (NFR)
- **NFR-PERF-001** 추천 응답 ≤ 10초 (RecommendService timeout)
- **NFR-EVAL-001** 알레르기 누출 0% (정규화 후 교집합 차단)
- **NFR-EVAL-002** Gemini 출력 화이트리스트 외 recipe_id 차단
- **NFR-SEC-001** API 키 환경변수 격리 (.env 비커밋)
- **NFR-SEC-002** bcrypt(work=12) + JWT(HS256)
- **NFR-OPS-001** /health 헬스체크 + 컨테이너 배포

## 팀원
| 역할 | 이름 | 담당 |
|---|---|---|
| PM / Backend | (작성자) | RecommendService · Model A·B · 인프라 |
| Frontend | (TBD) | 5 화면 (로그인·냉장고·추천·상세·평점) |
| Data | (TBD) | SYNONYM_MAP 확장 100쌍 · 레시피 시드 30+건 |
| QA | (TBD) | 골든셋 회귀 · 알레르기 누출 테스트 |

> 본 프로젝트는 학습 목적이며, 다수의 AI 도구(Claude Code, ChatGPT, Gemini)를 코딩 보조로 활용합니다.
> 모든 PR 의 `AI Usage` 섹션에 사용 내역을 명시합니다 (`.github/PULL_REQUEST_TEMPLATE.md` 참고).

## 라이선스
MIT — `LICENSE` 파일 참고.
