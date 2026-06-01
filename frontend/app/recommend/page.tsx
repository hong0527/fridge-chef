'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Refrigerator, ChefHat, Sparkles } from 'lucide-react';
import { BrandLockup } from '@/components/Brand';
import { Button } from '@/components/Button';
import { PreferenceWizard } from '@/components/PreferenceWizard';
import { RecipeCard, RecipeCardSkeleton } from '@/components/RecipeCard';
import { useToast } from '@/components/Toast';
import {
  apiErrorMessage,
  getFridge,
  recommend,
  type Preferences,
  type RecommendResponse,
} from '@/lib/api';

type Phase = 'wizard' | 'loading' | 'result' | 'error';

export default function RecommendPage() {
  const toast = useToast();
  const [phase, setPhase] = useState<Phase>('wizard');
  const [result, setResult] = useState<RecommendResponse | null>(null);
  const [progress, setProgress] = useState(0);
  // Browser setInterval 반환은 number — @types/node 의 NodeJS.Timeout 와 혼동 방지
  const progressIntervalRef = useRef<number | null>(null);

  // 컴포넌트 언마운트 시 in-flight interval cleanup (memory leak 방지)
  useEffect(() => {
    return () => {
      if (progressIntervalRef.current !== null) {
        window.clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
    };
  }, []);

  const handleSubmit = async (prefs: Preferences) => {
    setPhase('loading');
    setProgress(0);
    const start = Date.now();
    progressIntervalRef.current = window.setInterval(() => {
      const elapsed = (Date.now() - start) / 1000;
      setProgress(Math.min(95, Math.round((elapsed / 10) * 100)));
    }, 200);
    try {
      const fridge = await getFridge();
      const ingredients = fridge.items.map((i) => i.raw_name);
      const data = await recommend(ingredients, prefs);
      setResult(data);
      setPhase('result');
      const total = data.model_a.length + data.model_b.length;
      if (total === 0) {
        toast.show(
          ingredients.length === 0
            ? '냉장고가 비어있어요. 재료를 먼저 추가해주세요.'
            : '조건에 맞는 레시피를 찾지 못했어요. 재료를 더 추가하거나 다른 음식 종류·국가를 선택해보세요.',
          'info',
        );
      } else {
        toast.show(`추천 ${total}개 도착!`, 'success');
      }
    } catch (err) {
      toast.show(apiErrorMessage(err), 'error');
      setPhase('error');
    } finally {
      if (progressIntervalRef.current !== null) {
        window.clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
      setProgress(100);
    }
  };

  return (
    <main className="min-h-screen bg-cream-100 dark:bg-clay-900">
      <header className="max-w-7xl mx-auto px-6 lg:px-12 py-6 flex items-center justify-between">
        <BrandLockup size="md" />
        <Link
          href="/fridge"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-clay-700 dark:text-cream-200 hover:text-gochu-500"
        >
          <ArrowLeft className="h-4 w-4" /> 냉장고로
        </Link>
      </header>

      <AnimatePresence mode="wait">
        {phase === 'wizard' && (
          <motion.section
            key="wizard"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3 }}
            className="max-w-2xl mx-auto px-6 lg:px-8 pt-4 pb-16"
          >
            <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight">
              <span className="ink-underline">취향</span>을 알려주세요
            </h1>
            <p className="mt-3 text-clay-700 dark:text-cream-200">
              두 단계만 답하면 AI가 13가지 메뉴를 골라드려요.
            </p>
            <div className="mt-10 rounded-3xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 shadow-sticker p-7 sm:p-9">
              <PreferenceWizard onSubmit={handleSubmit} />
            </div>
          </motion.section>
        )}

        {phase === 'loading' && (
          <motion.section
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="max-w-5xl mx-auto px-6 lg:px-8 pt-4 pb-24"
          >
            <div className="flex flex-col items-center text-center mb-10">
              <div className="relative mb-5">
                <span
                  aria-hidden="true"
                  className="absolute inset-0 rounded-full bg-gochu-500/30 blur-2xl animate-pulse-warm"
                />
                <div className="relative h-20 w-20 rounded-full bg-cream-50 dark:bg-clay-800 border-2 border-clay-900 dark:border-cream-100 shadow-sticker flex items-center justify-center">
                  <Sparkles className="h-9 w-9 text-gochu-500 animate-pulse" />
                </div>
              </div>
              <h2 className="font-display text-3xl font-bold">
                두 명의 셰프가 동시에 고민 중…
              </h2>
              <p className="mt-2 text-clay-700 dark:text-cream-200 max-w-md">
                모델 A는 냉장고 재료 그대로,<br />
                모델 B는 한 가지만 더 사면 되는 레시피를 찾고 있어요.
              </p>
              {/* progress */}
              <div className="mt-6 w-full max-w-md">
                <div className="h-2 rounded-full bg-clay-400/30 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.4 }}
                    className="h-full bg-gradient-to-r from-gochu-500 via-mustard-500 to-herb-500"
                  />
                </div>
                <p className="mt-1.5 text-xs text-clay-500 tabular-nums" aria-live="polite">
                  {progress}% · Gemini 추천 이유 분석 중
                </p>
              </div>
            </div>

            {/* Skeleton previews */}
            <div className="space-y-10">
              <div>
                <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
                  <Refrigerator className="h-5 w-5 text-herb-500" />
                  냉털 레시피
                </h3>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <RecipeCardSkeleton key={i} type="cold" />
                  ))}
                </div>
              </div>
              <div>
                <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
                  <ChefHat className="h-5 w-5 text-mustard-500" />
                  부족재료 레시피
                </h3>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <RecipeCardSkeleton key={i} type="missing" />
                  ))}
                </div>
              </div>
            </div>
          </motion.section>
        )}

        {phase === 'result' && result && (result.model_a.length + result.model_b.length === 0) && (
          <motion.section
            key="result-empty"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="max-w-2xl mx-auto px-6 lg:px-12 pt-12 pb-24 text-center"
          >
            <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-mustard-500/20 border-2 border-clay-900 dark:border-cream-100 mb-6">
              <Refrigerator className="h-8 w-8 text-mustard-600" />
            </div>
            <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">
              조건에 맞는 레시피를 찾지 못했어요
            </h1>
            <p className="mt-4 text-clay-700 dark:text-cream-200 leading-relaxed">
              냉장고 재료를 더 추가하거나,<br />
              음식 종류 · 선호 국가 · 알레르기 조건을 바꿔보세요.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Button variant="primary" onClick={() => setPhase('wizard')}>
                조건 다시 설정
              </Button>
              <Link
                href="/fridge"
                className="inline-flex items-center gap-1.5 px-5 h-11 rounded-full font-semibold border-2 border-clay-900 dark:border-cream-100 text-clay-900 dark:text-cream-100 hover:bg-cream-200 dark:hover:bg-clay-800 transition-colors"
              >
                <Refrigerator className="h-4 w-4" /> 냉장고로 돌아가기
              </Link>
            </div>
          </motion.section>
        )}

        {phase === 'result' && result && (result.model_a.length + result.model_b.length > 0) && (
          <motion.section
            key="result"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="max-w-7xl mx-auto px-6 lg:px-12 pt-4 pb-24"
          >
            <div className="flex flex-wrap items-end justify-between gap-4 mb-2">
              <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight">
                오늘의 <span className="ink-underline">추천</span>
              </h1>
              <Button variant="secondary" onClick={() => setPhase('wizard')}>
                조건 다시 설정
              </Button>
            </div>
            <p className="text-clay-700 dark:text-cream-200 mb-10">
              냉털 {result.model_a.length}개 · 부족재료 {result.model_b.length}개를 골라드렸어요.
            </p>

            {/* Cold recipes — model A */}
            <section className="mb-14">
              <header className="flex items-center justify-between mb-4">
                <h2 className="font-display text-2xl font-bold flex items-center gap-2">
                  <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-herb-500 text-cream-50 border-2 border-clay-900">
                    <Refrigerator className="h-5 w-5" />
                  </span>
                  냉털 레시피
                  <span className="text-base font-medium text-clay-500">
                    · 모델 A
                  </span>
                </h2>
                <span className="text-sm text-clay-500">
                  {result.model_a.length}개
                </span>
              </header>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
                {result.model_a.map((r, i) => (
                  <RecipeCard key={r.recipe_id} recipe={r} type="cold" index={i} />
                ))}
              </div>
            </section>

            {/* Missing recipes — model B */}
            <section>
              <header className="flex items-center justify-between mb-4">
                <h2 className="font-display text-2xl font-bold flex items-center gap-2">
                  <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-mustard-500 text-clay-900 border-2 border-clay-900">
                    <ChefHat className="h-5 w-5" />
                  </span>
                  부족재료 레시피
                  <span className="text-base font-medium text-clay-500">
                    · 모델 B
                  </span>
                </h2>
                <span className="text-sm text-clay-500">
                  {result.model_b.length}개
                </span>
              </header>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {result.model_b.map((r, i) => (
                  <RecipeCard key={r.recipe_id} recipe={r} type="missing" index={i} />
                ))}
              </div>
            </section>
          </motion.section>
        )}

        {phase === 'error' && (
          <motion.section
            key="error"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="max-w-md mx-auto px-6 pt-16 text-center"
          >
            <h2 className="font-display text-3xl font-bold">추천 실패</h2>
            <p className="mt-3 text-clay-700 dark:text-cream-200">
              잠시 후 다시 시도해주세요.
            </p>
            <div className="mt-6 flex justify-center gap-2">
              <Button variant="secondary" onClick={() => setPhase('wizard')}>
                다시 시도
              </Button>
              <Link
                href="/fridge"
                className="inline-flex items-center h-11 px-6 rounded-full border-2 border-clay-900 dark:border-cream-100 font-semibold"
              >
                냉장고로
              </Link>
            </div>
          </motion.section>
        )}
      </AnimatePresence>
    </main>
  );
}
