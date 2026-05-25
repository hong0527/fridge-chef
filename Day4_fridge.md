# Day 4 회고록 (Day4_fridge.md)

작업 브랜치: `rok-fridge`
작업 기준 문서: `process(fridge).md` Day 4
작업 일자: 2026-05-24

---

## 1. 수행한 행동 요약

| 순서 | 작업 | 대상 파일 | 종류 |
|---|---|---|---|
| 4-1 | INGREDIENT_CATEGORY 파일 분리 | `frontend/lib/ingredientCategory.ts` | 신규 생성 |
| 4-2 | INGREDIENT_CATEGORY 확장 (market_ingredients 기반) | `frontend/lib/ingredientCategory.ts` | 수정 |
| 4-3 | 카테고리 세분화 — legume·grain 신규 추가 | `frontend/lib/ingredientCategory.ts`, `FridgeChip.tsx`, `page.tsx` | 수정 |
| 4-4 | 곡류·유제품 색상 구분 조정 | `frontend/components/FridgeChip.tsx`, `page.tsx` | 수정 |
| 4-5 | 프론트엔드 타입 체크 | `npx tsc --noEmit` | 검증 |

생성된 파일: `frontend/lib/ingredientCategory.ts`
삭제된 파일: 없음

---

## 2. 파일별 변경 상세

---

### `frontend/lib/ingredientCategory.ts` (신규)

#### 4-1. INGREDIENT_CATEGORY 파일 분리

기존에 `page.tsx` 상단에 인라인으로 선언되어 있던 `INGREDIENT_CATEGORY` 상수를 독립 파일로 분리했다.

**변경 전 — page.tsx 인라인 선언**
```tsx
// page.tsx
const INGREDIENT_CATEGORY: Record<string, 'vegetable' | 'meat' | 'seafood' | 'dairy' | 'seasoning'> = {
  대파: 'vegetable', 양파: 'vegetable', 마늘: 'vegetable', ...
  // 약 50개 항목이 page.tsx 안에 직접 포함
};
```

**변경 후 — 독립 파일 + import**
```tsx
// frontend/lib/ingredientCategory.ts
export type IngredientCategory = ...;
export const INGREDIENT_CATEGORY: Record<string, IngredientCategory> = { ... };

// page.tsx
import { INGREDIENT_CATEGORY } from '@/lib/ingredientCategory';
```

**이 변경이 필요한 이유**

카테고리 데이터는 UI 로직(이벤트 핸들러, 상태 관리)과 성격이 다른 순수 데이터다. 한 파일에 혼재시키면 page.tsx가 불필요하게 길어져 가독성이 떨어진다. 분리 후 카테고리 항목 추가·수정 시 page.tsx를 열지 않아도 된다.

---

#### 4-2. INGREDIENT_CATEGORY 확장

기존 약 50개 항목을 실제 레시피 데이터(`market_ingredients`)를 기반으로 대폭 확장했다.

| 카테고리 | 기존 | 확장 후 | 주요 추가 항목 |
|---|---|---|---|
| 채소·버섯·해조류 | 32개 | 63개 | 갓, 고사리, 곤드레, 냉이, 느타리/목이/팽이/표고버섯, 더덕, 도라지, 머위, 미나리, 봄동, 쑥, 청경채, 취나물, 매생이, 톳 등 |
| 육류 | 7개 | 8개 | 스팸 추가 |
| 해산물·어류 | 16개 | 60개+ | 게, 꼬막, 대구, 도미, 방어, 황태, 삼치, 장어, 쭈꾸미, 조기, 꽁치, 갑오징어, 한치, 가리비, 멍게, 성게 등 |
| 유제품·계란 | 7개 | 10개 | 두유, 휘핑크림, 요구르트 추가 |
| 조미료 | 18개 | 60개+ | 고춧가루, 국간장, 진간장, 멸치액젓, 새우젓, 케첩, 흑임자, 카레, 다시다, 혼다시, 두반장, 매실청, 올리고당, 와사비, 발사믹식초 등 |

