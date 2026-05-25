# 냉장고 기능 UX 개선 구현 계획서

## 작업 개요

냉장고 재료 관리 화면(`/fridge`)의 UX를 개선한다.
우선순위 1–7번 항목을 순서대로 구현하며, 백엔드 1건·프론트엔드 3건 파일을 수정한다.

---

## 전체 작업 파일 목록

| 우선순위 | 기능 | 파일 | 작업 종류 | 완료 |
|---|---|---|---|---|
| 1 | 자주 쓰는 재료 빠른 추가 버튼 | `frontend/app/(main)/fridge/page.tsx` | 수정 | [ ] |
| 2 | 서버 자동완성 엔드포인트 | `backend/app/api/fridge.py` | 수정 | [ ] |
| 2 | 서버 자동완성 URL 수정 | `frontend/lib/api.ts` | 수정 | [ ] |
| 3 | 기본 양념 일괄 추가 토글 | `frontend/app/(main)/fridge/page.tsx` | 수정 | [ ] |
| 4 | 빈 상태 안내 개선 | `frontend/app/(main)/fridge/page.tsx` | 수정 | [ ] |
| 5 | 카테고리별 색상 구분 | `frontend/components/FridgeChip.tsx` | 수정 | [ ] |
| 5 | 카테고리 매핑·색상 적용 | `frontend/app/(main)/fridge/page.tsx` | 수정 | [ ] |
| 6 | 재료 수정(인라인 편집) | `frontend/components/FridgeChip.tsx` | 수정 | [ ] |
| 6 | 편집 상태 관리 | `frontend/app/(main)/fridge/page.tsx` | 수정 | [ ] |
| 7 | 선택 삭제 기능 | `frontend/components/FridgeChip.tsx` | 수정 | [ ] |
| 7 | 선택 모드 상태 관리 | `frontend/app/(main)/fridge/page.tsx` | 수정 | [ ] |

> `fridge/page.tsx`는 기능 1·3·4·5·6·7이 모두 집중되므로 각 기능별 추가 위치를 섹션에서 명확히 표시한다.

---

## 상세 작업 내용

---

### 기능 1 — 자주 쓰는 재료 빠른 추가 버튼

**파일 경로**
- [frontend/app/(main)/fridge/page.tsx](frontend/app/(main)/fridge/page.tsx)

**접근 방식 상세설명**

현재 모든 재료는 타이핑으로만 추가 가능하다. `QUICK_INGREDIENTS` 상수 배열을 정의하고, 검색 인풋 아래에 빠른 추가 버튼 목록을 렌더링한다. 각 버튼은 클릭 시 기존 `handleAdd(name)` 함수를 재사용해 추가하므로 로직 중복이 없다. 이미 냉장고에 있는 재료는 버튼이 `dimmed`(불투명도 낮춤 + 클릭 불가) 처리되어 중복 추가를 방지한다.

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
      const added = ingredients.some((i) => i.raw_name === name);
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

### 기능 2 — 서버 자동완성 엔드포인트

**파일 경로**
- [backend/app/api/fridge.py](backend/app/api/fridge.py)
- [frontend/lib/api.ts](frontend/lib/api.ts)

**접근 방식 상세설명**

현재 `searchIngredients()`는 `/api/ingredients/search`를 호출하지만 백엔드에 해당 라우터가 없어 404를 반환한다. 백엔드의 기존 fridge 라우터(`/api/fridge`)에 `GET /search` 엔드포인트를 추가하고, 프론트엔드 호출 경로를 `/fridge/search`로 수정한다.

검색 로직은 백엔드 `SYNONYM_MAP`의 키(정규형)와 값(동의어) 모두를 검색해 일치하는 정규형을 반환한다. 예를 들어 "삼" 입력 시 `"삼겹살" → 돼지고기` 매핑에서 "돼지고기"가 반환된다.

**코드 스니펫**

`backend/app/api/fridge.py` — 파일 상단 import 추가 후 라우터 함수 추가:
```python
from app.core.synonym_map import SYNONYM_MAP  # import 블록에 추가


@router.get("/search")
async def search_ingredients(q: str = "") -> dict:
    """재료 이름 자동완성 — SYNONYM_MAP 기반 (SRS FR-002)."""
    needle = q.strip().lower()
    if not needle:
        return {"suggestions": []}

    seen: set[str] = set()
    results: list[str] = []

    for synonym, canonical in SYNONYM_MAP.items():
        # 동의어에 검색어 포함 → 정규형 반환
        if needle in synonym.lower() and canonical not in seen:
            seen.add(canonical)
            results.append(canonical)
        # 정규형에 검색어 포함 → 정규형 반환
        if needle in canonical.lower() and canonical not in seen:
            seen.add(canonical)
            results.append(canonical)
        if len(results) >= 8:
            break

    return {"suggestions": results}
```

`frontend/lib/api.ts` — `searchIngredients` 함수 내 URL 수정:
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

