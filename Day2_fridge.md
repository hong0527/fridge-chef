# Day 2 회고록 (Day2_fridge.md)

작업 브랜치: `rok-fridge`
작업 기준 문서: `process(fridge).md` Day 2
작업 일자: 2026-05-23

---

## 1. 수행한 행동 요약

| 순서 | 작업 | 대상 파일 | 종류 |
|---|---|---|---|
| 2-1 | 기능 1 — 빠른 추가 버튼 | `frontend/app/(main)/fridge/page.tsx` | 수정 |
| 2-2 | 기능 3 — 기본 양념 토글 | `frontend/app/(main)/fridge/page.tsx` | 수정 |
| 2-3 | 기능 4 — 빈 상태 개선 | `frontend/app/(main)/fridge/page.tsx` | 수정 |
| 2-4 | 기능 5 — 카테고리 색상 | `frontend/app/(main)/fridge/page.tsx` | 수정 |
| 버그수정 | handleAdd RF-05 중복 검사 보완 | `frontend/app/(main)/fridge/page.tsx` | 수정 |

생성된 파일: 없음
삭제된 파일: 없음

---

## 2. 파일별 변경 상세

### `frontend/app/(main)/fridge/page.tsx`

Day 2의 모든 변경이 이 파일에 집중됐다.

---

#### 2-1. 기능 1 — 자주 쓰는 재료 빠른 추가 버튼

**추가된 상수**
```tsx
const QUICK_INGREDIENTS = [
  '계란', '대파', '마늘', '양파', '두부',
  '돼지고기', '김치', '당근', '감자', '참기름',
];
```

**추가된 UI** (검색 인풋 하단)
```tsx
{QUICK_INGREDIENTS.map((name) => {
  // RF-05: raw_name + normalized_name 모두 비교
  const added = ingredients.some(
    (i) => i.raw_name === name || i.normalized_name === name
  );
  return (
    <button
      disabled={added || adding}
      onClick={() => !added && handleAdd(name)}
      ...
    >
      {added ? '✓ ' : '+ '}{name}
    </button>
  );
})}
```

**이 코드가 동작시키는 기능**
재료를 타이핑 없이 클릭 한 번으로 추가한다. 이미 냉장고에 있는 재료는 `✓` dimmed 처리되어 클릭 불가. RF-05에 따라 `normalized_name`도 함께 비교하므로 "달걀"을 직접 입력한 경우 "계란" 버튼이 자동으로 dimmed된다.

---

#### 2-2. 기능 3 — 기본 양념 일괄 추가 토글

**추가된 상수 및 상태**
```tsx
const BASIC_SEASONINGS = ['소금', '간장', '참기름', '설탕', '후추', '식용유'];
const [basicSeasoning, setBasicSeasoning] = useState(false);
```

**추가된 핸들러**
```tsx
const handleToggleBasicSeasoning = async () => {
  if (!basicSeasoning) {
    // 활성화: 냉장고에 없는 것만 추가
    for (const name of BASIC_SEASONINGS) {
      if (!ingredients.some((i) => i.raw_name === name)) {
        const added = await addIngredient(name);
        setIngredients((prev) => [...prev, added]);
      }
    }
    setBasicSeasoning(true);
  } else {
    // 비활성화: BASIC_SEASONINGS에 속한 것만 제거 (사용자 재료 보존)
    const toRemove = ingredients.filter((i) => BASIC_SEASONINGS.includes(i.raw_name));
    setIngredients((prev) => prev.filter((i) => !BASIC_SEASONINGS.includes(i.raw_name)));
    for (const ing of toRemove) await removeIngredient(ing.id);
    setBasicSeasoning(false);
  }
};
```

**이 코드가 동작시키는 기능**
소금·간장·참기름처럼 항상 있는 조미료를 버튼 하나로 일괄 추가/제거한다. 비활성화 시 `BASIC_SEASONINGS` 목록에 속한 재료만 선택 제거하므로, 사용자가 별도로 추가한 재료는 영향을 받지 않는다.

