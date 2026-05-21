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
│ Service       AuthService · FridgeService · RecommendService
│               + Model A · Model B · GeminiClient
├──────────────────────────────┤
│ Data          SQLAlchemy ORM (User · FridgeIngredient · Recipe · Rating)
└──────────────┬───────────────┘
               │
       Postgres 15 ──── Redis 7 (캐시·세션)
```

## 빠른 시작

### 1. 사전 준비
- Docker Desktop / Docker Engine
- Python 3.11+ (로컬 백엔드 개발 시)
- Node 20+ (로컬 프론트 개발 시)
- Gemini API 키 ([Google AI Studio](https://aistudio.google.com/app/apikey))

### 2. 환경변수 설정
```bash
cp .env.example .env
# .env 파일을 열어 GEMINI_API_KEY, JWT_SECRET 등을 채워주세요
```

### 3. 전체 스택 실행 (권장)
```bash
docker-compose up --build
# 백엔드: http://localhost:8000/docs
# 프론트: http://localhost:3000
```

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
│   │   ├── services/        # 비즈니스 로직 (auth_service · fridge_service · recommend_service · model_a · model_b · gemini_client)
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
├── docker-compose.yml
├── .env.example
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