**키 기준 원칙 유지**

키는 `normalized_name` 기준으로 유지했다. 예를 들어 닭가슴살·닭다리·닭날개는 SYNONYM_MAP에서 모두 `"닭고기"`로 정규화되므로 `닭고기: 'meat'` 하나로 처리된다.

---

#### 4-3. 카테고리 세분화 — legume·grain 신규 추가

기존 `vegetable` 하나로 묶여 있던 채소·버섯·해조류·두부·콩류를 세분화했다.

**IngredientCategory 타입 변경**

```ts
// 변경 전
export type IngredientCategory = 'vegetable' | 'meat' | 'seafood' | 'dairy' | 'seasoning';

// 변경 후
export type IngredientCategory =
  | 'vegetable'   // 채소·버섯·해조류
  | 'legume'      // 두부·콩류
  | 'grain'       // 곡류
  | 'meat'
  | 'seafood'
  | 'dairy'
  | 'seasoning';
```

**legume — 두부·콩류 (10개)**
```ts
두부: 'legume', 연두부: 'legume', 순두부: 'legume',
곤약: 'legume', 콩: 'legume', 검은콩: 'legume',
강낭콩: 'legume', 완두콩: 'legume', 팥: 'legume', 렌틸콩: 'legume',
```

**grain — 곡류 (12개)**
```ts
쌀: 'grain', 현미: 'grain', 찹쌀: 'grain', 보리: 'grain',
잡곡: 'grain', 귀리: 'grain', 율무: 'grain', 조: 'grain',
수수: 'grain', 기장: 'grain', 오트밀: 'grain', 밀: 'grain',
```

**세분화한 이유**

두부·콩류는 채소가 아닌 콩 단백질 식품 군에 가깝다. 곡류는 채소·콩류와 완전히 다른 식품군이다. 하나의 초록색으로 표시되면 사용자가 어떤 식품군인지 직관적으로 알기 어렵다.

---

### `frontend/components/FridgeChip.tsx`

#### 4-3 연속 — 신규 카테고리 색상 추가

```tsx
// 변경 전
categoryColor?: 'vegetable' | 'meat' | 'seafood' | 'dairy' | 'seasoning';

const categoryStyles = {
  vegetable: 'border-green-600  bg-green-50  ...text-green-800  ...',
  meat:      'border-red-500    bg-red-50    ...text-red-800    ...',
  seafood:   'border-blue-500   bg-blue-50   ...text-blue-800   ...',
  dairy:     'border-yellow-500 bg-yellow-50 ...text-yellow-800 ...',
  seasoning: 'border-orange-400 bg-orange-50 ...text-orange-700 ...',
};

// 변경 후
categoryColor?: 'vegetable' | 'legume' | 'grain' | 'meat' | 'seafood' | 'dairy' | 'seasoning';

const categoryStyles = {
  vegetable: 'border-green-600  bg-green-50  dark:bg-green-950/30  text-green-800  dark:text-green-300',
  legume:    'border-purple-500 bg-purple-50 dark:bg-purple-950/30 text-purple-800 dark:text-purple-300',
  grain:     'border-amber-700  bg-amber-100 dark:bg-amber-900/40  text-amber-900  dark:text-amber-200',
  meat:      'border-red-500    bg-red-50    dark:bg-red-950/30    text-red-800    dark:text-red-300',
  seafood:   'border-blue-500   bg-blue-50   dark:bg-blue-950/30   text-blue-800   dark:text-blue-300',
  dairy:     'border-yellow-500 bg-yellow-50 dark:bg-yellow-950/30 text-yellow-800 dark:text-yellow-300',
  seasoning: 'border-orange-400 bg-orange-50 dark:bg-orange-950/30 text-orange-700 dark:text-orange-300',
};
```

**색상 선택 근거**

| 카테고리 | 색상 | 선택 이유 |
|---|---|---|
| legume (두부·콩) | purple | 두부의 흰색·콩류의 보라 계열과 연상. 기존 7색과 충돌 없음 |
| grain (곡류) | amber (진한) | 곡물의 황갈색 연상. 단, yellow(유제품)와 유사하여 amber-700로 진하게 설정 |