---

#### 2-3. 기능 4 — 빈 상태 개선

**변경 전**
```tsx
<div className="... p-24 text-center">
  <p>아직 비어있어요</p>
  <p>위 입력창에 재료 이름을 넣어보세요.</p>
</div>
```

**변경 후**
```tsx
<div className="... p-8 text-center">
  <p>아직 비어있어요</p>
  <p>자주 쓰는 재료로 빠르게 시작해보세요.</p>
  <div className="mt-4 flex flex-wrap gap-2 justify-center">
    {['계란','대파','마늘','양파','두부','김치'].map((name) => (
      <button onClick={() => handleAdd(name)}>+ {name}</button>
    ))}
  </div>
</div>
```

**이 코드가 동작시키는 기능**
냉장고가 비어있을 때 텍스트 안내만 보여주던 것을, 자주 쓰는 재료 6개의 빠른 추가 버튼으로 교체한다. 처음 접속한 사용자가 타이핑 없이 클릭만으로 재료를 추가할 수 있어 진입 장벽을 낮춘다. 버튼 클릭 시 `handleAdd(name)`이 호출되어 재료가 추가되면 빈 상태 블록이 사라지고 재료 목록으로 전환된다.

---

#### 2-4. 기능 5 — 카테고리별 색상 구분

**추가된 매핑 상수**
```tsx
const INGREDIENT_CATEGORY: Record<string, 'vegetable'|'meat'|'seafood'|'dairy'|'seasoning'> = {
  대파: 'vegetable', 양파: 'vegetable', 마늘: 'vegetable', 당근: 'vegetable',
  감자: 'vegetable', 두부: 'vegetable', 김치: 'vegetable', 애호박: 'vegetable',
  돼지고기: 'meat',  소고기: 'meat',   닭고기: 'meat',
  새우: 'seafood',   오징어: 'seafood', 고등어: 'seafood', 조개류: 'seafood',
  계란: 'dairy',    우유: 'dairy',    치즈: 'dairy',    버터: 'dairy',
  소금: 'seasoning', 간장: 'seasoning', 참기름: 'seasoning',
  설탕: 'seasoning', 후추: 'seasoning', 식용유: 'seasoning',
};
```

**변경된 칩 렌더링**
```tsx
// 변경 전
<FridgeChip name={ing.raw_name} onRemove={() => handleRemove(ing.id)} />

// 변경 후
<FridgeChip
  name={ing.raw_name}
  onRemove={() => handleRemove(ing.id)}
  categoryColor={INGREDIENT_CATEGORY[ing.normalized_name]}
/>
```

**이 코드가 동작시키는 기능**
`normalized_name`을 키로 카테고리를 조회해 `categoryColor` prop으로 전달한다. Day 1에서 준비한 `FridgeChip.tsx`의 `categoryStyles`가 이 값을 받아 채소는 초록, 육류는 빨강, 해산물은 파랑, 유제품은 노랑, 조미료는 주황으로 칩을 렌더링한다. 매핑에 없는 재료는 `categoryColor`가 `undefined`로 전달되어 기존 default 스타일을 유지한다. `normalized_name` 기준으로 조회하므로 "달걀"을 입력해도 `normalized_name: "계란"` → `dairy`로 올바르게 분류된다.

---

#### 2-5. 버그 수정 — handleAdd RF-05 중복 검사 보완

**발견 경위**
수동 테스트 중 "달걀" 추가 후 입력창에 "계란"을 직접 타이핑하면 추가됐다. 빠른 추가 버튼의 중복 검사(RF-05)는 `normalized_name` 비교를 포함했지만, `handleAdd` 내부 검사는 `raw_name`만 비교하고 있어 입력창 경로로는 중복이 통과됐다.

