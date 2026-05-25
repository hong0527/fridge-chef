# 작업 순서 (process(fridge).md)

참고 문서: `workList2(fridge).md`
하루 최대 수행 가능 작업: 4가지

---

## 의존성 구조 (작업 순서 결정 근거)

```
[Day 1 — 백엔드 완성 + 공통 컴포넌트]
  fridge_service.py (수정)  ←── fridge.py가 search_ingredient_suggestions() 호출
  fridge.py (수정)          ←── fridge_service.py 완료 후
  lib/api.ts (수정)         ←── page.tsx 자동완성이 수정된 URL 사용
  FridgeChip.tsx (수정)     ←── page.tsx 기능 5·6·7이 신규 props(categoryColor·onEdit·selectable 등) 사용

[Day 2 — fridge/page.tsx 기능 1·3·4·5]
  기능 1 빠른 추가 버튼     ←── 독립적 (RF-05 중복 검사만 추가)
  기능 3 기본 양념 토글     ←── 독립적
  기능 4 빈 상태 개선       ←── 독립적
  기능 5 카테고리 색상      ←── Day 1 FridgeChip.tsx의 categoryColor prop 완료 후

[Day 3 — fridge/page.tsx 기능 6·7 + 코드 검증]
  기능 6 인라인 편집        ←── Day 1 FridgeChip.tsx의 onEdit prop 완료 후 (RF-03·RF-06)
  기능 7 선택 삭제          ←── Day 1 FridgeChip.tsx의 selectable·selected·onSelect 완료 후
  pytest -q                 ←── 백엔드 Day 1 완료 후
  npx tsc --noEmit          ←── 프론트엔드 Day 3 전체 완료 후

[Day 4 — E2E·NFR 전체 검증]
  브라우저 기능 검증        ←── Day 3 모든 작업 완료 후
  기존 기능 회귀 검증       ←── Day 3 모든 작업 완료 후
  NFR 항목 검증             ←── Day 3 모든 작업 완료 후
  ruff check .              ←── 백엔드 Day 1 완료 후
```

---

## Day 1 — 백엔드 완성 + 공통 컴포넌트

> 목표: 자동완성 서비스 함수·엔드포인트 완성 + FridgeChip 신규 props 추가

---

### 작업 1-1. `backend/app/services/fridge_service.py` 수정

- workList2(fridge).md 항목: **기능 2**
- 관련 NFR: —
- 내용: `search_ingredient_suggestions()` 함수 추가 (RF-01 서비스 레이어 분리, RF-04 동의어 자체 반환)

**테스트 파일 생성**
- 생성 위치: `backend/tests/unit/test_fridge_service.py`
```python
from app.services.fridge_service import search_ingredient_suggestions

def test_search_empty():
    assert search_ingredient_suggestions('') == []

def test_search_synonym_returns_synonym():
    # RF-04: 동의어 입력 시 정규형이 아닌 동의어 자체 반환
    results = search_ingredient_suggestions('달걀')
    assert '달걀' in results

def test_search_canonical_returns_canonical():
    results = search_ingredient_suggestions('계란')
    assert '계란' in results

def test_search_limit():
    results = search_ingredient_suggestions('고기')
    assert len(results) <= 8
```
- 생성 후 바로 실행:
```bash
pytest tests/unit/test_fridge_service.py -v
```

**테스트**

자동:
```bash
python -c "
from app.services.fridge_service import search_ingredient_suggestions

# 1. 빈 쿼리 → 빈 리스트
assert search_ingredient_suggestions('') == [], '빈 쿼리 실패'

# 2. RF-04: 동의어 매칭 → 동의어 자체 반환
results = search_ingredient_suggestions('달걀')
assert '달걀' in results, 'RF-04: 동의어 반환 실패'

# 3. 정규형 매칭 → 정규형 반환
results = search_ingredient_suggestions('계란')
assert '계란' in results, '정규형 반환 실패'

# 4. limit 8 이하 보장
results = search_ingredient_suggestions('고기')
assert len(results) <= 8, 'limit 초과'

print('fridge_service 테스트 통과')
"
```