---

#### 4-4. grain·dairy 색상 구분 조정

초기 grain 색상(`amber-500`)이 dairy(`yellow-500`)와 시각적으로 유사하다는 문제 확인.

**변경 내용**

```tsx
// 변경 전
grain: 'border-amber-500  bg-amber-50  dark:bg-amber-950/30  text-amber-800  dark:text-amber-300',

// 변경 후
grain: 'border-amber-700  bg-amber-100 dark:bg-amber-900/40  text-amber-900  dark:text-amber-200',
```

범례 도트도 동일하게 조정:
```tsx
// page.tsx 범례
{ label: '곡류', color: 'bg-amber-400' }  →  { label: '곡류', color: 'bg-amber-600' }
```

border(`500→700`), 배경(`50→100`), 텍스트(`800→900`) 모두 한 단계씩 어둡게 조정해 yellow와 명확히 구분되도록 했다.

---

### `frontend/app/(main)/fridge/page.tsx`

#### 4-1 연속 — INGREDIENT_CATEGORY import로 교체

```tsx
// 변경 전
import { localSuggest } from '@/lib/synonyms';
// + 파일 내부에 const INGREDIENT_CATEGORY = { ... } 50줄

// 변경 후
import { localSuggest } from '@/lib/synonyms';
import { INGREDIENT_CATEGORY } from '@/lib/ingredientCategory';
// 인라인 상수 완전 제거
```

#### 4-3 연속 — 범례에 legume·grain 항목 추가

```tsx
// 변경 전 (5항목)
{ label: '채소',   color: 'bg-green-500'  },
{ label: '육류',   color: 'bg-red-400'    },
{ label: '해산물', color: 'bg-blue-400'   },
{ label: '유제품', color: 'bg-yellow-400' },
{ label: '조미료', color: 'bg-orange-400' },

// 변경 후 (7항목)
{ label: '채소',    color: 'bg-green-500'  },
{ label: '두부·콩', color: 'bg-purple-400' },
{ label: '곡류',    color: 'bg-amber-600'  },
{ label: '육류',    color: 'bg-red-400'    },
{ label: '해산물',  color: 'bg-blue-400'   },
{ label: '유제품',  color: 'bg-yellow-400' },
{ label: '조미료',  color: 'bg-orange-400' },
```

---

## 3. 테스트 내역

---

### 테스트 1 — TypeScript 타입 체크

**무엇을 확인하기 위한 테스트인가**
`IngredientCategory` 타입에 `'legume' | 'grain'`이 추가됐으므로, `FridgeChip`의 `categoryColor` prop 타입과 `categoryStyles` 객체 키가 모두 일치하는지, `page.tsx`의 import 경로와 사용이 올바른지 확인한다.

```bash
cd frontend && npx tsc --noEmit
# 결과: 출력 없음 (0 errors)
```

---

## 4. 한계점 및 Day 4 개선사항

---

### L-01 — SYNONYM_MAP 미확장으로 인한 categorization 공백

**문제**
`INGREDIENT_CATEGORY` 키는 `normalized_name` 기준이다. 사용자가 SYNONYM_MAP에 없는 표현(예: "볶음밥용 쌀", "쌀밥")을 입력하면 `normalize()`가 그대로 반환하므로, 해당 키가 `INGREDIENT_CATEGORY`에 없어 카테고리 색상이 표시되지 않는다.

**발생 흐름**
```
사용자 입력: "햅쌀"
normalize("햅쌀") → "햅쌀"   ← SYNONYM_MAP에 없음
INGREDIENT_CATEGORY["햅쌀"]  → undefined
→ FridgeChip에 categoryColor 전달 안 됨 → 기본 흑백 칩 표시
```

**해결 방향**
SYNONYM_MAP에 `"햅쌀": "쌀"`, `"찰밥": "찹쌀"` 등 곡류 동의어를 추가하거나, `INGREDIENT_CATEGORY`에 동의어 표현도 직접 등록한다. 근본 해결은 SYNONYM_MAP 확장.

