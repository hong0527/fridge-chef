# 냉장고 기능 UX 개선 구현 계획서 v2

## 작업 개요

`workList(fridge).md` 대비 `research(fridge).md` 이슈 RF-01~RF-07 반영.
백엔드 2건·프론트엔드 3건 파일을 수정한다.

---

## workList(fridge).md 대비 변경 사항 요약

| 구분 | workList(fridge).md | workList2(fridge).md |
|---|---|---|
| 검색 로직 위치 | 라우터(`fridge.py`)에서 직접 처리 | **`fridge_service.py`로 분리** (RF-01) |
| 검색 엔드포인트 인증 | 없음 | **`Depends(get_current_user)` 추가** (RF-02) |
| 검색 결과 형태 | 정규형만 반환 | **동의어·정규형 모두 반환** (RF-04) |
| 빠른 추가 중복 검사 | `raw_name`만 비교 | **`normalized_name`도 비교** (RF-05) |
| 편집 순서 | 삭제 → 추가 (소실 위험) | **추가 → 성공 후 삭제** (RF-03) |
| 편집 후 목록 순서 | 맨 뒤에 추가 | **원래 위치(index)에 삽입** (RF-06) |
| 카테고리 칩 그림자 | categoryColor 시 어두운 그림자 유지 | **categoryColor 시 그림자 제거** (RF-07) |
| `fridge_service.py` | 변경 없음 | **검색 함수 추가** (RF-01) |

---

## 전체 작업 파일 목록

| 우선순위 | 기능 | 파일 | 작업 종류 | 완료 |
|---|---|---|---|---|
| 1 | 자주 쓰는 재료 빠른 추가 버튼 | `frontend/app/(main)/fridge/page.tsx` | 수정 | [ ] |
| 2 | 서버 자동완성 — 검색 서비스 함수 | `backend/app/services/fridge_service.py` | **수정 (함수 추가)** | [ ] |
| 2 | 서버 자동완성 — 검색 엔드포인트 | `backend/app/api/fridge.py` | 수정 | [ ] |
| 2 | 서버 자동완성 URL 수정 | `frontend/lib/api.ts` | 수정 | [ ] |
| 3 | 기본 양념 일괄 추가 토글 | `frontend/app/(main)/fridge/page.tsx` | 수정 | [ ] |
| 4 | 빈 상태 안내 개선 | `frontend/app/(main)/fridge/page.tsx` | 수정 | [ ] |
| 5 | 카테고리별 색상 구분 | `frontend/components/FridgeChip.tsx` | 수정 | [ ] |
| 5 | 카테고리 매핑·색상 적용 | `frontend/app/(main)/fridge/page.tsx` | 수정 | [ ] |
| 6 | 재료 수정(인라인 편집) | `frontend/components/FridgeChip.tsx` | 수정 | [ ] |
| 6 | 편집 상태 관리 | `frontend/app/(main)/fridge/page.tsx` | 수정 | [ ] |
| 7 | 선택 삭제 기능 | `frontend/components/FridgeChip.tsx` | 수정 | [ ] |
| 7 | 선택 모드 상태 관리 | `frontend/app/(main)/fridge/page.tsx` | 수정 | [ ] |

> `fridge/page.tsx`는 기능 1·3·4·5·6·7이 모두 집중된다.
> `fridge_service.py`는 기능 2(RF-01)에서 신규 추가된 파일이다.

---

## 상세 작업 내용

---

### 기능 1 — 자주 쓰는 재료 빠른 추가 버튼

**파일 경로**
- [frontend/app/(main)/fridge/page.tsx](frontend/app/(main)/fridge/page.tsx)

**변경 이유 (RF-05 반영)**
`workList(fridge).md`의 중복 검사가 `raw_name`만 비교해, 사용자가 "달걀"을 직접 입력 후 빠른 추가 버튼의 "계란"을 클릭하면 중복 감지가 안 됐다. `normalized_name`도 함께 비교하도록 수정한다.

**접근 방식 상세설명**

`QUICK_INGREDIENTS` 상수를 정규형 기준으로 정의하고, 중복 검사 시 `raw_name`과 `normalized_name` 두 가지를 모두 확인한다. 기존 `handleAdd(name)` 함수를 그대로 재사용해 로직 중복이 없다.

**코드 스니펫**

