'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Plus, Trash2, Search, Refrigerator, AlertTriangle, ArrowRight } from 'lucide-react';
import { Button } from '@/components/Button';
import { FridgeChip } from '@/components/FridgeChip';
import { Modal } from '@/components/Modal';
import { useToast } from '@/components/Toast';
import {
  addIngredient,
  apiErrorMessage,
  getFridge,
  removeIngredient,
  searchIngredients,
  type Ingredient,
} from '@/lib/api';
import { localSuggest } from '@/lib/synonyms';
import { INGREDIENT_CATEGORY } from '@/lib/ingredientCategory';

const MAX_INGREDIENTS = 50;

// NFR-USE-001 — 빠른 추가 버튼으로 재료 등록 시간 단축 (3분 이내 추천 흐름)
const QUICK_INGREDIENTS = [
  '계란', '대파', '마늘', '양파', '두부',
  '돼지고기', '김치', '당근', '감자', '참기름',
];

// NFR-USE-001 — 기본 양념 토글로 반복 입력 제거
const BASIC_SEASONINGS = ['소금', '간장', '참기름', '설탕', '후추', '식용유'];

export default function FridgePage() {
  const router = useRouter();
  const toast = useToast();

  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [highlight, setHighlight] = useState(-1);
  const [clearOpen, setClearOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [basicSeasoning, setBasicSeasoning] = useState(false); // 기능 3
  const [editingId, setEditingId] = useState<number | null>(null); // 기능 6
  const [editValue, setEditValue] = useState(''); // 기능 6
  const [selectMode, setSelectMode] = useState(false); // 기능 7
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set()); // 기능 7
  const debounceRef = useRef<number | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const data = await getFridge();
        if (alive) setIngredients(data.items);
      } catch (err) {
        if (alive) toast.show(apiErrorMessage(err), 'error');
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    const q = input.trim();
    if (!q) { setSuggestions([]); setHighlight(-1); return; }
    setSuggestions(localSuggest(q));
    debounceRef.current = window.setTimeout(async () => {
      const list = await searchIngredients(q);
      setSuggestions(list.slice(0, 8));
    }, 180);
    return () => { if (debounceRef.current) window.clearTimeout(debounceRef.current); };
  }, [input]);

  const canAdd = useMemo(() => {
    const t = input.trim();
    if (!t) return false;
    if (ingredients.some((i) => i.raw_name === t)) return false;
    return true;
  }, [input, ingredients]);

  const handleAdd = async (name?: string) => {
    const target = (name ?? input).trim();
    if (!target) return;
    if (ingredients.length >= MAX_INGREDIENTS) {
      toast.show(`재료는 최대 ${MAX_INGREDIENTS}개까지 추가할 수 있어요.`, 'warning');
      return;
    }
    // RF-05: raw_name + normalized_name 모두 비교 (예: "달걀" 있을 때 "계란" 입력 차단)
    if (ingredients.some((i) => i.raw_name === target || i.normalized_name === target)) {
      toast.show('이미 추가된 재료예요.', 'info');
      return;
    }
    setAdding(true);
    try {
      const added = await addIngredient(target);
      setIngredients((prev) => [...prev, added]);
      setInput('');
      setSuggestions([]);
      toast.show(`'${target}' 추가됨`, 'success');
    } catch (err) {
      toast.show(apiErrorMessage(err), 'error');
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (id: number) => {
    const prev = ingredients;
    setIngredients((p) => p.filter((i) => i.id !== id));
    try {
      await removeIngredient(id);
    } catch (err) {
      setIngredients(prev);
      toast.show(apiErrorMessage(err), 'error');
    }
  };

  const handleClearAll = async () => {
    setClearOpen(false);
    const prev = ingredients;
    setIngredients([]);
    try {
      for (const ing of prev) await removeIngredient(ing.id);
      toast.show('냉장고를 비웠어요.', 'success');
    } catch (err) {
      setIngredients(prev);
      toast.show(apiErrorMessage(err), 'error');
    }
  };

  // 기능 3: 기본 양념 일괄 추가/제거
  const handleToggleBasicSeasoning = async () => {
    if (!basicSeasoning) {
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
      const toRemove = ingredients.filter((i) => BASIC_SEASONINGS.includes(i.raw_name));
      setIngredients((prev) => prev.filter((i) => !BASIC_SEASONINGS.includes(i.raw_name)));
      for (const ing of toRemove) {
        await removeIngredient(ing.id);
      }
      setBasicSeasoning(false);
    }
  };

  // 기능 6: 인라인 편집
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

  // 기능 7: 선택 삭제
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

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setHighlight((h) => Math.min(suggestions.length - 1, h + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlight((h) => Math.max(-1, h - 1)); }
    else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlight >= 0 && suggestions[highlight]) handleAdd(suggestions[highlight]);
      else handleAdd();
    } else if (e.key === 'Escape') setSuggestions([]);
  };

  const goRecommend = () => {
    if (ingredients.length === 0) { toast.show('먼저 재료를 1개 이상 추가해주세요.', 'warning'); return; }
    router.push('/recommend');
  };

  return (
    <main className="min-h-screen bg-cream-100 dark:bg-clay-900">
      {/* BrandLockup 제거 — layout.tsx 사이드바에서 렌더됨 */}
      <header className="max-w-5xl mx-auto px-6 lg:px-8 py-6 flex items-center justify-end">
        <Link
          href="/recommend"
          className="hidden sm:inline-flex items-center gap-1.5 text-sm font-semibold text-clay-700 dark:text-cream-200 hover:text-gochu-500"
        >
          추천 결과 보기 <ArrowRight className="h-4 w-4" />
        </Link>
      </header>

      <section className="max-w-5xl mx-auto px-6 lg:px-8 pb-16">
        <div className="flex items-end justify-between mb-6">
          <div>
            <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight flex items-center gap-3">
              <Refrigerator className="h-9 w-9 text-gochu-500" aria-hidden="true" />
              내 냉장고
            </h1>
            <p className="mt-2 text-clay-700 dark:text-cream-200">
              남아있는 재료를 입력해주세요. 동의어도 자동으로 인식해요.
            </p>
          </div>
          <span
            className="hidden sm:inline-flex items-center px-3 py-1.5 rounded-full bg-cream-50 dark:bg-clay-800 border-2 border-clay-900 dark:border-cream-100 text-sm font-bold tabular-nums"
            aria-live="polite"
          >
            {ingredients.length}/{MAX_INGREDIENTS}
          </span>
        </div>

        <div className="relative">
          <div className="flex items-center gap-2 rounded-2xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 shadow-sticker px-4 h-14">
            <Search className="h-5 w-5 text-clay-500" aria-hidden="true" />
            <label htmlFor="ing-input" className="sr-only">재료 이름 입력</label>
            <input
              id="ing-input"
              type="text"
              autoComplete="off"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="예: 대파, 두부, 닭가슴살…"
              maxLength={20}
              className="flex-1 bg-transparent outline-none text-base placeholder:text-clay-400"
              aria-autocomplete="list"
              aria-controls="suggest-list"
              aria-expanded={suggestions.length > 0}
            />
            <Button size="sm" variant="primary" onClick={() => handleAdd()} disabled={!canAdd} loading={adding} type="button">
              <span className="flex items-center gap-1">
                <Plus className="h-4 w-4" /> 추가
              </span>
            </Button>
          </div>

          {suggestions.length > 0 && (
            <motion.ul
              id="suggest-list"
              role="listbox"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="absolute z-20 mt-2 w-full overflow-hidden rounded-2xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 shadow-sticker"
            >
              {suggestions.map((s, i) => (
                <li key={s} role="option" aria-selected={i === highlight}>
                  <button
                    type="button"
                    onMouseEnter={() => setHighlight(i)}
                    onClick={() => handleAdd(s)}
                    className={`flex w-full items-center justify-between px-4 py-3 text-left border-b last:border-b-0 border-clay-900/10 dark:border-cream-100/10 ${
                      i === highlight ? 'bg-gochu-500/10' : 'hover:bg-cream-200 dark:hover:bg-clay-700'
                    }`}
                  >
                    <span className="font-medium">{s}</span>
                    <Plus className="h-4 w-4 text-clay-500" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </motion.ul>
          )}

          {/* 기능 1: 자주 쓰는 재료 빠른 추가 버튼 + 기능 3: 기본 양념 토글 */}
          <div className="mt-3">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold text-clay-500 dark:text-clay-400">자주 쓰는 재료</p>
              {/* 기능 3: 기본 양념 토글 버튼 */}
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
            </div>
            {/* 기능 1: 빠른 추가 버튼 목록 */}
            <div className="flex flex-wrap gap-1.5">
              {QUICK_INGREDIENTS.map((name) => {
                // RF-05: raw_name + normalized_name 모두 비교해 동의어 중복 방지
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
        </div>

        <div className="mt-8">
          {/* 기능 7: 선택 모드 헤더 */}
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-display text-lg font-bold">담긴 재료</h2>
            {/* 기능 5: 카테고리 색상 범례 */}
            {ingredients.length > 0 && !loading && (
              <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 mb-3">
                {[
                  { label: '채소', color: 'bg-green-500' },
                  { label: '두부·콩', color: 'bg-purple-400' },
                  { label: '곡류', color: 'bg-amber-600' },
                  { label: '육류', color: 'bg-red-400' },
                  { label: '해산물', color: 'bg-blue-400' },
                  { label: '유제품', color: 'bg-yellow-400' },
                  { label: '조미료', color: 'bg-orange-400' },
                ].map(({ label, color }) => (
                  <span key={label} className="flex items-center gap-1.5 text-xs text-clay-500 dark:text-clay-400">
                    <span className={`w-2.5 h-2.5 rounded-full ${color}`} />
                    {label}
                  </span>
                ))}
              </div>
            )}
            <div className="flex items-center gap-3">
              {ingredients.length > 0 && !selectMode && (
                <button
                  type="button"
                  onClick={() => setSelectMode(true)}
                  className="text-sm font-semibold text-clay-600 dark:text-clay-400 hover:text-gochu-500"
                >
                  선택
                </button>
              )}
              {selectMode && (
                <>
                  <button
                    type="button"
                    onClick={handleDeleteSelected}
                    disabled={selectedIds.size === 0}
                    className="text-sm font-semibold text-gochu-500 disabled:text-clay-300"
                  >
                    삭제 ({selectedIds.size})
                  </button>
                  <button
                    type="button"
                    onClick={exitSelectMode}
                    className="text-sm font-semibold text-clay-600 dark:text-clay-400"
                  >
                    취소
                  </button>
                </>
              )}
              {ingredients.length > 0 && !selectMode && (
                <button
                  type="button"
                  onClick={() => setClearOpen(true)}
                  className="inline-flex items-center gap-1.5 text-sm font-semibold text-clay-600 dark:text-clay-400 hover:text-gochu-500"
                >
                  <Trash2 className="h-4 w-4" /> 전체 삭제
                </button>
              )}
            </div>
          </div>

          {loading ? (
            <div className="flex flex-wrap gap-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <span key={i} className="skeleton h-9 w-20 rounded-chip" />
              ))}
            </div>
          ) : ingredients.length === 0 ? (
            // 기능 4: 빈 상태 개선 — 빠른 추가 버튼 삽입
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
          ) : (
            // NFR-USE-002: flex-wrap으로 PC·태블릿 반응형 대응
            <ul className="flex flex-wrap gap-2">
              {ingredients.map((ing) =>
                // 기능 6: 편집 모드 — 인라인 input 표시
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
                    {/* 기능 5·6·7: categoryColor + onEdit + selectable/selected/onSelect */}
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
            </ul>
          )}

          {ingredients.length >= MAX_INGREDIENTS && (
            <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-mustard-500/15 border-2 border-mustard-500 px-4 py-2 text-sm font-semibold text-mustard-600 dark:text-mustard-400">
              <AlertTriangle className="h-4 w-4" aria-hidden="true" />
              최대 {MAX_INGREDIENTS}개까지 추가 가능합니다.
            </div>
          )}
        </div>

        <div className="sticky bottom-4 mt-6 flex justify-end">
          <Button size="md" variant="primary" onClick={goRecommend} disabled={ingredients.length === 0}>
            <span className="flex items-center gap-2 whitespace-nowrap">
              추천받기 <ArrowRight className="h-5 w-5" />
            </span>
          </Button>
        </div>
      </section>

      <Modal open={clearOpen} onClose={() => setClearOpen(false)} title="모든 재료를 삭제할까요?">
        <p className="text-clay-700 dark:text-cream-200">
          담겨있는 <strong>{ingredients.length}개</strong>의 재료가 모두 사라집니다. 되돌릴 수 없어요.
        </p>
        <div className="mt-6 flex gap-2 justify-end">
          <Button variant="secondary" onClick={() => setClearOpen(false)}>취소</Button>
          <Button variant="danger" onClick={handleClearAll}>
            <span className="flex items-center gap-1.5">
              <Trash2 className="h-4 w-4" /> 전체 삭제
            </span>
          </Button>
        </div>
      </Modal>
    </main>
  );
}
