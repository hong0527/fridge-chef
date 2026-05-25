# Day 1 회고록 (Day1_fridge.md)

작업 브랜치: `rok-fridge`
작업 기준 문서: `process(fridge).md` Day 1
작업 일자: 2026-05-23

---

## 1. 수행한 행동 요약

| 순서 | 작업 | 대상 파일 | 종류 |
|---|---|---|---|
| 1-1 | 재료 자동완성 서비스 함수 추가 | `backend/app/services/fridge_service.py` | 수정 |
| 1-2 | 자동완성 검색 엔드포인트 추가 | `backend/app/api/fridge.py` | 수정 |
| 1-3 | 자동완성 API 호출 URL 수정 | `frontend/lib/api.ts` | 수정 |
| 1-4 | FridgeChip 신규 props 전체 추가 | `frontend/components/FridgeChip.tsx` | 수정 |

생성된 파일: 없음
삭제된 파일: 없음

---

## 2. 파일별 변경 상세

---

### 2-1. `backend/app/services/fridge_service.py`

**변경 종류**: 수정 (함수 추가)

**변경 전 상태**
- `list_for_user()`, `add_for_user()`, `delete_for_user()` 3개 함수만 존재
- 재료 검색 기능 없음

**변경 후 상태**
- `SYNONYM_MAP` import 추가
- `search_ingredient_suggestions(q, limit)` 함수 신규 추가

**추가된 코드**
```python
from app.core.synonym_map import SYNONYM_MAP, normalize  # SYNONYM_MAP 추가

def search_ingredient_suggestions(q: str, limit: int = 8) -> list[str]:
    needle = q.strip().lower()
    if not needle:
        return []
    seen: set[str] = set()
    results: list[str] = []
    for synonym, canonical in SYNONYM_MAP.items():
        if needle in synonym.lower() and synonym not in seen:
            seen.add(synonym)
            results.append(synonym)
        if needle in canonical.lower() and canonical not in seen:
            seen.add(canonical)
            results.append(canonical)
        if len(results) >= limit:
            break
    return results
```

**이 코드가 동작시키는 기능**
재료 입력창에 글자를 타이핑할 때 나타나는 자동완성 제안 목록의 핵심 로직이다.
- 사용자가 "달"을 입력하면 SYNONYM_MAP에서 "달걀"(동의어)을 찾아 "달걀" 자체를 반환한다.
- 사용자가 "계"를 입력하면 정규형 "계란"을 찾아 반환한다.
- 동의어·정규형 양방향 검색으로 사용자가 어떤 표현을 써도 제안이 나온다.
- 최대 8개까지만 반환해 응답을 가볍게 유지한다.

**적용된 이슈 수정**
- RF-01: 기존 `workList(fridge).md`는 검색 로직을 라우터(`fridge.py`)에 직접 작성해 4계층 구조(SDD §1.3) 위반이었다. 비즈니스 로직을 Service Layer인 이 파일로 분리했다.
- RF-04: 기존 계획은 동의어("달걀") 입력 시 정규형("계란")을 반환했다. 사용자가 "달"을 입력했는데 "계란"이 나오면 혼란스럽다. 동의어는 동의어 자체를 반환하도록 수정했다.

---

### 2-2. `backend/app/api/fridge.py`

**변경 종류**: 수정 (엔드포인트 추가)

**변경 전 상태**
- `GET /api/fridge`, `POST /api/fridge`, `DELETE /api/fridge/{id}` 3개 엔드포인트
- 자동완성 엔드포인트 없음 → 프론트엔드가 `/api/ingredients/search`를 호출해도 404 반환

**변경 후 상태**
- `GET /api/fridge/search?q=` 엔드포인트 추가
- `_: User = Depends(get_current_user)` 인증 적용

**추가된 코드**
```python
@router.get("/search")
async def search_ingredients(
    q: str = "",
    _: User = Depends(get_current_user),  # RF-02: 인증 적용
) -> dict:
    """재료 이름 자동완성 — SYNONYM_MAP 기반."""
    results = fridge_service.search_ingredient_suggestions(q)
    return {"suggestions": results}
```

> `_` 표기: 인증 확인 목적으로만 사용하고 실제 user 데이터는 불필요하므로 관례상 `_`로 선언했다.