`fridge/page.tsx` 상단 상수 추가:
```tsx
const QUICK_INGREDIENTS = [
  '계란', '대파', '마늘', '양파', '두부',
  '돼지고기', '김치', '당근', '감자', '참기름',
];
```

검색 인풋 `</div>` 닫힘 태그 바로 아래에 추가:
```tsx
{/* 빠른 추가 버튼 */}
<div className="mt-3">
  <p className="text-xs font-semibold text-clay-500 dark:text-clay-400 mb-2">
    자주 쓰는 재료
  </p>
  <div className="flex flex-wrap gap-1.5">
    {QUICK_INGREDIENTS.map((name) => {
      // RF-05: raw_name + normalized_name 모두 비교
      const added = ingredients.some(
        (i) => i.raw_name === name || i.normalized_name === name
      );
      return (
        <button
          key={name}
          type="button"
          onClick={() => !added && handleAdd(name)}
          disabled={added || adding}
          className={`px-2.5 py-1 rounded-full text-xs font-semibold border-2 transition-colors ${
            added
              ? 'border-clay-300 text-clay-300 dark:border-clay-600 dark:text-clay-600 cursor-default'
              : 'border-clay-700 text-clay-700 dark:border-cream-200 dark:text-cream-200 hover:bg-gochu-500 hover:text-white hover:border-gochu-500'
          }`}
        >
          {added ? '✓ ' : '+ '}{name}
        </button>
      );
    })}
  </div>
</div>
```

---

### 기능 2 — 서버 자동완성

**파일 경로**
- [backend/app/services/fridge_service.py](backend/app/services/fridge_service.py) — **신규 함수 추가 (RF-01)**
- [backend/app/api/fridge.py](backend/app/api/fridge.py) — 엔드포인트 추가 (RF-01, RF-02)
- [frontend/lib/api.ts](frontend/lib/api.ts) — URL 수정

**변경 이유 (RF-01, RF-02, RF-04 반영)**
- RF-01: 검색 로직이 라우터에서 `SYNONYM_MAP`을 직접 순회하는 것은 4계층 구조(SDD §1.3) 위반. 비즈니스 로직은 Service Layer인 `fridge_service.py`로 분리.
- RF-02: 기존 fridge 라우터의 모든 엔드포인트는 `Depends(get_current_user)` 필수. 검색 엔드포인트만 인증 없이 작성된 것은 일관성 위반.
- RF-04: 동의어("달걀") 입력 시 정규형("계란")만 반환하면 사용자가 기대하는 결과와 다르다. 동의어 자체도 반환한다.

**접근 방식 상세설명**

`fridge_service.py`에 `search_ingredient_suggestions()` 함수를 추가한다. 이 함수는 입력 키워드를 `SYNONYM_MAP`의 동의어(key)와 정규형(value) 양쪽에서 검색해, **매칭된 형태 그대로** 반환한다. 예를 들어 "달" 입력 시 동의어 "달걀"이 매칭되면 "달걀"을 반환하고, 정규형 "계란"이 직접 매칭되면 "계란"을 반환한다. 라우터는 이 서비스 함수를 호출하는 역할만 한다.

**코드 스니펫**

`backend/app/services/fridge_service.py` — import 추가 및 함수 추가:
```python
from app.core.synonym_map import SYNONYM_MAP  # import 블록에 추가


def search_ingredient_suggestions(q: str, limit: int = 8) -> list[str]:
    """SYNONYM_MAP 기반 재료 이름 자동완성 (RF-01: Service Layer 분리, RF-04: 동의어 반환).

    동의어("달걀") 입력 시 동의어 자체를 반환.
    정규형("계란") 입력 시 정규형을 반환.
    """
    needle = q.strip().lower()
    if not needle:
        return []
    seen: set[str] = set()
    results: list[str] = []
    for synonym, canonical in SYNONYM_MAP.items():
        # 동의어 매칭 → 동의어 자체 반환 (사용자가 입력 중인 형태 유지)
        if needle in synonym.lower() and synonym not in seen:
            seen.add(synonym)
            results.append(synonym)
        # 정규형 매칭 → 정규형 반환
        if needle in canonical.lower() and canonical not in seen:
            seen.add(canonical)
            results.append(canonical)
        if len(results) >= limit:
            break
    return results
```