**변경 전**
```tsx
if (ingredients.some((i) => i.raw_name === target)) {
  toast.show('이미 추가된 재료예요.', 'info');
  return;
}
```

**변경 후**
```tsx
// RF-05: raw_name + normalized_name 모두 비교 (예: "달걀" 있을 때 "계란" 입력 차단)
if (ingredients.some((i) => i.raw_name === target || i.normalized_name === target)) {
  toast.show('이미 추가된 재료예요.', 'info');
  return;
}
```

**이 코드가 동작시키는 기능**
`normalized_name === target` 조건 추가로, "달걀"(`normalized_name: "계란"`)이 이미 있을 때 입력창에 "계란"을 타이핑해도 차단된다. 이 수정으로 입력창을 통한 동의어 중복 추가가 방지된다.

---

## 3. 테스트 내역

---

### 테스트 1 — TypeScript 타입 체크

**무엇을 확인하기 위한 테스트인가**
`INGREDIENT_CATEGORY` 타입, `basicSeasoning` state, `handleToggleBasicSeasoning` 반환 타입 등 Day 2에서 추가된 모든 코드가 타입 오류 없이 컴파일되는지 확인한다.

```bash
cd frontend && npx tsc --noEmit
# 결과: 출력 없음 (0 errors)
```

---

### 테스트 2 — 백엔드 회귀 테스트

**무엇을 확인하기 위한 테스트인가**
Day 2 작업은 프론트엔드 전용이므로 백엔드 변경이 없다. Day 1에서 추가한 `/search` 엔드포인트와 기존 CRUD가 여전히 정상인지 확인한다.

```bash
pytest tests/api/test_fridge_api.py -q
# 결과: 12 passed, 2 xfailed, 0 failed
```

---

### 테스트 3 — 수동 브라우저 확인 (9항목)

**무엇을 확인하기 위한 테스트인가**
각 기능이 실제 브라우저에서 의도한 대로 동작하는지 확인한다.

| 항목 | 결과 | 확인 내용 |
|---|---|---|
| 빠른 추가 버튼 10개 표시 | ✅ | 검색 인풋 하단 렌더링 |
| 버튼 클릭 → 추가 + dimmed | ✅ | 클릭 시 칩 생성 + ✓ 표시 |
| 기본 양념 한번에 추가 | ✅ | 6개 조미료 일괄 추가 |
| 양념 버튼 재클릭 → 조미료만 제거 | ✅ | 사용자 추가 재료 보존 확인 |
| 빈 상태 버튼 6개 표시 | ✅ | 냉장고 비울 때 UI 전환 |
| 카테고리 색상 구분 | ✅ | 채소 초록, 육류 빨강 등 |
| 매핑 없는 재료 기존 스타일 | ✅ | default 칩 스타일 유지 |
| RF-05: 달걀 추가 후 계란 버튼 dimmed | ✅ | normalized_name 비교 확인 |
| RF-05(버그): 달걀 후 계란 입력창 차단 | **❌ → 수정 후 ✅** | handleAdd 버그 발견·수정 |

---

## 4. 한계점 및 Day 2 개선사항

---

### L-01 — 역방향 중복 차단 미완성

**문제**
"계란"이 냉장고에 있을 때 입력창에 "달걀"을 타이핑하면 여전히 추가된다.

**원인**
`handleAdd("달걀")` 실행 시:
```
i.raw_name === "달걀"       → false (raw_name은 "계란")
i.normalized_name === "달걀" → false (normalized_name도 "계란")
→ 중복 감지 실패
```
"달걀"이 "계란"으로 정규화된다는 사실을 프론트엔드에서 모르기 때문이다.