**이 코드가 동작시키는 기능**
프론트엔드 자동완성 드롭다운이 실제로 서버 결과를 받아오는 HTTP 연결 지점이다.
- `GET /api/fridge/search?q=달` 요청 → `{"suggestions": ["달걀", ...]}` 응답
- JWT 토큰 없이 호출하면 401 반환 → 비인증 사용자가 재료 목록을 무단 조회하지 못한다.
- 서비스 함수를 호출하는 것 외에 별도 로직 없음 (Presentation Layer 책임만 수행).

**적용된 이슈 수정**
- RF-01: 검색 로직을 라우터에 두지 않고 `fridge_service.search_ingredient_suggestions()` 호출로만 처리했다.
- RF-02: 기존 fridge 라우터의 모든 엔드포인트는 `get_current_user` 인증이 필수인데, 자동완성 엔드포인트만 인증 없이 작성될 뻔했다. 동일하게 적용했다.

**작업 중 발생한 사항**
IDE에서 `user: User = Depends(...)` 선언 후 `user`를 실제로 사용하지 않는다는 힌트가 표시됐다. 의도적으로 인증 확인만 하는 것이므로 Python 관례에 따라 `_`로 변경해 해소했다.

---

### 2-3. `frontend/lib/api.ts`

**변경 종류**: 수정 (URL 1줄 변경)

**변경 전 상태**
```typescript
const { data } = await api.get<{ suggestions: string[] }>('/ingredients/search', {
```

**변경 후 상태**
```typescript
const { data } = await api.get<{ suggestions: string[] }>('/fridge/search', {
```

**이 코드가 동작시키는 기능**
재료 입력창에서 타이핑 시 자동완성 제안을 서버에서 가져오는 API 호출 경로다.
- 변경 전: `/api/ingredients/search` → 백엔드에 존재하지 않는 경로 → 404 오류 → 자동완성 무응답
- 변경 후: `/api/fridge/search` → 2-2에서 추가한 엔드포인트 → 정상 동작

이 변경 하나로 기존에 항상 실패하던 자동완성 기능이 실제로 서버 결과를 받아오게 된다.

---

### 2-4. `frontend/components/FridgeChip.tsx`

**변경 종류**: 수정 (전체 재작성 수준의 props 확장)

**변경 전 인터페이스**
```typescript
interface FridgeChipProps {
  name: string;
  onRemove?: () => void;
  variant?: 'default' | 'used' | 'missing' | 'compact';
  className?: string;
}
```

**변경 후 인터페이스**
```typescript
interface FridgeChipProps {
  name: string;
  onRemove?: () => void;
  onEdit?: () => void;           // 기능 6: 인라인 편집 진입
  selectable?: boolean;          // 기능 7: 선택 모드 여부
  selected?: boolean;            // 기능 7: 현재 선택 상태
  onSelect?: () => void;         // 기능 7: 선택 토글 콜백
  variant?: 'default' | 'used' | 'missing' | 'compact';
  categoryColor?: 'vegetable' | 'meat' | 'seafood' | 'dairy' | 'seasoning';  // 기능 5
  className?: string;
}
```

**추가된 로직 3가지**

**(A) 카테고리 색상 스타일 맵 (기능 5용)**
```typescript
const categoryStyles = {
  vegetable: 'border-green-600 bg-green-50 ...',
  meat:      'border-red-500  bg-red-50 ...',
  seafood:   'border-blue-500 bg-blue-50 ...',
  dairy:     'border-yellow-500 bg-yellow-50 ...',
  seasoning: 'border-orange-400 bg-orange-50 ...',
}
```

**(B) RF-07 그림자 조건 수정 (기능 5용)**
```typescript
// 변경 전
variant !== 'compact' && 'shadow-[0_2px_0_0_rgba(26,23,21,0.85)]'

// 변경 후
variant !== 'compact' && !categoryColor && 'shadow-[0_2px_0_0_rgba(26,23,21,0.85)]'
```

**(C) 선택 모드 시 X 버튼 → 체크박스 교체 (기능 7용)**
```typescript
{selectable ? (
  <span className={cn('...', selected ? 'bg-gochu-500 ...' : 'border-clay-400')}>
    {selected && <span className="text-[10px]">✓</span>}
  </span>
) : onRemove && (
  <button ...><X /></button>
)}
```