회귀 확인 — 기존 서비스 함수(`add_for_user`·`list_for_user`·`delete_for_user`) 영향 없음:
```bash
pytest tests/api/test_fridge_api.py -q
```

---

### 작업 1-2. `backend/app/api/fridge.py` 수정

- workList2(fridge).md 항목: **기능 2**
- 관련 NFR: **NFR-SEC-002**
- 내용: `GET /api/fridge/search` 엔드포인트 추가 — `fridge_service.search_ingredient_suggestions()` 호출, `Depends(get_current_user)` 적용 (RF-02)
- 선행 조건: 작업 1-1 완료

**테스트**

자동 — 라우터 구조 확인:
```bash
python -c "
from app.api.fridge import router, search_ingredients
import inspect

# 1. /search 경로 존재 확인
paths = [r.path for r in router.routes]
assert '/search' in paths, '/search 경로 없음'

# 2. RF-02: get_current_user Depends 존재 확인
sig = inspect.signature(search_ingredients)
param_defaults = [str(p.default) for p in sig.parameters.values()]
assert any('get_current_user' in d for d in param_defaults), 'RF-02: 인증 Depends 없음'

print('fridge.py 라우터 테스트 통과')
"
```

수동 — 서버 구동 후:
```
[ ] Swagger UI(http://localhost:8000/docs) → GET /api/fridge/search 엔드포인트 노출
[ ] 미인증 상태로 GET /api/fridge/search?q=계란 → 401 응답 (NFR-SEC-002)
[ ] 인증 상태로 GET /api/fridge/search?q=계란 → {"suggestions": [...]} 응답
[ ] q=달 → suggestions에 "달걀" 포함 (RF-04 확인)
```

회귀 확인 — 기존 fridge 엔드포인트 정상 동작:
```bash
pytest tests/api/test_fridge_api.py -q
```

---

### 작업 1-3. `frontend/lib/api.ts` 수정

- workList2(fridge).md 항목: **기능 2**
- 관련 NFR: —
- 내용: `searchIngredients()` 내 URL `/ingredients/search` → `/fridge/search` 변경

**테스트**

자동 — URL 변경 확인:
```bash
cd frontend

# 변경 전 URL이 남아있지 않은지 확인
grep -c "ingredients/search" lib/api.ts && echo "URL 미변경 — 수정 필요" || echo "기존 URL 제거 확인"

# 변경 후 URL 존재 확인
grep -c "fridge/search" lib/api.ts && echo "fridge/search 확인" || echo "새 URL 없음 — 수정 필요"
```

자동 — 타입 체크:
```bash
cd frontend && npx tsc --noEmit
```

수동:
```
[ ] 냉장고 페이지 재료 입력 시 자동완성 제안 목록 표시 확인
[ ] "달" 입력 → "달걀" 제안 표시 (RF-04)
[ ] "계" 입력 → "계란" 제안 표시
```

회귀 확인 — 기존 API 함수 영향 없음:
```bash
cd frontend && npx tsc --noEmit
```

---

### 작업 1-4. `frontend/components/FridgeChip.tsx` 수정

- workList2(fridge).md 항목: **기능 5·6·7**
- 관련 NFR: NFR-USE-002
- 내용: `categoryColor`·`onEdit`·`selectable`·`selected`·`onSelect` props 추가 + `categoryStyles` 맵 추가 + RF-07 그림자 조건 수정(`!categoryColor &&`)

**테스트 파일 생성**
- 생성 위치: `frontend/__tests__/FridgeChip.test.tsx`
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { FridgeChip } from '../components/FridgeChip';

