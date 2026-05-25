# Day 3 회고록 (Day3_fridge.md)

작업 브랜치: `rok-fridge`
작업 기준 문서: `process(fridge).md` Day 3
작업 일자: 2026-05-23

---

## 1. 수행한 행동 요약

| 순서 | 작업 | 대상 파일 | 종류 |
|---|---|---|---|
| 3-1 | 기능 6 — 인라인 편집 | `frontend/app/(main)/fridge/page.tsx` | 수정 |
| 3-2 | 기능 7 — 선택 삭제 | `frontend/app/(main)/fridge/page.tsx` | 수정 |
| 3-3 | 백엔드 전체 테스트 | `pytest -q` | 검증 |
| 3-4 | 프론트엔드 타입 체크 | `npx tsc --noEmit` | 검증 |

생성된 파일: 없음
삭제된 파일: 없음

---

## 2. 파일별 변경 상세

### `frontend/app/(main)/fridge/page.tsx`

Day 3의 모든 변경이 이 파일에 집중됐다.

---

#### 3-1. 기능 6 — 재료 인라인 편집

**추가된 상태**
```tsx
const [editingId, setEditingId] = useState<number | null>(null);
const [editValue, setEditValue] = useState('');
```

**추가된 핸들러**
```tsx
const handleEditStart = (id: number, currentName: string) => {
  setEditingId(id);
  setEditValue(currentName);
};

const handleEditSubmit = async (id: number) => {
  const newName = editValue.trim();
  const original = ingredients.find((i) => i.id === id);
  if (!newName || !original || newName === original.raw_name) {
    setEditingId(null);
    return;
  }
  // RF-06: 원래 위치 기억
  const originalIndex = ingredients.findIndex((i) => i.id === id);
  try {
    // RF-03: 추가 먼저 → 성공 후 삭제 (실패 시 기존 재료 보존)
    const added = await addIngredient(newName);
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
```

**변경된 칩 렌더링 — 편집 모드 분기**
```tsx
{ingredients.map((ing) =>
  editingId === ing.id ? (
    // 편집 모드: 인라인 input 표시
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
        className="px-3 py-1.5 rounded-chip border-2 border-gochu-500 ..."
      />
    </li>
  ) : (
    // 일반 모드
    <li key={ing.id}>
      <FridgeChip
        name={ing.raw_name}
        onEdit={selectMode ? undefined : () => handleEditStart(ing.id, ing.raw_name)}
        ...
      />
    </li>
  )
)}
```

**이 코드가 동작시키는 기능**

칩 이름 영역을 클릭하면 해당 위치에 인라인 `<input>`이 나타나 재료명을 바로 수정할 수 있다. 기존에는 오타 수정 시 재료를 삭제하고 다시 입력해야 했다.

- `handleEditStart`: 편집 대상 id와 현재 이름을 상태에 저장해 input을 열음
- `handleEditSubmit`: Enter 또는 blur 시 호출. 이름이 동일하면 API 호출 없이 취소. 다르면 RF-03·RF-06 적용
- ESC 키: `setEditingId(null)` → 변경 사항 저장 없이 원래 칩으로 복귀

**RF-03 적용 — 추가 먼저, 삭제 나중**

```
기존 방식 (workList 원본):
  1. removeIngredient(id)  ← 삭제 먼저
  2. addIngredient(newName) ← 실패하면 재료 영구 소실 ❌

RF-03 수정:
  1. addIngredient(newName)  ← 추가 먼저
  2. removeIngredient(id)    ← 추가 성공 후 삭제
  → 추가 실패해도 기존 재료 보존 ✅
```

Docker 로그로 순서 확인:
```
POST   /api/fridge        201 Created    ← addIngredient 먼저
OPTIONS /api/fridge/66    200 OK         ← CORS 사전 확인 (자동, 무시)
DELETE /api/fridge/66     204 No Content ← removeIngredient 나중
```

**RF-06 적용 — 원래 위치 유지**