**각 prop이 동작시키는 기능**

| 추가 prop | 동작하는 기능 | 설명 |
|---|---|---|
| `categoryColor` | 기능 5 카테고리 색상 | 채소는 초록, 육류는 빨강 등 카테고리별 칩 색상 구분 |
| `onEdit` | 기능 6 인라인 편집 | 칩 이름 클릭 시 편집 모드 진입 콜백 |
| `selectable` | 기능 7 선택 모드 | true일 때 칩 클릭으로 선택/해제 가능 |
| `selected` | 기능 7 선택 상태 | true일 때 gochu-500 강조 테두리 표시 |
| `onSelect` | 기능 7 선택 토글 | 선택 모드에서 칩 클릭 시 호출되는 콜백 |

**RF-07 수정의 의미**
`categoryColor`가 지정된 칩은 밝은 파스텔 배경(bg-green-50 등)을 가진다. 여기에 `rgba(26,23,21,0.85)` 거의 검정에 가까운 그림자가 함께 적용되면 기본 칩(bg-cream-50, 어두운 계열)보다 시각적으로 훨씬 강조되어 어색해 보인다. 카테고리 색상이 있을 때는 그림자를 제거해 통일감을 유지한다.

**기존 기능 유지**
- `variant` prop은 그대로 동작 (`used`, `missing`, `compact` 등)
- `onRemove` X 버튼은 `selectable`이 false일 때 그대로 표시
- 랜딩 페이지(`page.tsx`)의 데모 칩(`variant="used"`, `variant="missing"`)은 신규 props를 사용하지 않으므로 시각적 변화 없음

---

## 3. 테스트 내역

---

### 테스트 1 — `fridge_service.py` 함수 동작 확인

**무엇을 확인하기 위한 테스트인가**
`search_ingredient_suggestions()`가 4가지 핵심 조건을 모두 만족하는지 확인한다.

| 케이스 | 입력 | 기대 결과 | 확인 목적 |
|---|---|---|---|
| 빈 쿼리 | `''` | `[]` | 빈 입력 시 불필요한 연산 없이 즉시 반환 |
| 동의어 매칭 | `'달걀'` | `'달걀'` 포함 | RF-04: 정규형("계란")이 아닌 동의어 자체 반환 |
| 정규형 매칭 | `'계란'` | `'계란'` 포함 | 정규형 직접 입력 시 정규형 반환 |
| limit | `'고기'` | 길이 ≤ 8 | 결과가 최대 8개를 넘지 않음 |

**실행 명령 및 결과**
```bash
python -c "from app.services.fridge_service import search_ingredient_suggestions; ..."
# 결과: fridge_service 테스트 통과
```

---

### 테스트 2 — `fridge.py` 기존 API 회귀 테스트

**무엇을 확인하기 위한 테스트인가**
`fridge_service.py`에 `SYNONYM_MAP` import와 신규 함수를 추가하면서 기존 `add_for_user`, `list_for_user`, `delete_for_user`에 영향을 주지 않았는지 확인한다. 또한 신규 `/search` 엔드포인트가 기존 CRUD 엔드포인트와 충돌하지 않는지 확인한다.

**실행 명령 및 결과**
```bash
pytest tests/api/test_fridge_api.py -q
# 결과: 12 passed, 2 xfailed, 0 failed
```

`xfailed`는 원래부터 미구현 표시된 테스트로 이번 작업과 무관하다.

---

### 테스트 3 — TypeScript 타입 체크

**무엇을 확인하기 위한 테스트인가**
`FridgeChip.tsx`에 5개 props를 추가하고 `api.ts`의 URL을 수정한 후, 기존 코드에서 이 컴포넌트를 사용하는 모든 곳(`page.tsx` 데모 칩, 랜딩 페이지 등)이 TypeScript 오류 없이 컴파일되는지 확인한다.
새 props는 모두 optional(`?`)로 선언했으므로 기존 호출 코드는 수정 없이 통과해야 한다.

**실행 명령 및 결과**
```bash
cd frontend && npx tsc --noEmit
# 결과: 출력 없음 (0 errors)
```

---