**해결 방향**
`frontend/lib/synonyms.ts`에 `normalizeLocal()` 함수 추가:
```typescript
export function normalizeLocal(input: string): string {
  const lower = input.trim().toLowerCase();
  for (const [canonical, synonyms] of Object.entries(SYNONYM_MAP)) {
    if (canonical.toLowerCase() === lower) return canonical;
    if (synonyms.some(s => s.toLowerCase() === lower)) return canonical;
  }
  return input.trim();
}
```
`handleAdd`에서 `normalizeLocal(target)`을 사전 변환 후 `normalized_name`과 비교.

**커버리지 한계**
프론트엔드 `synonyms.ts`는 40쌍. 백엔드 118쌍 중 포함되지 않은 78쌍은 여전히 역방향 차단 불가. 완전한 해결을 위해서는 백엔드 `add_for_user`의 `normalized_name` 중복 체크(방법 B)도 병행 필요.

---

### L-02 — 프론트엔드·백엔드 SYNONYM_MAP 비동기화

**문제**
| | 프론트엔드 `synonyms.ts` | 백엔드 `synonym_map.py` |
|---|---|---|
| 구조 | `정규형 → [동의어]` | `동의어 → 정규형` |
| 쌍 수 | 40쌍 | 118쌍 |

두 파일이 별도로 관리되어 한쪽에 동의어를 추가해도 반대쪽에 반영되지 않는다. `localSuggest()`와 `normalizeLocal()`은 40쌍 기준으로만 동작한다.

**해결 방향**
백엔드 `SYNONYM_MAP`을 단일 소스로 삼고, 프론트엔드는 빌드 시 자동 생성하거나 API로 받아오는 구조로 통합. 단기적으로는 신규 동의어 추가 시 양쪽 모두 수동 업데이트.

---

### L-03 — 레시피 재료명의 준비 방법·상태·형태 수식어 미처리

**문제**
레시피 재료명은 기본 재료에 조리 준비 방법, 상태, 형태를 수식어로 붙여 표기하는 경우가 많다.

```
레시피 재료명 = 기본 재료 + 수식어
"다진 마늘"   = 마늘     + 다진 (조리 준비 방법)
"냉동 새우"   = 새우     + 냉동 (상태)
"후춧가루"    = 후추     + 가루 (형태)
"데친 시금치" = 시금치   + 데친 (조리 준비 방법)
```

현재 `normalize()`는 SYNONYM_MAP에 등록된 항목만 변환한다. 수식어가 붙은 재료명은 SYNONYM_MAP에 개별 등록되지 않으면 그대로 반환되어 사용자 냉장고의 기본 재료와 매칭이 실패한다.

**수식어 패턴 분류**

| 패턴 | 예시 | 기본 재료 | 냉장고 재료로 대체 가능 |
|------|-----|-----------|-----------------------|
| 다진X | 다진마늘, 다진양파, 다진쇠고기 | 마늘, 양파, 소고기 | ✅ |
| 채 썬X | 채 썬당근, 채 썬양배추 | 당근, 양배추 | ✅ |
| 데친X | 데친시금치, 데친숙주 | 시금치, 숙주 | ✅ |
| 삶은X | 삶은계란, 삶은감자 | 계란, 감자 | ✅ |
| 냉동X | 냉동새우, 냉동오징어 | 새우, 오징어 | ✅ |
| X가루 | 후춧가루, 마늘가루, 생강가루 | 후추, 마늘, 생강 | ✅ |
| X즙 | 생강즙, 양파즙 | 생강, 양파 | ✅ |
| 말린X | 말린표고버섯, 말린새우 | 버섯, 새우 | ⚠️ 식감 차이 있음 |
| X페이스트 | 토마토페이스트 | 토마토 | ❌ 별도 가공품 |

**원인**
현재 SYNONYM_MAP은 **개별 케이스를 수동 등록**하는 방식이다. 수식어 패턴은 재료 수 × 수식어 수만큼 경우의 수가 발생하므로 개별 등록으로는 완전한 커버리지가 불가능하다.

두 파일 모두 기존 팀원이 작성한 것으로, 이 구조적 한계는 우리가 만든 문제가 아니라 기존 설계에서 내려온 한계다.