```
기존 방식 (workList 원본):
  setIngredients((prev) => [...prev.filter(...), added])
  → 편집한 재료가 목록 맨 뒤로 이동 ❌

RF-06 수정:
  const originalIndex = ingredients.findIndex((i) => i.id === id);
  next.splice(originalIndex, 0, added);
  → 편집 완료 후 원래 위치 유지 ✅
```

---

#### 3-2. 기능 7 — 선택 삭제

**추가된 상태**
```tsx
const [selectMode, setSelectMode] = useState(false);
const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
```

**추가된 핸들러**
```tsx
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
    for (const ing of toDelete) await removeIngredient(ing.id);
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

**변경된 헤더 — 선택/삭제/취소 버튼**
```tsx
<div className="flex items-center gap-3">
  {ingredients.length > 0 && !selectMode && (
    <button onClick={() => setSelectMode(true)}>선택</button>
  )}
  {selectMode && (
    <>
      <button onClick={handleDeleteSelected} disabled={selectedIds.size === 0}>
        삭제 ({selectedIds.size})
      </button>
      <button onClick={exitSelectMode}>취소</button>
    </>
  )}
  {ingredients.length > 0 && !selectMode && (
    <button onClick={() => setClearOpen(true)}>
      <Trash2 /> 전체 삭제
    </button>
  )}
</div>
```

**이 코드가 동작시키는 기능**

여러 재료를 한 번에 삭제할 수 있다. 기존에는 재료를 하나씩 X 버튼으로 삭제하거나 전체 삭제만 가능했다.

- "선택" 버튼 → `selectMode: true` → 각 칩에 체크박스 표시, `onEdit` 비활성
- 칩 클릭 → `toggleSelectId()` → gochu-500 강조 테두리 + 체크박스 체크
- "삭제 (N)" → 낙관적 업데이트로 즉시 목록에서 제거 후 API 순차 호출
- 삭제 실패 시 → `setIngredients(prev)` 롤백으로 목록 원상복귀
- "취소" → `selectMode: false`, `selectedIds` 초기화
- 선택 모드 중 "전체 삭제" 버튼 숨김 (동시 표시 방지)

---

## 3. 테스트 내역

---

### 테스트 1 — TypeScript 타입 체크

**무엇을 확인하기 위한 테스트인가**
`editingId(number | null)`, `selectedIds(Set<number>)` 등 신규 상태 타입과, `handleEditSubmit`의 async 반환 타입, `FridgeChip`에 새로 전달되는 `onEdit·selectable·selected·onSelect` props 타입이 모두 일치하는지 확인한다.

```bash
cd frontend && npx tsc --noEmit
# 결과: 출력 없음 (0 errors)
```

---

### 테스트 2 — 백엔드 전체 테스트

**무엇을 확인하기 위한 테스트인가**
Day 3 변경은 프론트엔드 전용이므로 백엔드 변경이 없다. Day 1·2에서 추가한 코드와 기존 전체 API가 여전히 정상인지 확인한다.

```bash
pytest -q
# 결과: 159 passed, 4 xfailed, 1 xpassed, 0 failed
```

---

### 테스트 3 — 수동 브라우저 확인 (10항목)

**무엇을 확인하기 위한 테스트인가**
기능 6·7이 실제 브라우저에서 의도한 대로 동작하는지 확인한다.

| 항목 | 결과 | 확인 내용 |
|---|---|---|
| 칩 이름 클릭 → 인라인 input + 자동 포커스 | ✅ | 편집 모드 진입 |
| 수정 후 Enter → 토스트 + 원래 위치 유지 | ✅ | RF-03·RF-06 동작 |
| Escape → 편집 취소 (저장 없이 칩 복귀) | ✅ | ESC 키 취소 |
| RF-03: POST 먼저 → DELETE 나중 (Docker 로그) | ✅ | Docker 로그로 확인 |
| "선택" 버튼 → 선택 모드 + 체크박스 표시 | ✅ | 선택 모드 진입 |
| 칩 클릭 → gochu-500 강조 테두리 | ✅ | 선택 시각 피드백 |
| "삭제 (N)" → N개 삭제 + 토스트 | ✅ | 선택 삭제 동작 |
| "취소" → 선택 모드 종료 + 선택 초기화 | ✅ | 취소 동작 |
| 선택 모드 중 "전체 삭제" 버튼 숨김 | ✅ | UI 충돌 방지 |
| 선택 모드 중 칩 이름 클릭 → 편집 미진입 | ✅ | onEdit 비활성 확인 |

**RF-03 확인 방법**
Network 탭 대신 Docker 컨테이너 로그로 확인:
```
fridgechef-backend | POST   /api/fridge        201 Created    ← 추가 먼저
fridgechef-backend | OPTIONS /api/fridge/66    200 OK         ← CORS (무시)
fridgechef-backend | DELETE /api/fridge/66     204 No Content ← 삭제 나중
```
> 204 No Content = DELETE 성공 응답. 삭제 후 반환할 데이터가 없어 body 없이 성공을 반환함.

---

## 4. 한계점 및 Day 3 개선사항

---

### L-01 — 편집 시 중복 검사 부재

**문제**
`handleEditSubmit`에 기존 재료와의 중복 검사가 없다. 동의어뿐만 아니라 **이미 냉장고에 있는 어떤 재료로든** 편집이 가능하다.

**발생 흐름 — 일반 중복**
```
냉장고: 돼지고기, 두부
"두부" 칩 → "돼지고기"로 편집 → Enter