test('categoryColor 없을 때 shadow 클래스 적용', () => {
  const { container } = render(<FridgeChip name="재료" />);
  expect(container.firstElementChild?.className).toContain('shadow-[0_2px');
});

test('RF-07: categoryColor 지정 시 shadow 클래스 미적용', () => {
  const { container } = render(
    <FridgeChip name="대파" categoryColor="vegetable" />
  );
  expect(container.firstElementChild?.className).not.toContain('shadow-[0_2px');
});

test('onEdit 지정 시 name span 클릭 → onEdit 호출', () => {
  const onEdit = jest.fn();
  render(<FridgeChip name="계란" onEdit={onEdit} />);
  fireEvent.click(screen.getByText('계란'));
  expect(onEdit).toHaveBeenCalledTimes(1);
});

test('selectable + selected 시 체크박스 표시', () => {
  render(<FridgeChip name="계란" selectable selected onSelect={jest.fn()} />);
  expect(screen.getByText('✓')).toBeInTheDocument();
});

test('selectable 미지정 시 X 삭제 버튼 표시', () => {
  const onRemove = jest.fn();
  render(<FridgeChip name="계란" onRemove={onRemove} />);
  fireEvent.click(screen.getByRole('button', { name: '계란 재료 삭제' }));
  expect(onRemove).toHaveBeenCalledTimes(1);
});
```
- 생성 후 바로 실행:
```bash
cd frontend && npx jest __tests__/FridgeChip.test.tsx --no-coverage
```

**테스트**

자동:
```bash
cd frontend && npx tsc --noEmit
```

수동:
```
[ ] 냉장고 페이지 기존 재료 칩 렌더링 → 스타일 변경 없음 (categoryColor 없는 경우)
[ ] 재료 칩 X 버튼 → 삭제 정상 동작 (기존 기능 유지)
```

회귀 확인:
```bash
pytest tests/api/test_fridge_api.py -q
```

---

### Day 1 완료 체크
```
[ ] fridge_service.py — python 스니펫 4가지 통과
[ ] fridge_service.py — pytest tests/unit/test_fridge_service.py -v 통과
[ ] fridge.py — 라우터 python 확인 통과
[ ] fridge.py — Swagger /search 노출 + 미인증 401 확인
[ ] fridge.py — pytest tests/api/test_fridge_api.py -q (기존 회귀) 통과
[ ] api.ts — grep URL 변경 확인 + npx tsc 통과
[ ] FridgeChip.tsx — npx tsc 통과
[ ] FridgeChip.tsx — Jest 5가지 통과
```

---

## Day 2 — fridge/page.tsx 기능 1·3·4·5

> 목표: 빠른 추가·양념 토글·빈 상태·카테고리 색상 구현

---

### 작업 2-1. `frontend/app/(main)/fridge/page.tsx` 기능 1 — 빠른 추가 버튼

- workList2(fridge).md 항목: **기능 1**
- 관련 NFR: NFR-USE-001
- 내용: `QUICK_INGREDIENTS` 상수 + 빠른 추가 버튼 UI + RF-05 중복 검사(`raw_name` + `normalized_name` 모두 비교)

**테스트**

자동:
```bash
cd frontend && npx tsc --noEmit
```

수동:
```
[ ] 검색 인풋 아래 "자주 쓰는 재료" 레이블 + 10개 버튼 표시
[ ] 버튼 클릭 → 재료 추가 + 버튼 ✓ dimmed 처리
[ ] dimmed 버튼 클릭 → 아무 동작 없음 (disabled)
[ ] RF-05: "달걀" 직접 입력 후 "계란" 빠른 추가 버튼 → dimmed 상태 (normalized_name 중복 방지)
```

회귀 확인:
```
[ ] 기존 타이핑 추가(검색 인풋 + Enter) 정상 동작
[ ] 기존 재료 X 버튼 삭제 정상 동작
```

---

### 작업 2-2. `frontend/app/(main)/fridge/page.tsx` 기능 3 — 기본 양념 토글

- workList2(fridge).md 항목: **기능 3**
- 관련 NFR: NFR-USE-001
- 내용: `BASIC_SEASONINGS` 상수(6개) + `basicSeasoning` boolean 상태 + `handleToggleBasicSeasoning()` + 토글 버튼 UI

**테스트**

자동:
```bash
cd frontend && npx tsc --noEmit
```

수동:
```
[ ] "+ 기본 양념 한번에 추가" 버튼 표시
[ ] 클릭 → 소금·간장·참기름·설탕·후추·식용유 6개 추가 + 버튼 "✓ 기본 양념 포함 중"으로 변경
[ ] 재클릭 → 6개 조미료만 제거 (사용자가 직접 추가한 다른 재료는 보존)
[ ] 이미 일부 조미료가 있을 때 → 없는 것만 추가 (중복 없음)
```

회귀 확인:
```
[ ] 빠른 추가 버튼(기능 1) 정상 동작 유지
[ ] 기존 타이핑 추가·삭제 정상 동작
```

---

### 작업 2-3. `frontend/app/(main)/fridge/page.tsx` 기능 4 — 빈 상태 개선

- workList2(fridge).md 항목: **기능 4**
- 관련 NFR: NFR-USE-001
- 내용: 빈 상태 블록 교체 — 안내 문구 변경 + 빠른 추가 버튼 6개(계란·대파·마늘·양파·두부·김치) 삽입

**테스트**

자동:
```bash
cd frontend && npx tsc --noEmit
```

수동:
```
[ ] 냉장고 비어있을 때 → "자주 쓰는 재료로 빠르게 시작해보세요." 문구 표시
[ ] 6개 버튼 표시
[ ] 버튼 클릭 → 재료 추가 + 재료 목록으로 전환 (빈 상태 블록 사라짐)
[ ] 기존 문구("위 입력창에 재료 이름을 넣어보세요.") 미표시 확인
```

회귀 확인:
```
[ ] 재료 있을 때 빈 상태 블록 표시 안 됨
[ ] 재료 추가 후 재료 목록으로 정상 전환
```

---

### 작업 2-4. `frontend/app/(main)/fridge/page.tsx` 기능 5 — 카테고리 색상

- workList2(fridge).md 항목: **기능 5**
- 관련 NFR: NFR-USE-002
- 내용: `INGREDIENT_CATEGORY` 매핑 딕셔너리 추가 + `FridgeChip`에 `categoryColor={INGREDIENT_CATEGORY[ing.normalized_name]}` 전달
- 선행 조건: 작업 1-4 (FridgeChip.tsx `categoryColor` prop) 완료

**테스트**

자동:
```bash
cd frontend && npx tsc --noEmit
```

수동:
```
[ ] 대파·양파·마늘·당근·감자·두부·김치·애호박 → 초록(vegetable) 테두리·배경
[ ] 돼지고기·소고기·닭고기 → 빨강(meat) 테두리·배경
[ ] 새우·오징어·고등어·조개류 → 파랑(seafood) 테두리·배경
[ ] 계란·우유·치즈·버터 → 노랑(dairy) 테두리·배경
[ ] 소금·간장·참기름·설탕·후추·식용유 → 주황(seasoning) 테두리·배경
[ ] 매핑 없는 재료(예: 사과) → 기존 default 스타일 유지
[ ] RF-07: 카테고리 색상 칩에 검정 그림자 없음
```

회귀 확인:
```
[ ] 재료 추가·삭제 정상 동작 (카테고리 관계없이)
[ ] categoryColor 미지정 칩 → 기존 shadow 스타일 유지
```

---

### Day 2 완료 체크
```
[ ] 기능 1 — 빠른 추가 버튼 10개 + RF-05 중복 방지 확인
[ ] 기능 3 — 토글 버튼 동작 + 비활성화 시 사용자 재료 보존 확인
[ ] 기능 4 — 빈 상태 버튼 6개 + 클릭 추가 확인
[ ] 기능 5 — 5가지 카테고리 색상 표시 + RF-07 그림자 없음 확인
[ ] npx tsc --noEmit — 0 errors
```

---

## Day 3 — fridge/page.tsx 기능 6·7 + 코드 검증

> 목표: 인라인 편집·선택 삭제 구현 완성 후 백엔드·프론트엔드 코드 전체 검증

---

### 작업 3-1. `frontend/app/(main)/fridge/page.tsx` 기능 6 — 인라인 편집

- workList2(fridge).md 항목: **기능 6**
- 관련 NFR: NFR-USE-001
- 내용: `editingId`·`editValue` 상태 + `handleEditStart()`·`handleEditSubmit()` + 인라인 `<input>` 렌더링 (RF-03 추가 먼저, RF-06 원래 위치 `splice` 삽입)
- 선행 조건: 작업 1-4 (FridgeChip.tsx `onEdit` prop) 완료

**테스트**

자동:
```bash
cd frontend && npx tsc --noEmit
```

수동:
```
[ ] 칩 이름 클릭 → 해당 위치에 인라인 input 표시 + 자동 포커스
[ ] 수정 후 Enter → 토스트 "'기존명' → '새이름' 수정됨" 표시
[ ] Escape → 편집 취소 (원래 칩으로 복귀)
[ ] blur(다른 곳 클릭) → 수정 제출
[ ] 이름 변경 없이 Enter → 취소 (API 호출 없음)
[ ] RF-03: 네트워크 탭에서 POST(추가) → DELETE(삭제) 순서 확인
[ ] RF-06: 10개 재료 중 3번째 편집 완료 → 3번째 위치 그대로 유지
```

회귀 확인:
```
[ ] 편집 모드 중 다른 기능(양념 토글 등) 클릭 → 정상 동작
[ ] 편집 완료 후 카테고리 색상(기능 5) 정상 표시
```

---

### 작업 3-2. `frontend/app/(main)/fridge/page.tsx` 기능 7 — 선택 삭제

- workList2(fridge).md 항목: **기능 7**
- 관련 NFR: NFR-USE-001
- 내용: `selectMode`·`selectedIds(Set<number>)` 상태 + `toggleSelectId()`·`handleDeleteSelected()`·`exitSelectMode()` + 헤더 선택/삭제/취소 버튼 UI
- 선행 조건: 작업 1-4 (FridgeChip.tsx `selectable`·`selected`·`onSelect` props) 완료

**테스트**

자동:
```bash
cd frontend && npx tsc --noEmit
```

수동:
```
[ ] "선택" 버튼 클릭 → 선택 모드 진입 + 모든 칩에 체크박스 표시
[ ] 칩 클릭 → 체크박스 체크 + gochu-500 강조 테두리
[ ] 칩 재클릭 → 체크박스 해제
[ ] "삭제 (N)" 버튼 클릭 → N개 재료 삭제 + 토스트 "N개 재료가 삭제되었습니다."
[ ] "취소" 클릭 → 선택 모드 종료 + 선택 초기화 (재료 유지)
[ ] 선택 0개 상태에서 "삭제" 버튼 → disabled
[ ] 선택 모드 중 "전체 삭제" 버튼 숨김
[ ] 선택 모드 중 칩 이름 클릭 → 편집 미진입 (onEdit 비활성)
[ ] 선택 삭제 실패 시 → 재료 목록 롤백 (낙관적 업데이트 취소)
```

회귀 확인:
```
[ ] 선택 모드 종료 후 기존 기능(단일 추가·편집·삭제·전체 삭제) 정상 복귀
[ ] 카테고리 색상(기능 5) 선택 모드 진입/종료 시 유지
```

---

### 작업 3-3. 백엔드 전체 테스트

```bash
cd backend
pytest -q
ruff check app/services/fridge_service.py app/api/fridge.py
```

확인 항목:
```
[ ] 전체 테스트 통과 (0 failed)
[ ] test_fridge_api.py 전체 통과
[ ] test_fridge_service.py 전체 통과
[ ] ruff 오류 없음 (fridge_service.py, fridge.py)
```

> Day 3-3은 테스트 작업 자체이므로 별도 테스트 항목 없음.

---

### 작업 3-4. 프론트엔드 타입·유닛 전체 검증

```bash
cd frontend
npx tsc --noEmit
npx jest --no-coverage
```

확인 항목:
```
[ ] TypeScript 컴파일 오류 0건
[ ] FridgeChip.test.tsx Jest 5가지 통과
```

> Day 3-4는 검증 작업 자체이므로 별도 테스트 항목 없음.

---

### Day 3 완료 체크
```
[ ] 기능 6 — 이름 클릭 편집 + RF-03 순서 확인 + RF-06 위치 확인
[ ] 기능 7 — 선택 모드 + 선택 삭제 + 취소 동작 확인
[ ] pytest -q — 0 failed + ruff 오류 없음
[ ] npx tsc --noEmit — 0 errors + Jest 전체 통과
```

---

## Day 4 — E2E·NFR 전체 검증

> 목표: 7개 기능 전체 흐름 검증 + 기존 기능 회귀 없음 + NFR 충족 확인

---

### 작업 4-1. 브라우저 기능 전체 검증

서버 구동:
```bash
# 백엔드
cd backend && uvicorn app.main:app --reload