// useState 블록에 추가
const [basicSeasoning, setBasicSeasoning] = useState(false);
```

핸들러 추가:
```tsx
const handleToggleBasicSeasoning = async () => {
  if (!basicSeasoning) {
    // 활성화 — 없는 재료만 추가
    for (const name of BASIC_SEASONINGS) {
      if (!ingredients.some((i) => i.raw_name === name)) {
        try {
          const added = await addIngredient(name);
          setIngredients((prev) => [...prev, added]);
        } catch {
          // 개별 실패는 무시하고 계속 진행
        }
      }
    }
    setBasicSeasoning(true);
  } else {
    // 비활성화 — BASIC_SEASONINGS에 속한 재료만 제거
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

검색 인풋 위 또는 빠른 추가 버튼 영역 옆에 추가:
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

**접근 방식 상세설명**

`FridgeChip`에 이미 `variant` prop과 `className` prop이 존재한다. 기존 variant 시스템을 건드리지 않고 `categoryColor` prop을 추가해 카테고리별 테두리·배경색을 지정한다. `fridge/page.tsx`에 재료명 → 카테고리 매핑 딕셔너리를 정의하고, 칩 렌더링 시 해당 값을 `categoryColor`로 전달한다. 매핑에 없는 재료는 기존 `default` 스타일을 그대로 유지한다.

**코드 스니펫**

`frontend/components/FridgeChip.tsx` — props 및 스타일 확장:
```tsx
// FridgeChipProps에 추가
interface FridgeChipProps {
  name: string;
  onRemove?: () => void;
  variant?: 'default' | 'used' | 'missing' | 'compact';
  categoryColor?: 'vegetable' | 'meat' | 'seafood' | 'dairy' | 'seasoning';
  className?: string;
}

// categoryColor 스타일 맵 추가 (컴포넌트 내부)
const categoryStyles = {
  vegetable: 'border-green-600 bg-green-50 dark:bg-green-950/30 text-green-800 dark:text-green-300',
  meat:      'border-red-500  bg-red-50   dark:bg-red-950/30  text-red-800  dark:text-red-300',
  seafood:   'border-blue-500 bg-blue-50  dark:bg-blue-950/30 text-blue-800 dark:text-blue-300',
  dairy:     'border-yellow-500 bg-yellow-50 dark:bg-yellow-950/30 text-yellow-800 dark:text-yellow-300',
  seasoning: 'border-orange-400 bg-orange-50 dark:bg-orange-950/30 text-orange-700 dark:text-orange-300',
} as const;

// 컴포넌트 함수 파라미터에 추가
export function FridgeChip({ name, onRemove, variant = 'default', categoryColor, className }: FridgeChipProps) {

// className cn() 호출에서 categoryColor 적용
className={cn(
  'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-chip border-2 font-medium text-sm whitespace-nowrap',
  'transition-transform duration-150 hover:-translate-y-0.5',
  variant !== 'compact' && 'shadow-[0_2px_0_0_rgba(26,23,21,0.85)]',
  categoryColor ? categoryStyles[categoryColor] : styles[variant],
  className,
)}
```

`frontend/app/(main)/fridge/page.tsx` — 카테고리 매핑 추가:
```tsx
const INGREDIENT_CATEGORY: Record<string, 'vegetable' | 'meat' | 'seafood' | 'dairy' | 'seasoning'> = {
  // 채소·두부
  대파: 'vegetable', 양파: 'vegetable', 마늘: 'vegetable', 당근: 'vegetable',
  감자: 'vegetable', 두부: 'vegetable', 김치: 'vegetable', 애호박: 'vegetable',
  // 육류
  돼지고기: 'meat', 소고기: 'meat', 닭고기: 'meat',
  // 해산물
  새우: 'seafood', 오징어: 'seafood', 고등어: 'seafood', 조개류: 'seafood',
  // 유제품·계란
  계란: 'dairy', 우유: 'dairy', 치즈: 'dairy', 버터: 'dairy',
  // 조미료
  소금: 'seasoning', 간장: 'seasoning', 참기름: 'seasoning',
  설탕: 'seasoning', 후추: 'seasoning', 식용유: 'seasoning',
};

// 칩 렌더링 시 categoryColor 전달
<FridgeChip
  name={ing.raw_name}
  onRemove={() => handleRemove(ing.id)}
  categoryColor={INGREDIENT_CATEGORY[ing.normalized_name]}
/>
```

---

### 기능 6 — 재료 인라인 편집

**파일 경로**
- [frontend/components/FridgeChip.tsx](frontend/components/FridgeChip.tsx)
- [frontend/app/(main)/fridge/page.tsx](frontend/app/(main)/fridge/page.tsx)

**접근 방식 상세설명**

현재 오타 수정 시 삭제 후 재입력이 필요하다. `FridgeChip`에 `onEdit` prop을 추가해 칩 이름 영역 클릭 시 편집 콜백을 호출한다. `fridge/page.tsx`에서 `editingId` state로 현재 편집 중인 재료 ID를 추적하고, 해당 칩 위치에 인라인 `<input>`을 렌더링한다. 수정 완료(Enter 또는 blur) 시 기존 재료를 삭제하고 새 이름으로 재추가하는 방식으로 백엔드 PATCH 엔드포인트 없이 구현한다.

**코드 스니펫**

`frontend/components/FridgeChip.tsx` — `onEdit` prop 추가:
```tsx
interface FridgeChipProps {
  name: string;
  onRemove?: () => void;
  onEdit?: () => void;           // 추가
  variant?: 'default' | 'used' | 'missing' | 'compact';
  categoryColor?: 'vegetable' | 'meat' | 'seafood' | 'dairy' | 'seasoning';
  className?: string;
}

// name span을 클릭 가능하게 변경
<span
  className={cn('leading-none', onEdit && 'cursor-pointer hover:underline underline-offset-2')}
  onClick={onEdit}
  title={onEdit ? '클릭해서 편집' : undefined}
>
  {name}
</span>
```

`frontend/app/(main)/fridge/page.tsx` — 편집 상태 및 핸들러 추가:
```tsx
// state 추가
const [editingId, setEditingId] = useState<number | null>(null);
const [editValue, setEditValue] = useState('');

// 편집 시작
const handleEditStart = (id: number, currentName: string) => {
  setEditingId(id);
  setEditValue(currentName);
};

// 편집 완료
const handleEditSubmit = async (id: number) => {
  const newName = editValue.trim();
  const original = ingredients.find((i) => i.id === id);
  if (!newName || !original || newName === original.raw_name) {
    setEditingId(null);
    return;
  }
  try {
    await removeIngredient(id);
    const added = await addIngredient(newName);
    setIngredients((prev) => [...prev.filter((i) => i.id !== id), added]);
    toast.show(`'${original.raw_name}' → '${newName}' 수정됨`, 'success');
  } catch (err) {
    toast.show(apiErrorMessage(err), 'error');
  } finally {
    setEditingId(null);
  }
};

// 칩 목록 렌더링 부분 교체
{ingredients.map((ing) =>
  editingId === ing.id ? (
    // 편집 모드: 인라인 인풋
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
    // 일반 모드
    <li key={ing.id}>
      <FridgeChip
        name={ing.raw_name}
        onRemove={() => handleRemove(ing.id)}
        onEdit={() => handleEditStart(ing.id, ing.raw_name)}
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

// 컴포넌트 내부 — selected 시 강조 테두리
className={cn(
  'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-chip border-2 font-medium text-sm whitespace-nowrap',
  'transition-transform duration-150 hover:-translate-y-0.5',
  variant !== 'compact' && 'shadow-[0_2px_0_0_rgba(26,23,21,0.85)]',
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
  <button type="button" onClick={onRemove} aria-label={`${name} 재료 삭제`}
    className="inline-flex h-5 w-5 items-center justify-center rounded-full hover:bg-clay-900/10 dark:hover:bg-cream-100/15">
    <X className="h-3.5 w-3.5" />
  </button>
)}
```

`frontend/app/(main)/fridge/page.tsx` — 선택 모드 상태 및 핸들러:
```tsx
// state 추가
const [selectMode, setSelectMode] = useState(false);
const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

// 선택 토글
const toggleSelectId = (id: number) => {
  setSelectedIds((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });
};

// 선택 삭제
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

// 선택 모드 종료
const exitSelectMode = () => {
  setSelectMode(false);
  setSelectedIds(new Set());
};
```

헤더 영역 버튼 추가 (`담긴 재료` h2 옆):
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

{/* 칩 렌더링 시 selectable·selected·onSelect 전달 */}
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

## 작업 완료 체크리스트

### 기능 1 완료 기준
```
[ ] QUICK_INGREDIENTS 상수 추가
[ ] 빠른 추가 버튼 UI 렌더링
[ ] 이미 추가된 재료 dimmed 처리
[ ] handleAdd 재사용으로 로직 중복 없음
```

### 기능 2 완료 기준
```
[ ] GET /api/fridge/search?q= 엔드포인트 동작 확인 (Swagger)
[ ] api.ts URL /fridge/search로 수정
[ ] 자동완성 입력 시 서버 결과 반영 확인
[ ] 기존 자동완성 동작 회귀 없음
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
[ ] 빠른 추가 버튼 6개 표시
[ ] 버튼 클릭 시 재료 추가 동작
```

### 기능 5 완료 기준
```
[ ] FridgeChip에 categoryColor prop 추가
[ ] INGREDIENT_CATEGORY 매핑 추가
[ ] 채소·육류·해산물·유제품·조미료 색상 구분 표시
[ ] 매핑 없는 재료는 기존 default 스타일 유지
```

### 기능 6 완료 기준
```
[ ] FridgeChip 이름 클릭 시 편집 모드 진입
[ ] 인라인 input 표시 및 자동 포커스
[ ] Enter 확인 / Escape 취소
[ ] 변경 없이 blur 시 취소
[ ] 수정 성공 토스트 표시
```

### 기능 7 완료 기준
```
[ ] 선택 모드 진입/종료 동작
[ ] 칩 클릭으로 개별 선택/해제
[ ] 선택된 칩 gochu-500 강조
[ ] 선택 삭제 후 토스트 표시
[ ] 전체 삭제와 선택 삭제 동시 표시 안 됨
```