`backend/app/api/fridge.py` — 엔드포인트 추가 (파일 맨 아래):
```python
@router.get("/search")
async def search_ingredients(
    q: str = "",
    user: User = Depends(get_current_user),  # RF-02: 인증 추가
) -> dict:
    """재료 이름 자동완성 — SYNONYM_MAP 100쌍 기반."""
    results = fridge_service.search_ingredient_suggestions(q)
    return {"suggestions": results}
```

`frontend/lib/api.ts` — URL 수정:
```typescript
// 변경 전
const { data } = await api.get<{ suggestions: string[] }>('/ingredients/search', {

// 변경 후
const { data } = await api.get<{ suggestions: string[] }>('/fridge/search', {
```

---

### 기능 3 — 기본 양념 일괄 추가 토글

**파일 경로**
- [frontend/app/(main)/fridge/page.tsx](frontend/app/(main)/fridge/page.tsx)

**접근 방식 상세설명**

소금·간장·참기름처럼 거의 모든 가정에 항상 있는 조미료를 매번 타이핑하는 불편함을 해소한다. 토글 버튼 하나로 `BASIC_SEASONINGS` 배열 전체를 일괄 추가/제거한다. `basicSeasoning` boolean 상태로 현재 적용 여부를 추적하고, 이미 냉장고에 없는 재료만 추가하며 이미 있는 재료는 건너뛴다. 비활성화 시에는 `BASIC_SEASONINGS`에 속하면서 냉장고에 있는 재료만 제거해 사용자가 별도로 추가한 재료를 보존한다.

**코드 스니펫**

상수 및 상태 추가:
```tsx
const BASIC_SEASONINGS = ['소금', '간장', '참기름', '설탕', '후추', '식용유'];
const [basicSeasoning, setBasicSeasoning] = useState(false);
```

핸들러 추가:
```tsx
const handleToggleBasicSeasoning = async () => {
  if (!basicSeasoning) {
    for (const name of BASIC_SEASONINGS) {
      if (!ingredients.some((i) => i.raw_name === name)) {
        try {
          const added = await addIngredient(name);
          setIngredients((prev) => [...prev, added]);
        } catch {
          // 개별 실패 무시하고 계속 진행
        }
      }
    }
    setBasicSeasoning(true);
  } else {
    const toRemove = ingredients.filter((i) =>
      BASIC_SEASONINGS.includes(i.raw_name)
    );
    setIngredients((prev) =>
      prev.filter((i) => !BASIC_SEASONINGS.includes(i.raw_name))
    );
    for (const ing of toRemove) {
      await removeIngredient(ing.id);
    }
    setBasicSeasoning(false);
  }
};
```

UI 버튼 추가:
```tsx
<button
  type="button"
  onClick={handleToggleBasicSeasoning}
  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border-2 transition-colors ${
    basicSeasoning
      ? 'bg-gochu-500 border-gochu-500 text-white'
      : 'border-clay-700 text-clay-700 dark:border-cream-200 dark:text-cream-200 hover:border-gochu-500'
  }`}
>
  {basicSeasoning ? '✓ 기본 양념 포함 중' : '+ 기본 양념 한번에 추가'}