# 프론트엔드 (별도 터미널)
cd frontend && npm run dev
```

| 기능 | 검증 항목 | 기준 |
|---|---|---|
| 기능 1 | 빠른 추가 버튼 10개 | 클릭 → 칩 추가 + dimmed 처리 |
| 기능 2 | 자동완성 드롭다운 | 재료 입력 시 제안 목록 표시 + "달" → "달걀" 포함 |
| 기능 3 | 양념 토글 버튼 | 활성·비활성 시 6개 조미료 추가·제거 |
| 기능 4 | 빈 상태 버튼 | 냉장고 비었을 때 6개 버튼 표시 + 클릭 추가 |
| 기능 5 | 카테고리 색상 칩 | 5가지 카테고리 색상 구분 표시 |
| 기능 6 | 인라인 편집 | 이름 클릭 → 수정 → 원래 위치 유지 |
| 기능 7 | 선택 삭제 | 다중 선택 → 삭제 → 토스트 표시 |

```
[ ] 기능 1~7 항목 전체 체크
```

---

### 작업 4-2. 기존 냉장고 기능 회귀 검증

```
[ ] 타이핑으로 재료 추가 (검색 인풋 + Enter)
[ ] 단일 재료 X 버튼 삭제
[ ] 전체 삭제 버튼 + 확인 모달 → 전체 삭제
[ ] 최대 50개 초과 시 경고 토스트 표시
[ ] 페이지 새로고침 후 재료 목록 유지 (DB 영속성)
[ ] 추천받기 버튼 → /recommend 페이지 이동 + 추천 결과 정상 표시
```

---

### 작업 4-3. NFR 항목 검증

| NFR | 검증 방법 | 기준 |
|---|---|---|
| NFR-SEC-002 | 토큰 없이 `GET /api/fridge/search?q=계란` 호출 | HTTP 401 응답 |
| NFR-USE-001 | 로그인 → 재료 추가(기능 1·3 활용) → 추천받기 흐름 시간 측정 | 3분 이내 완료 |
| NFR-USE-002 | 375px · 768px · 1920px 브라우저 너비에서 `flex flex-wrap` 확인 | 레이아웃 깨짐 없음 |

NFR-SEC-002 자동 확인 (bash):
```bash
curl -s -o /dev/null -w "%{http_code}" \
  "http://localhost:8000/api/fridge/search?q=계란"