**영향**
사용자가 냉장고에 "양파"를 등록했어도 레시피 재료가 "다진양파"이면 매칭 실패 → 실제로 만들 수 있는 요리가 추천 목록에서 누락된다.

**정규화 설계 방향 — 느슨한 매칭 채택**
수식어가 붙은 재료와 기본 재료의 관계:
- 사용자가 기본 재료(양파)를 가지고 있으면, 수식어(다진) 상태로 준비할 수 있다
- 추천 누락(양파 있는데 레시피 미추천)이 오추천(대체 가능한 레시피 추천)보다 UX상 더 나쁘다
- 따라서 수식어를 제거하고 기본 재료로 정규화하는 **느슨한 매칭** 방식을 채택한다
- 단, `X페이스트`처럼 원재료와 전혀 다른 가공품은 정규화 대상에서 제외한다

**해결 방향**
SYNONYM_MAP에 개별 항목을 추가하는 방식 대신, **패턴 기반 전처리 함수**를 도입해 `normalize()` 호출 전에 수식어를 체계적으로 제거한다.

```python
# 예시 설계 방향 (실제 구현은 별도 작업)
def strip_modifiers(ingredient: str) -> str:
    """준비 방법·상태·형태 수식어 제거 후 기본 재료명 반환."""
    # 1. 조리 준비 방법 접두사 제거: 다진, 채 썬, 데친, 삶은, 볶은, 간 ...
    # 2. 상태 접두사 제거: 냉동, 말린, 건 ...
    # 3. 형태 접미사 제거: 가루, 즙 ...
    # 4. 예외 처리: 페이스트 등 대체 불가 가공품은 유지
    ...
```

이 함수가 도입되면 SYNONYM_MAP 등록 항목 수를 줄이면서도 더 넓은 커버리지를 확보할 수 있어 L-02의 관리 부담도 완화된다.

---

### L-04 — 육류 독립 부위명 SYNONYM_MAP 미등록

**문제**
닭고기는 부위명이 독립 단어로 SYNONYM_MAP에 등록되어 있어 정규화가 된다. 반면 돼지고기·소고기·오리고기는 일부 부위명이 미등록 상태다.

| 육류 | 등록된 부위 | 미등록 부위 |
|---|---|---|
| 닭고기 | 닭가슴살, 닭다리, 닭날개, 닭안심, 닭정육 | 닭볶음용, 닭봉 |
| 돼지고기 | 삼겹살, 대패삼겹살, 돼지목살, 돼지등심, 돼지안심, 돼지갈비, 다진돼지고기 | **목살**(단독), 항정살, 가브리살, 앞다리살, 족발 |
| 소고기 | 소불고기, 소등심, 소안심, 차돌박이, 다진소고기, 우삼겹 | **쇠고기**(표기 다름), 국거리, 불고기감, 양지, 사태, 한우 |
| 오리고기 | **없음** | 오리고기 전체 |

**L-03과의 차이**
- L-03: "다진양파"처럼 수식어+재료 **조합 패턴** → `strip_modifiers()`로 체계적 처리
- L-04: "목살"처럼 **독립적인 부위명 단어** 자체가 SYNONYM_MAP에 없는 커버리지 누락 → 개별 항목 추가로 해결 가능

**모호성 주의**
- "목살" 단독 → 관용적으로 돼지목살이지만 소목살도 존재 (맥락 의존)
- "등심" 단독 → 돼지등심·소등심 모두 해당 (모호)
- 이처럼 모호한 단어는 추가 시 신중히 판단 필요

**영향**
사용자가 냉장고에 "목살", "항정살", "양지" 등을 등록해도 SYNONYM_MAP에 없으면 `normalized_name`이 그대로 저장되어 레시피의 "돼지고기"와 매칭이 안 됨.