</button>
```

---

### 기능 4 — 빈 상태 안내 개선

**파일 경로**
- [frontend/app/(main)/fridge/page.tsx](frontend/app/(main)/fridge/page.tsx)

**접근 방식 상세설명**

현재 빈 냉장고 상태는 텍스트 안내만 표시해 사용자가 다시 입력창으로 돌아가야 한다. 빈 상태 블록 안에 자주 쓰는 재료 빠른 추가 버튼을 직접 삽입해, 처음 접속한 사용자도 클릭 한 번으로 재료를 추가할 수 있도록 진입 장벽을 낮춘다.

**코드 스니펫**

기존 빈 상태 블록 전체 교체:
```tsx
{/* 변경 전 */}
) : ingredients.length === 0 ? (
  <div className="rounded-3xl border-2 border-dashed border-clay-400 dark:border-cream-100/30 bg-cream-50/40 dark:bg-clay-800/40 p-10 text-center">
    <Refrigerator className="h-10 w-10 mx-auto text-clay-400" aria-hidden="true" />
    <p className="mt-3 font-semibold">아직 비어있어요</p>
    <p className="text-sm text-clay-600 dark:text-clay-400 mt-1">
      위 입력창에 재료 이름을 넣어보세요.
    </p>
  </div>

{/* 변경 후 */}
) : ingredients.length === 0 ? (
  <div className="rounded-3xl border-2 border-dashed border-clay-400 dark:border-cream-100/30 bg-cream-50/40 dark:bg-clay-800/40 p-8 text-center">
    <Refrigerator className="h-10 w-10 mx-auto text-clay-400" aria-hidden="true" />
    <p className="mt-3 font-semibold">아직 비어있어요</p>
    <p className="text-sm text-clay-600 dark:text-clay-400 mt-1">
      자주 쓰는 재료로 빠르게 시작해보세요.
    </p>
    <div className="mt-4 flex flex-wrap gap-2 justify-center">
      {['계란', '대파', '마늘', '양파', '두부', '김치'].map((name) => (
        <button
          key={name}
          type="button"
          onClick={() => handleAdd(name)}
          disabled={adding}
          className="px-3 py-1.5 rounded-full text-sm border-2 border-clay-600 dark:border-cream-200 text-clay-700 dark:text-cream-200 hover:bg-gochu-500 hover:text-white hover:border-gochu-500 transition-colors"
        >
          + {name}
        </button>
      ))}
    </div>
  </div>
```

---

### 기능 5 — 카테고리별 색상 구분

**파일 경로**
- [frontend/components/FridgeChip.tsx](frontend/components/FridgeChip.tsx)
- [frontend/app/(main)/fridge/page.tsx](frontend/app/(main)/fridge/page.tsx)

**변경 이유 (RF-07 반영)**
`workList(fridge).md`에서 `categoryColor` 적용 시 기존 어두운 그림자(`rgba(26,23,21,0.85)`)가 밝은 카테고리 배경과 어색하게 보였다. `categoryColor` 지정 시 그림자를 제거한다.

**접근 방식 상세설명**

`FridgeChip`에 `categoryColor` prop을 추가한다. 기존 `variant` 시스템은 유지하면서, `categoryColor`가 지정된 경우 카테고리 스타일을 적용하고 그림자를 생략한다. `fridge/page.tsx`에 재료명 → 카테고리 매핑을 정의해 칩 렌더링 시 전달한다.

**코드 스니펫**

`frontend/components/FridgeChip.tsx` — props 및 스타일 확장:
```tsx
interface FridgeChipProps {
  name: string;
  onRemove?: () => void;
  onEdit?: () => void;
  selectable?: boolean;
  selected?: boolean;
  onSelect?: () => void;
  variant?: 'default' | 'used' | 'missing' | 'compact';
  categoryColor?: 'vegetable' | 'meat' | 'seafood' | 'dairy' | 'seasoning';
  className?: string;
}

// 컴포넌트 내부 — 카테고리 스타일 맵 추가
const categoryStyles = {
  vegetable: 'border-green-600 bg-green-50 dark:bg-green-950/30 text-green-800 dark:text-green-300',
  meat:      'border-red-500  bg-red-50   dark:bg-red-950/30  text-red-800  dark:text-red-300',
  seafood:   'border-blue-500 bg-blue-50  dark:bg-blue-950/30 text-blue-800 dark:text-blue-300',
  dairy:     'border-yellow-500 bg-yellow-50 dark:bg-yellow-950/30 text-yellow-800 dark:text-yellow-300',
  seasoning: 'border-orange-400 bg-orange-50 dark:bg-orange-950/30 text-orange-700 dark:text-orange-300',
} as const;

// className cn() 호출 수정 (RF-07: categoryColor 시 그림자 제거)
className={cn(
  'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-chip border-2 font-medium text-sm whitespace-nowrap',
  'transition-transform duration-150 hover:-translate-y-0.5',
  // RF-07: categoryColor 지정 시 어두운 그림자 제거
  variant !== 'compact' && !categoryColor && 'shadow-[0_2px_0_0_rgba(26,23,21,0.85)]',
  categoryColor ? categoryStyles[categoryColor] : styles[variant],
  selected && 'border-gochu-500 ring-2 ring-gochu-500/40',
  selectable && 'cursor-pointer',
  className,
)}
```

`frontend/app/(main)/fridge/page.tsx` — 카테고리 매핑 추가:
```tsx
const INGREDIENT_CATEGORY: Record<string, 'vegetable' | 'meat' | 'seafood' | 'dairy' | 'seasoning'> = {
  대파: 'vegetable', 양파: 'vegetable', 마늘: 'vegetable', 당근: 'vegetable',
  감자: 'vegetable', 두부: 'vegetable', 김치: 'vegetable', 애호박: 'vegetable',
  돼지고기: 'meat', 소고기: 'meat', 닭고기: 'meat',
  새우: 'seafood', 오징어: 'seafood', 고등어: 'seafood', 조개류: 'seafood',
  계란: 'dairy', 우유: 'dairy', 치즈: 'dairy', 버터: 'dairy',
  소금: 'seasoning', 간장: 'seasoning', 참기름: 'seasoning',
  설탕: 'seasoning', 후추: 'seasoning', 식용유: 'seasoning',
};

// 칩 렌더링 시 categoryColor 전달
<FridgeChip
  name={ing.raw_name}
  onRemove={selectMode ? undefined : () => handleRemove(ing.id)}
  onEdit={selectMode ? undefined : () => handleEditStart(ing.id, ing.raw_name)}
  selectable={selectMode}
  selected={selectedIds.has(ing.id)}
  onSelect={() => toggleSelectId(ing.id)}
  categoryColor={INGREDIENT_CATEGORY[ing.normalized_name]}
/>
```

---

### 기능 6 — 재료 인라인 편집

**파일 경로**
- [frontend/components/FridgeChip.tsx](frontend/components/FridgeChip.tsx)
- [frontend/app/(main)/fridge/page.tsx](frontend/app/(main)/fridge/page.tsx)

**변경 이유 (RF-03, RF-06 반영)**
- RF-03: `workList(fridge).md`의 삭제→추가 순서는 `addIngredient` 실패 시 재료가 영구 소실된다. **추가 먼저 → 성공 후 삭제** 순서로 변경한다.
- RF-06: 편집 완료 재료가 목록 맨 뒤로 이동하는 문제. `originalIndex`를 기억해 원래 위치에 삽입한다.

**접근 방식 상세설명**

`FridgeChip`에 `onEdit` prop을 추가해 이름 클릭 시 편집 콜백을 호출한다. `editingId` state로 현재 편집 중인 재료를 추적하고, 해당 위치에 인라인 `<input>`을 렌더링한다. 편집 완료 시 새 재료를 추가한 후 기존 재료를 삭제하며, `findIndex`로 원래 위치를 기억해 `splice`로 삽입한다.

**코드 스니펫**

`frontend/components/FridgeChip.tsx` — `onEdit` prop 추가:
```tsx
// name span — 클릭 시 편집 진입
<span
  className={cn('leading-none', onEdit && 'cursor-pointer hover:underline underline-offset-2')}
  onClick={onEdit}
  title={onEdit ? '클릭해서 편집' : undefined}
>
  {name}
</span>
```

`frontend/app/(main)/fridge/page.tsx` — 편집 상태 및 핸들러:
```tsx
const [editingId, setEditingId] = useState<number | null>(null);
const [editValue, setEditValue] = useState('');

const handleEditStart = (id: number, currentName: string) => {
  setEditingId(id);
  setEditValue(currentName);
};

// RF-03: 추가 먼저 → 성공 후 삭제 / RF-06: 원래 위치에 삽입
const handleEditSubmit = async (id: number) => {
  const newName = editValue.trim();
  const original = ingredients.find((i) => i.id === id);
  if (!newName || !original || newName === original.raw_name) {
    setEditingId(null);
    return;
  }
  // RF-06: 원래 인덱스 기억
  const originalIndex = ingredients.findIndex((i) => i.id === id);
  try {
    // RF-03: 추가 먼저 (실패해도 기존 재료 보존)
    const added = await addIngredient(newName);
    // RF-03: 추가 성공 후 기존 재료 삭제
    await removeIngredient(id);
    setIngredients((prev) => {
      const next = prev.filter((i) => i.id !== id);
      // RF-06: 원래 위치에 삽입
      next.splice(originalIndex, 0, added);
      return [...next];
    });
    toast.show(`'${original.raw_name}' → '${newName}' 수정됨`, 'success');
  } catch (err) {
    toast.show(apiErrorMessage(err), 'error');
  } finally {
    setEditingId(null);
  }
};

// 칩 목록 렌더링
{ingredients.map((ing) =>
  editingId === ing.id ? (
    <li key={ing.id}>
      <input
        autoFocus
        type="text"
        value={editValue}
        maxLength={20}
        onChange={(e) => setEditValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleEditSubmit(ing.id);
          if (e.key === 'Escape') setEditingId(null);
        }}
        onBlur={() => handleEditSubmit(ing.id)}
        className="px-3 py-1.5 rounded-chip border-2 border-gochu-500 bg-cream-50 dark:bg-clay-800 text-sm font-medium outline-none w-28"
      />
    </li>
  ) : (
    <li key={ing.id}>
      <FridgeChip
        name={ing.raw_name}
        onRemove={selectMode ? undefined : () => handleRemove(ing.id)}
        onEdit={selectMode ? undefined : () => handleEditStart(ing.id, ing.raw_name)}
        selectable={selectMode}
        selected={selectedIds.has(ing.id)}
        onSelect={() => toggleSelectId(ing.id)}
        categoryColor={INGREDIENT_CATEGORY[ing.normalized_name]}
      />
    </li>
  )
)}
```

---

### 기능 7 — 선택 삭제

**파일 경로**
- [frontend/components/FridgeChip.tsx](frontend/components/FridgeChip.tsx)
- [frontend/app/(main)/fridge/page.tsx](frontend/app/(main)/fridge/page.tsx)

**접근 방식 상세설명**

헤더 영역에 "선택 모드" 토글 버튼을 추가한다. 선택 모드 진입 시 각 칩에 체크박스가 표시되고, 칩 클릭으로 개별 선택/해제가 가능하다. 선택된 칩은 `gochu-500` 강조 테두리로 시각화한다. 선택 삭제는 기존 `removeIngredient(id)` 반복 호출로 구현해 별도 백엔드 엔드포인트가 필요없다. 선택 모드 종료 시 선택 목록은 초기화된다.

**코드 스니펫**

`frontend/components/FridgeChip.tsx` — 선택 관련 prop 추가:
```tsx
interface FridgeChipProps {
  name: string;
  onRemove?: () => void;
  onEdit?: () => void;
  selectable?: boolean;           // 선택 모드 여부
  selected?: boolean;             // 현재 선택 상태
  onSelect?: () => void;          // 선택 토글 콜백
  variant?: 'default' | 'used' | 'missing' | 'compact';
  categoryColor?: 'vegetable' | 'meat' | 'seafood' | 'dairy' | 'seasoning';
  className?: string;
}