### 테스트 4 — 수동: Swagger UI 엔드포인트 노출 확인

**무엇을 확인하기 위한 테스트인가**
`docker-compose up --build` 후 실제 서버에 `/api/fridge/search` 경로가 정상적으로 등록됐는지 확인한다. FastAPI가 라우터를 자동 파싱하므로 Swagger에 노출되면 엔드포인트가 정상 등록된 것이다.

**확인 방법**: `http://localhost:8000/docs` 접속 → `GET /api/fridge/search` 항목 존재
**결과**: 확인됨

---

### 테스트 5 — 수동: 미인증 401 응답 확인 (NFR-SEC-002)

**무엇을 확인하기 위한 테스트인가**
`Depends(get_current_user)`가 실제 요청에서 동작하는지 확인한다. JWT 토큰 없이 호출했을 때 401이 반환되지 않으면 인증 로직이 빠진 것이다.

**확인 방법**: 브라우저 주소창에 `http://localhost:8000/api/fridge/search?q=계란` 입력
**결과**: `{"detail":"토큰이 필요합니다."}` — 401 응답 확인됨

---

## 4. 현재 리스크

| # | 리스크 | 심각도 | 설명 |
|---|---|---|---|
| R-01 | `GET /search` 라우터 순서 충돌 가능성 | 낮음 | FastAPI는 라우터를 등록 순서대로 매칭한다. `DELETE /{ingredient_id}` 뒤에 `GET /search`를 추가했는데, `ingredient_id` 경로가 문자열 "search"를 정수로 변환 시도할 수 있다. 현재 `ingredient_id`는 `int` 타입이므로 "search"는 변환 실패 → `GET /search`로 넘어가 정상 동작한다. 단, 향후 경로 타입이 바뀌면 충돌 가능. |
| R-02 | SYNONYM_MAP 전체 순회 성능 | 낮음 | SYNONYM_MAP이 현재 100쌍 내외여서 문제없지만, 향후 수천 쌍으로 늘어나면 매 요청마다 전체 순회 시 지연 발생 가능. 현재 규모에서는 무시 가능. |
| R-03 | FridgeChip 신규 props 미사용 상태 | 낮음 | `categoryColor`, `onEdit`, `selectable`, `selected`, `onSelect`가 추가됐지만 `fridge/page.tsx`에서 아직 사용하지 않는다. Day 2~3에서 page.tsx를 수정할 때 연결 예정. |

---

## 5. 후속 작업

| 일차 | 작업 | 의존 관계 |
|---|---|---|
| Day 2 | `fridge/page.tsx`에 기능 1(빠른 추가), 3(양념 토글), 4(빈 상태), 5(카테고리 색상) 추가 | Day 1 FridgeChip 완료 후 가능 |
| Day 3 | `fridge/page.tsx`에 기능 6(인라인 편집), 7(선택 삭제) 추가 | Day 1 FridgeChip 완료 후 가능 |
| Day 3 | `pytest -q` 전체 + `npx tsc --noEmit` 전체 검증 | Day 3 작업 완료 후 |
| Day 4 | 브라우저 E2E 검증 + NFR 항목 전체 확인 | Day 3 완료 후 |
| 미결 | 자동완성 인증 토큰 확인 테스트 | 로그인 후 `/fridge/search?q=` 호출 → 200 + suggestions 반환 확인 필요 |

---

## 6. Day 1 완료 체크리스트

```
[✅] fridge_service.py — search_ingredient_suggestions() 추가
[✅] fridge_service.py — python 스니펫 테스트 4가지 통과
[✅] fridge.py — GET /api/fridge/search 엔드포인트 추가 (인증 포함)
[✅] fridge.py — pytest tests/api/test_fridge_api.py 12 passed, 0 failed
[✅] api.ts — URL /ingredients/search → /fridge/search 변경
[✅] api.ts — npx tsc --noEmit 0 errors
[✅] FridgeChip.tsx — 5개 신규 props + categoryStyles + RF-07 그림자 조건 추가
[✅] FridgeChip.tsx — npx tsc --noEmit 0 errors
[✅] 수동: http://localhost:8000/docs → GET /api/fridge/search 노출 확인
[✅] 수동: 미인증 호출 → {"detail":"토큰이 필요합니다."} 401 확인
```