---

### L-02 — 해조류 분류 소속 모호성

**문제**
김·미역·다시마·파래·매생이·톳 등 해조류를 `vegetable(채소·버섯·해조류)`로 분류했다. 그러나 이들은 바다에서 나는 식재료로 `seafood`에 포함시키는 관점도 타당하다.

**현재 선택의 근거**
한국 요리에서 미역국·김무침 등 해조류 요리는 채소 요리에 더 가까운 맥락으로 사용되고, 사용자가 "해산물"로 인식하기 어렵다.

**영향 범위**
카테고리 색상 표시 목적이므로 레시피 추천 매칭에는 영향 없음.

---

### L-03 — grain 카테고리 QUICK_INGREDIENTS 미반영

**문제**
`QUICK_INGREDIENTS`와 빈 상태 버튼에 곡류 항목이 없다. grain 카테고리를 추가했지만 사용자가 "쌀"을 직접 타이핑해야만 grain 색상을 확인할 수 있다.

```tsx
const QUICK_INGREDIENTS = [
  '계란', '대파', '마늘', '양파', '두부',
  '돼지고기', '김치', '당근', '감자', '참기름',
  // 곡류 항목 없음
];
```

**해결 방향**
`QUICK_INGREDIENTS`에 "쌀" 추가 또는 곡류 전용 빠른 추가 버튼 구성.

---

## 5. 현재 리스크

| # | 리스크 | 심각도 | 설명 |
|---|---|---|---|
| R-01 | 편집 중 중복 검사 부재 (Day3 L-01) | 중 | 편집 시 기존 재료와 동일 이름으로 수정 가능 |
| R-02 | "김치" 모호성 (Day3 L-02) | 중 | QUICK_INGREDIENTS "김치"와 레시피 매칭 실패 가능 |
| R-03 | INGREDIENT_CATEGORY 김치 단순화 (Day3 L-03) | 낮음 | 김치 종류 구분 없이 단일 채소 색상 |
| R-04 | Day 2 L-01~L-04 미해소 | 중 | 역방향 중복, SYNONYM_MAP 비동기화, 수식어 패턴, 육류 부위명 |
| R-05 | SYNONYM_MAP 미확장으로 categorization 공백 (L-01) | 낮음 | 동의어 미등록 표현 입력 시 카테고리 색상 미표시 |

---

## 6. 후속 작업

| 우선순위 | 작업 | 의존 관계 |
|---|---|---|
| 높음 | R-01 해소: `handleEditSubmit` 중복 검사 추가 | 즉시 가능 |
| 높음 | SYNONYM_MAP 곡류·두부 동의어 확장 | INGREDIENT_CATEGORY 확장 완료 후 |
| 중간 | R-02 해소: SYNONYM_MAP 김치 종류 등록 | 소규모 |
| 중간 | L-03 해소: QUICK_INGREDIENTS에 쌀 추가 | 즉시 가능 |
| 낮음 | Day 2 L-01 해소: normalizeLocal() 추가 | 중기 |
| 낮음 | Day 2 L-03 해소: strip_modifiers() 구현 | 중기 |
| 낮음 | Day 2 L-04 해소: 육류 부위명 SYNONYM_MAP 추가 | 소규모 |

---

## 7. Day 4 완료 체크리스트

```
[✅] INGREDIENT_CATEGORY → frontend/lib/ingredientCategory.ts 분리
[✅] INGREDIENT_CATEGORY 확장 — 약 50개 → 약 250개 (7카테고리)
[✅] IngredientCategory 타입 — 5종 → 7종 (legume·grain 추가)
[✅] FridgeChip.tsx — legume(purple), grain(amber 진한) 색상 추가
[✅] page.tsx — import 전환 + 범례 7항목으로 업데이트
[✅] grain·dairy 색상 구분 조정 (amber-700/100)
[✅] npx tsc --noEmit — 0 errors
```