// 컴포넌트 내부 — selected 시 강조 테두리 (RF-07: categoryColor 지정 시 그림자 제거 포함)
className={cn(
  'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-chip border-2 font-medium text-sm whitespace-nowrap',
  'transition-transform duration-150 hover:-translate-y-0.5',
  variant !== 'compact' && !categoryColor && 'shadow-[0_2px_0_0_rgba(26,23,21,0.85)]',
  categoryColor ? categoryStyles[categoryColor] : styles[variant],
  selected && 'border-gochu-500 ring-2 ring-gochu-500/40',
  selectable && 'cursor-pointer',
  className,
)}
onClick={selectable ? onSelect : undefined}

// X 버튼 — 선택 모드에서는 체크박스로 교체
{selectable ? (
  <span className={cn(
    'inline-flex h-4 w-4 items-center justify-center rounded border-2 transition-colors',
    selected ? 'bg-gochu-500 border-gochu-500 text-white' : 'border-clay-400'
  )}>
    {selected && <span className="text-[10px] leading-none">✓</span>}
  </span>
) : onRemove && (
  <button
    type="button"
    onClick={onRemove}
    aria-label={`${name} 재료 삭제`}
    className="inline-flex h-5 w-5 items-center justify-center rounded-full hover:bg-clay-900/10 dark:hover:bg-cream-100/15"
  >
    <X className="h-3.5 w-3.5" />
  </button>
)}
```

`frontend/app/(main)/fridge/page.tsx` — 선택 모드 상태 및 핸들러:
```tsx
const [selectMode, setSelectMode] = useState(false);
const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

