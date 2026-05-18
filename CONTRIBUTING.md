# Contributing — FridgeChef

> 소프트웨어공학팀 프로젝트. 한국어 우선, 작은 단위 PR 권장.

## 브랜치 전략 (GitHub Flow + dev)
- `main` : 항상 배포 가능한 상태. 직접 푸시 금지.
- `dev`  : 통합 브랜치. 모든 feature PR은 `dev` 로 머지.
- 작업 브랜치 명규칙
  - `feat/<scope>-<짧은-설명>` 예: `feat/recommend-model-a`
  - `fix/<scope>-<짧은-설명>`  예: `fix/fridge-normalize-bug`
  - `chore/<설명>`             예: `chore/ci-cache-pip`

## 커밋 컨벤션 (Conventional Commits)
```
<type>(<scope>): <subject>

[optional body]
[optional footer]
```
type: `feat | fix | docs | refactor | test | chore | perf | ci | style`

예시:
```
feat(recommend): 모델 A 냉털 코사인 유사도 구현
fix(fridge): 동의어 정규화에서 None 처리
chore(ci): pip 캐시 추가로 CI 30% 단축
```

## PR 절차
1. 브랜치 작업 → 본인 푸시
2. PR 생성 (`base: dev`)
3. PR 템플릿의 **AI Usage** 섹션 반드시 기입
4. 코드리뷰 1인 이상 승인 후 머지
5. `dev` → `main` 머지는 릴리스 시점에만

## 코드 스타일
- Python: `ruff check .` 통과, 타입힌트 권장
- TypeScript: `npx tsc --noEmit` 통과, ESLint 위반 0
- 한국어 주석 OK, 단 공개 인터페이스에는 docstring 포함
- 비즈니스 로직에는 `# NFR-XXX-NNN` 추적 주석

## 로컬 개발
```bash
# 백엔드
cd backend
pip install .[dev]
uvicorn app.main:app --reload

# 프론트
cd frontend
npm install
npm run dev

# 전체 스택
docker-compose up --build
```

## 테스트
```bash
cd backend && pytest -q
cd frontend && npx tsc --noEmit
```