**해결 방향**
모호성이 없는 항목부터 우선 추가:
```python
# 돼지고기 — 독립 부위명
"항정살":   "돼지고기",
"가브리살": "돼지고기",
"앞다리살": "돼지고기",

# 소고기 — 독립 부위명 및 표기 다름
"쇠고기":   "소고기",
"국거리":   "소고기",
"불고기감": "소고기",
"양지":     "소고기",
"사태":     "소고기",
"한우":     "소고기",

# 오리
"오리":     "오리고기",
"오리고기": "오리고기",
```

모호한 단어("목살", "등심" 단독)는 레시피 데이터에서 실제로 어떻게 사용되는지 확인 후 판단.

---

## 5. 현재 리스크

| # | 리스크 | 심각도 | 설명 |
|---|---|---|---|
| R-01 | 역방향 중복 미차단 (L-01) | 중 | "계란" 있을 때 "달걀" 입력 시 중복 추가됨 |
| R-02 | SYNONYM_MAP 비동기화 (L-02) | 낮음 | 프론트 40쌍 vs 백엔드 118쌍 불일치 |
| R-03 | 레시피 재료 수식어 미처리 (L-03) | 중 | 다진X·채 썬X·X가루 등 수식어 패턴을 SYNONYM_MAP이 개별 등록 방식으로 처리하므로 커버리지 불완전. 실제 레시피 데이터의 재료와 사용자 냉장고 재료 매칭 실패 가능 |
| R-04 | FridgeChip onEdit·selectable 미연결 | 낮음 | Day 1에서 추가한 props가 page.tsx에서 아직 미사용 |
| R-05 | 육류 독립 부위명 미등록 (L-04) | 중 | 목살·항정살·양지·쇠고기 등 독립 부위명이 SYNONYM_MAP에 없어 사용자 냉장고 재료와 레시피 매칭 실패. 오리고기는 전체 미등록 |

---

## 6. 후속 작업

| 일차 | 작업 | 의존 관계 |
|---|---|---|
| Day 3-1 | `fridge/page.tsx` 기능 6 — 인라인 편집 | Day 1 FridgeChip `onEdit` prop 완료 |
| Day 3-2 | `fridge/page.tsx` 기능 7 — 선택 삭제 | Day 1 FridgeChip `selectable·selected·onSelect` 완료 |
| Day 3-3 | pytest -q 전체 검증 | Day 3 작업 완료 후 |
| Day 3-4 | npx tsc --noEmit 전체 검증 | Day 3 작업 완료 후 |
| 별도 | L-01 해소: `normalizeLocal()` + 백엔드 안전망 | Day 3 이후 |
| 별도 | L-03 해소: `strip_modifiers()` 패턴 기반 전처리 함수 설계·구현 | 중기 작업, L-02 해소 후 병행 권장 |
| 별도 | L-04 해소: 모호성 없는 부위명 SYNONYM_MAP 추가 (항정살·쇠고기·양지 등) | 즉시 가능 (소규모) |
| 별도 | L-02 해소: SYNONYM_MAP 단일 소스 통합 | 중기 리팩토링 |

---

## 7. Day 2 완료 체크리스트

```
[✅] 기능 1 — QUICK_INGREDIENTS 10개 버튼 + RF-05 dimmed 처리
[✅] 기능 3 — BASIC_SEASONINGS 토글 + 비활성화 시 사용자 재료 보존
[✅] 기능 4 — 빈 상태 버튼 6개 + 클릭 추가 동작
[✅] 기능 5 — INGREDIENT_CATEGORY 매핑 + categoryColor 전달
[✅] 버그 수정 — handleAdd RF-05 normalized_name 비교 추가
[✅] npx tsc --noEmit — 0 errors
[✅] pytest test_fridge_api.py — 12 passed, 0 failed
[✅] 수동 브라우저 9항목 — 전체 통과 (버그 발견 후 수정 포함)
```