const toggleSelectId = (id: number) => {
  setSelectedIds((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });
};

const handleDeleteSelected = async () => {
  const toDelete = ingredients.filter((i) => selectedIds.has(i.id));
  const prev = ingredients;
  setIngredients((p) => p.filter((i) => !selectedIds.has(i.id)));
  try {
    for (const ing of toDelete) {
      await removeIngredient(ing.id);
    }
    toast.show(`${toDelete.length}개 재료가 삭제되었습니다.`, 'success');
    setSelectedIds(new Set());
    setSelectMode(false);
  } catch (err) {
    setIngredients(prev);
    toast.show(apiErrorMessage(err), 'error');
  }
};

const exitSelectMode = () => {
  setSelectMode(false);
  setSelectedIds(new Set());
};
```

`담긴 재료` 헤더 영역:
```tsx
<div className="flex items-center justify-between mb-3">
  <h2 className="font-display text-lg font-bold">담긴 재료</h2>
  <div className="flex items-center gap-3">
    {ingredients.length > 0 && !selectMode && (
      <button type="button" onClick={() => setSelectMode(true)}
        className="text-sm font-semibold text-clay-600 dark:text-clay-400 hover:text-gochu-500">
        선택
      </button>
    )}
    {selectMode && (
      <>
        <button type="button" onClick={handleDeleteSelected}
          disabled={selectedIds.size === 0}
          className="text-sm font-semibold text-gochu-500 disabled:text-clay-300">
          삭제 ({selectedIds.size})
        </button>
        <button type="button" onClick={exitSelectMode}
          className="text-sm font-semibold text-clay-600 dark:text-clay-400">
          취소
        </button>
      </>
    )}
    {ingredients.length > 0 && !selectMode && (
      <button type="button" onClick={() => setClearOpen(true)}
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-clay-600 dark:text-clay-400 hover:text-gochu-500">
        <Trash2 className="h-4 w-4" /> 전체 삭제
      </button>
    )}
  </div>