# 출력이 401이어야 함
```

```
[ ] NFR-SEC-002: 미인증 /fridge/search → 401
[ ] NFR-USE-001: 재료 추가 → 추천 흐름 3분 이내 완료
[ ] NFR-USE-002: 375px · 768px · 1920px 레이아웃 정상
```

---

### 작업 4-4. `ruff check .` 전체 실행

```bash
cd backend && ruff check .
```

확인 항목:
```
[ ] Python 코드 전체 lint 오류 0건
[ ] fridge_service.py 신규 함수 스타일 준수
[ ] fridge.py 신규 엔드포인트 스타일 준수
```

> Day 4-4는 검증 작업 자체이므로 별도 테스트 항목 없음.

---

### Day 4 완료 체크
```
[ ] 브라우저 기능 1~7 전체 정상 동작
[ ] 기존 기능(추가·삭제·전체삭제·자동완성·추천) 회귀 없음
[ ] NFR-SEC-002 미인증 401 확인
[ ] NFR-USE-001 3분 이내 흐름 확인
[ ] NFR-USE-002 반응형 레이아웃 확인
[ ] ruff check . — 0 errors
```

---

## 전체 일정 요약

| 일차 | 작업 번호 | 파일 | 성격 | 생성할 테스트 파일 | 테스트 방법 |
|---|---|---|---|---|---|
| Day 1 | 기능 2 | `fridge_service.py` | 수정 | `tests/unit/test_fridge_service.py` | pytest unit |
| Day 1 | 기능 2 | `fridge.py` | 수정 | — | python 스니펫 + 수동 |
| Day 1 | 기능 2 | `lib/api.ts` | 수정 | — | tsc + grep |
| Day 1 | 기능 5·6·7 | `FridgeChip.tsx` | 수정 | `__tests__/FridgeChip.test.tsx` | Jest + tsc |
| Day 2 | 기능 1 | `fridge/page.tsx` | 수정 | — | tsc + 수동 |
| Day 2 | 기능 3 | `fridge/page.tsx` | 수정 | — | tsc + 수동 |
| Day 2 | 기능 4 | `fridge/page.tsx` | 수정 | — | tsc + 수동 |
| Day 2 | 기능 5 | `fridge/page.tsx` | 수정 | — | tsc + 수동 |
| Day 3 | 기능 6 | `fridge/page.tsx` | 수정 | — | tsc + 수동 |
| Day 3 | 기능 7 | `fridge/page.tsx` | 수정 | — | tsc + 수동 |
| Day 3 | — | pytest -q + ruff | 백엔드 검증 | — | — |
| Day 3 | — | npx tsc + Jest | 프론트엔드 검증 | — | — |
| Day 4 | — | 브라우저 E2E | 기능 1~7 검증 | — | — |
| Day 4 | — | 회귀 검증 | 기존 기능 | — | — |
| Day 4 | — | NFR 검증 | 비기능 요구사항 | — | — |
| Day 4 | — | ruff check . | 코드 품질 전체 | — | — |

---

## 주의사항

- **작업 1-4(`FridgeChip.tsx`)는 Day 2 기능 5와 Day 3 기능 6·7이 모두 의존한다.** Day 1 내 반드시 완료. FridgeChip에 props가 없으면 page.tsx 수정 시 TypeScript 오류 발생.
- **작업 1-2(`fridge.py`)는 1-1 완료 후 진행.** `search_ingredient_suggestions()` 없이 라우터가 import 오류 발생.
- `fridge/page.tsx`는 기능 1·3·4·5·6·7이 모두 집중된다. Day 2~3에 걸쳐 순차 추가하며, 각 기능 추가 후 즉시 `npx tsc --noEmit` 실행 권장.
- 각 일차 완료 후 `git commit` 권장 — 롤백 지점 확보.