handleEditSubmit:
  중복 검사 없음
  → addIngredient("돼지고기") → 성공 (백엔드 중복 체크 없음)
  → removeIngredient(두부 id)
결과: 돼지고기 2개 공존 ❌
```

**발생 흐름 — 동의어 중복**
```
냉장고: 달걀 (normalized: 계란), 계란 (normalized: 계란)
"계란" 칩 → "달걀"로 편집 → Enter

handleEditSubmit:
  중복 검사 없음
  → addIngredient("달걀") → 성공
  → removeIngredient(계란 id)
결과: 달걀 2개 공존 ❌
```

즉, 동의어 여부와 관계없이 냉장고에 이미 있는 재료명으로 수정하면 모두 중복이 발생한다.

**해결 방향**

| 방법 | 설명 | 장단점 |
|---|---|---|
| **A. 편집 제출 전 중복 검사(쉬움)** | `handleEditSubmit`에서 `newName`이 기존 재료와 겹치는지 확인 후 차단 | 즉각 피드백, 프론트에서 처리 but, 역방향 동의어 잡지 못함 ex: 계란, 달걀 공존|
| **B. 백엔드 normalized_name 중복 차단(어려움)** | `add_for_user`에서 DB 조회 후 중복 시 409 반환 | 모든 문제 해결(완전한 보장), Day 2 L-01 해결책과 동일 |

방법 A 코드:
```tsx
const isDuplicate = ingredients.some(
  (i) => i.id !== id && (i.raw_name === newName || i.normalized_name === newName)
);
if (isDuplicate) {
  toast.show('이미 추가된 재료예요.', 'info');
  setEditingId(null);
  return;
}
```

방법 B는 Day 2 L-01(역방향 중복)과 함께 백엔드 `add_for_user`의 `normalized_name` 중복 체크로 근본 해결. 두 문제를 동시에 처리할 수 있어 병행 권장.

---

### L-02 — QUICK_INGREDIENTS "김치" 모호성

**문제**
빠른 추가 버튼과 빈 상태 버튼에 "김치"가 등록되어 있다.

```tsx
const QUICK_INGREDIENTS = ['계란', '대파', ..., '김치', ...];
// 빈 상태 버튼
['계란', '대파', '마늘', '양파', '두부', '김치']
```

"김치"는 배추김치·깍두기·열무김치·오이소박이·부추김치 등 다양한 종류를 포함하는 모호한 표현이다.

**구체적 문제**

| 상황 | 결과 |
|---|---|
| 사용자가 "김치" 버튼 클릭 → `normalized_name: "김치"` 저장 | 레시피가 "배추김치"로 저장 시 매칭 실패 ❌ |
| 사용자가 "배추김치" 직접 입력 → `normalized_name: "배추김치"` | 레시피의 "김치"와 매칭 실패 ❌ |
| 사용자가 "깍두기" 입력 → `normalized_name: "깍두기"` | 레시피의 "김치"와 매칭 실패 ❌ |

**김치 종류별 대체 가능성**

| 종류 | 기반 재료 | 일반 김치 레시피 대체 |
|---|---|---|
| 배추김치 | 배추 | ✅ 기본 |
| 열무김치 | 열무 | ⚠️ 가능하나 맛 차이 |
| 부추김치 | 부추 | ⚠️ 향 강해 어색 |
| 깍두기 | 무 | ⚠️ 찌개는 가능, 볶음밥은 어색 |
| 오이소박이 | 오이 | ❌ 성격 완전히 다름 |

**해결 방향**
```python
# SYNONYM_MAP에 추가 (대체 가능한 것만)
"배추김치":  "김치",
"열무김치":  "김치",
"부추김치":  "김치",
# 깍두기·오이소박이는 개별 유지
```
`QUICK_INGREDIENTS`의 "김치"는 "배추김치"로 구체화하거나 현행 유지 후 SYNONYM_MAP 등록으로 해결.

---

### L-03 — INGREDIENT_CATEGORY 김치 분류 단순화

**문제**
현재 `김치: 'vegetable'`로 단일 분류되어 있다. 깍두기(무)·오이소박이(오이) 등은 기반 재료가 달라 채소 중에서도 세부 분류가 다르다. 그러나 현재 카테고리 시스템이 채소 내 세분화를 지원하지 않아 모든 김치가 동일한 초록색으로 표시된다.

**영향 범위**
카테고리 색상은 시각적 구분 목적이므로 추천 매칭에는 영향 없음. UX 정확도 문제.

**해결 방향**
카테고리를 세분화하거나 (`vegetable-fermented` 등) 현행 유지.

---

## 5. 현재 리스크

| # | 리스크 | 심각도 | 설명 |
|---|---|---|---|
| R-01 | 편집 중 동의어 중복 허용 (L-01) | 중 | 동의어 관계인 재료로 편집 시 중복 공존 |
| R-02 | "김치" 모호성 (L-02) | 중 | QUICK_INGREDIENTS "김치"와 실제 레시피 재료 매칭 실패 가능 |
| R-03 | INGREDIENT_CATEGORY 단순화 (L-03) | 낮음 | 김치 종류 구분 없이 단일 채소 색상 |
| R-04 | Day 2 L-01~L-04 미해소 | 중 | 역방향 중복, SYNONYM_MAP 비동기화, 수식어 패턴, 육류 부위명 |

---

## 6. 후속 작업

| 일차 | 작업 | 의존 관계 |
|---|---|---|
| Day 4 | 브라우저 E2E 기능 1~7 전체 검증 | Day 3 완료 후 |
| Day 4 | 기존 기능 회귀 검증 | Day 3 완료 후 |
| Day 4 | NFR 항목 검증 | Day 3 완료 후 |
| Day 4 | ruff check . | 백엔드 전체 완료 후 |
| 별도 | L-01 해소: 편집 중복 검사 + 백엔드 안전망 | 즉시 가능 |
| 별도 | L-02 해소: SYNONYM_MAP 김치 종류 등록 | 소규모 |
| 별도 | Day 2 L-01 해소: normalizeLocal() 추가 | 중기 |
| 별도 | Day 2 L-03 해소: strip_modifiers() 구현 | 중기 |
| 별도 | Day 2 L-04 해소: 육류 부위명 SYNONYM_MAP 추가 | 소규모 |

---

## 7. Day 3 완료 체크리스트

```
[✅] 기능 6 — 칩 이름 클릭 편집 + RF-03 순서 + RF-06 위치 유지
[✅] 기능 7 — 선택 모드 + 선택 삭제 + 취소 + 실패 시 롤백
[✅] pytest -q — 159 passed, 0 failed
[✅] npx tsc --noEmit — 0 errors
[✅] 수동 브라우저 10항목 전체 통과
[✅] RF-03 Docker 로그로 POST → DELETE 순서 확인
```