</div>
```

---

## 작업 완료 체크리스트

### 기능 1 완료 기준
```
[ ] QUICK_INGREDIENTS 상수 추가
[ ] 빠른 추가 버튼 UI 렌더링
[ ] RF-05: raw_name + normalized_name 모두 비교해 중복 방지
[ ] 이미 추가된 재료 dimmed 처리
```

### 기능 2 완료 기준
```
[ ] RF-01: fridge_service.py에 search_ingredient_suggestions() 추가
[ ] RF-02: GET /api/fridge/search에 Depends(get_current_user) 추가
[ ] RF-04: 동의어("달걀") 입력 시 동의어 자체 반환 확인
[ ] api.ts URL /fridge/search로 수정
[ ] Swagger UI에서 /api/fridge/search 엔드포인트 확인
```

### 기능 3 완료 기준
```
[ ] BASIC_SEASONINGS 상수 추가
[ ] 토글 버튼 UI 표시
[ ] 활성 시 6개 조미료 일괄 추가
[ ] 비활성 시 조미료만 선택 제거 (개별 추가 재료 보존)
```

### 기능 4 완료 기준
```
[ ] 빈 상태 안내 문구 변경
[ ] 빠른 추가 버튼 6개 표시 및 동작
```

### 기능 5 완료 기준
```
[ ] FridgeChip에 categoryColor prop 추가
[ ] RF-07: categoryColor 지정 시 그림자 제거 확인
[ ] INGREDIENT_CATEGORY 매핑 추가
[ ] 채소·육류·해산물·유제품·조미료 색상 구분 표시
[ ] 매핑 없는 재료는 기존 default 스타일 유지
```

### 기능 6 완료 기준
```
[ ] FridgeChip 이름 클릭 시 편집 모드 진입
[ ] 인라인 input 표시 및 자동 포커스
[ ] RF-03: addIngredient 먼저 → 성공 후 removeIngredient 순서 확인
[ ] RF-06: 편집 완료 후 재료가 원래 위치에 유지되는지 확인
[ ] Enter 확인 / Escape 취소 / blur 시 제출
```

### 기능 7 완료 기준
```
[ ] 선택 모드 진입/종료 동작
[ ] 칩 클릭으로 개별 선택/해제
[ ] 선택된 칩 gochu-500 강조
[ ] 선택 삭제 후 토스트 표시
[ ] 선택 모드 중 전체 삭제 버튼 숨김
```
