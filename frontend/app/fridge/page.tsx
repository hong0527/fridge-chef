'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Plus, Trash2, Search, Refrigerator, AlertTriangle, ArrowRight, User, Settings, LogOut } from 'lucide-react';
import { BrandLockup } from '@/components/Brand';
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
  logout,
  type Ingredient,
} from '@/lib/api';
import { localSuggest } from '@/lib/synonyms';

const MAX_INGREDIENTS = 50;

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
  const debounceRef = useRef<number | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const data = await getFridge();
        if (alive) setIngredients(data.items);
      } catch (err) {
        if (alive) {
          toast.show(apiErrorMessage(err), 'error');
        }
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Autocomplete (debounced) — instant local suggestion for typing latency,
  // then server-authoritative SYNONYM_MAP result replaces it.
  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    const q = input.trim();
    if (!q) {
      setSuggestions([]);
      setHighlight(-1);
      return;
    }
    setSuggestions(localSuggest(q));
    debounceRef.current = window.setTimeout(async () => {
      const list = await searchIngredients(q);
      setSuggestions(list.slice(0, 8));
    }, 180);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
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
    if (ingredients.some((i) => i.raw_name === target)) {
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

  // 백엔드에 일괄 삭제 엔드포인트가 없어 개별 DELETE 를 순차 실행.
  const handleClearAll = async () => {
    setClearOpen(false);
    const prev = ingredients;
    setIngredients([]);
    try {
      for (const ing of prev) {
        await removeIngredient(ing.id);
      }
      toast.show('냉장고를 비웠어요.', 'success');
    } catch (err) {
      setIngredients(prev);
      toast.show(apiErrorMessage(err), 'error');
    }
  };

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight((h) => Math.min(suggestions.length - 1, h + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => Math.max(-1, h - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlight >= 0 && suggestions[highlight]) {
        handleAdd(suggestions[highlight]);
      } else {
        handleAdd();
      }
    } else if (e.key === 'Escape') {
      setSuggestions([]);
    }
  };

  const goRecommend = () => {
    if (ingredients.length === 0) {
      toast.show('먼저 재료를 1개 이상 추가해주세요.', 'warning');
      return;
    }
    router.push('/recommend');
  };

  const handleLogout = async () => {
    await logout();
    toast.show('로그아웃 되었습니다.', 'success');
    router.push('/');
  };

  return (
    <main className="min-h-screen bg-cream-100 dark:bg-clay-900">
      <header className="max-w-7xl mx-auto px-6 lg:px-12 py-6 flex items-center justify-between">
        <BrandLockup size="md" />
        <Link
          href="/recommend"
          className="hidden sm:inline-flex items-center gap-1.5 text-sm font-semibold text-clay-700 dark:text-cream-200 hover:text-gochu-500"
        >
          추천 결과 보기 <ArrowRight className="h-4 w-4" />
        </Link>
      </header>

      <div className="max-w-7xl mx-auto px-6 lg:px-12 flex flex-col md:flex-row gap-10 lg:gap-16 mt-8">
        {/* Sidebar - Explicitly visible */}
        <div className="w-full md:w-80 space-y-6">
          <div className="p-6 bg-cream-50 dark:bg-clay-800 rounded-[32px] border border-clay-900/10 dark:border-cream-100/10 shadow-soft">
            <h3 className="font-display text-xl font-bold mb-6 px-1">설정</h3>
            <div className="space-y-3">
              <Button variant="secondary" size="lg" className="w-full justify-start gap-4 px-6 h-14 text-lg">
                <User className="h-6 w-6 text-gochu-500" /> 프로필 설정
              </Button>
              <Button variant="secondary" size="lg" className="w-full justify-start gap-4 px-6 h-14 text-lg">
                <Settings className="h-6 w-6 text-herb-500" /> 알레르기 설정
              </Button>
              <Button
                variant="ghost"
                size="lg"
                onClick={handleLogout}
                className="w-full justify-start gap-4 px-6 h-14 text-lg text-clay-500 hover:text-gochu-500 hover:bg-gochu-500/5 transition-all"
              >
                <LogOut className="h-6 w-6" /> 로그아웃
              </Button>
            </div>
            
            <div className="mt-8 pt-6 border-t border-clay-900/5 dark:border-cream-100/5">
              <p className="px-1 text-xs font-bold tracking-widest uppercase text-clay-400 dark:text-clay-500 mb-4">
                통계
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-4 rounded-2xl bg-cream-100 dark:bg-clay-900/50">
                  <span className="block text-2xl font-bold tabular-nums text-gochu-500">{ingredients.length}</span>
                  <span className="text-[10px] font-bold text-clay-500">재료 수</span>
                </div>
                <div className="p-4 rounded-2xl bg-cream-100 dark:bg-clay-900/50">
                  <span className="block text-2xl font-bold tabular-nums text-herb-500">12</span>
                  <span className="text-[10px] font-bold text-clay-500">받은 추천</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <section className="flex-1 max-w-3xl pb-16">
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

        {/* Input */}
        <div className="relative">
          <div className="flex items-center gap-2 rounded-2xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 shadow-sticker px-4 h-14">
            <Search className="h-5 w-5 text-clay-500" aria-hidden="true" />
            <label htmlFor="ing-input" className="sr-only">
              재료 이름 입력
            </label>
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
            <Button
              size="sm"
              variant="primary"
              onClick={() => handleAdd()}
              disabled={!canAdd}
              loading={adding}
              type="button"
            >
              <Plus className="h-4 w-4" /> 추가
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
                      i === highlight
                        ? 'bg-gochu-500/10'
                        : 'hover:bg-cream-200 dark:hover:bg-clay-700'
                    }`}
                  >
                    <span className="font-medium">{s}</span>
                    <Plus className="h-4 w-4 text-clay-500" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </motion.ul>
          )}
        </div>

        {/* Tags */}
        <div className="mt-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-display text-lg font-bold">담긴 재료</h2>
            {ingredients.length > 0 && (
              <button
                type="button"
                onClick={() => setClearOpen(true)}
                className="inline-flex items-center gap-1.5 text-sm font-semibold text-clay-600 dark:text-clay-400 hover:text-gochu-500"
              >
                <Trash2 className="h-4 w-4" /> 전체 삭제
              </button>
            )}
          </div>

          {loading ? (
            <div className="flex flex-wrap gap-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <span key={i} className="skeleton h-9 w-20 rounded-chip" />
              ))}
            </div>
          ) : ingredients.length === 0 ? (
            <div className="rounded-3xl border-2 border-dashed border-clay-400 dark:border-cream-100/30 bg-cream-50/40 dark:bg-clay-800/40 p-10 text-center">
              <Refrigerator className="h-10 w-10 mx-auto text-clay-400" aria-hidden="true" />
              <p className="mt-3 font-semibold">아직 비어있어요</p>
              <p className="text-sm text-clay-600 dark:text-clay-400 mt-1">
                위 입력창에 재료 이름을 넣어보세요.
              </p>
            </div>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {ingredients.map((ing) => (
                <li key={ing.id}>
                  <FridgeChip
                    name={ing.raw_name}
                    onRemove={() => handleRemove(ing.id)}
                  />
                </li>
              ))}
            </ul>
          )}

          {ingredients.length >= MAX_INGREDIENTS && (
            <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-mustard-500/15 border-2 border-mustard-500 px-4 py-2 text-sm font-semibold text-mustard-600 dark:text-mustard-400">
              <AlertTriangle className="h-4 w-4" aria-hidden="true" />
              최대 {MAX_INGREDIENTS}개까지 추가 가능합니다.
            </div>
          )}
        </div>

        {/* Sticky CTA */}
        <div className="sticky bottom-4 mt-12 flex justify-end">
          <Button
            size="lg"
            variant="primary"
            onClick={goRecommend}
            disabled={ingredients.length === 0}
          >
            추천받기 <ArrowRight className="h-5 w-5" />
          </Button>
        </div>
      </section>
      </div>

      <Modal
        open={clearOpen}
        onClose={() => setClearOpen(false)}
        title="모든 재료를 삭제할까요?"
      >
        <p className="text-clay-700 dark:text-cream-200">
          담겨있는 <strong>{ingredients.length}개</strong>의 재료가 모두 사라집니다. 되돌릴 수 없어요.
        </p>
        <div className="mt-6 flex gap-2 justify-end">
          <Button variant="secondary" onClick={() => setClearOpen(false)}>
            취소
          </Button>
          <Button variant="danger" onClick={handleClearAll}>
            <Trash2 className="h-4 w-4" /> 전체 삭제
          </Button>
        </div>
      </Modal>
    </main>
  );
}
