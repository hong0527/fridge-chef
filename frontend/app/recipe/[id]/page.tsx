'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Clock,
  ChefHat,
  Flame,
  Globe2,
  Tag,
  ShieldAlert,
  Star,
  ImageOff,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { BrandLockup } from '@/components/Brand';
import { Button } from '@/components/Button';
import { FridgeChip } from '@/components/FridgeChip';
import { useToast } from '@/components/Toast';
import { apiErrorMessage, getAllergies, getRecipe, type Recipe } from '@/lib/api';

const FAVORITE_ENABLED = false; // Could 우선순위 — SRS v1.10

interface RecipePageProps {
  params: { id: string };
}

export default function RecipeDetailPage({ params }: RecipePageProps) {
  const router = useRouter();
  const toast = useToast();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [loading, setLoading] = useState(true);
  // 클라이언트 환경 (회원 알레르기) — SRS: 사용자 알레르기 일치 시 경고
  const [userAllergies, setUserAllergies] = useState<string[]>([]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const data = await getRecipe(params.id);
        if (alive) setRecipe(data);
      } catch (err) {
        if (alive) toast.show(apiErrorMessage(err), 'error');
      } finally {
        if (alive) setLoading(false);
      }
    })();
    // SSR-safe helper (lib/api.ts) — typeof window guard 일관성 유지
    setUserAllergies(getAllergies());
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  const matchedAllergies =
    recipe?.allergens?.filter((a) => userAllergies.includes(a)) ?? [];

  if (loading) {
    return <RecipeDetailSkeleton />;
  }

  if (!recipe) {
    return (
      <main className="min-h-screen bg-cream-100 dark:bg-clay-900 flex items-center justify-center px-6 text-center">
        <div>
          <h1 className="font-display text-3xl font-bold">레시피를 찾을 수 없어요</h1>
          <p className="mt-2 text-clay-600 dark:text-clay-400">URL을 확인해주세요.</p>
          <Link
            href="/recommend"
            className="mt-6 inline-flex items-center gap-2 h-11 px-6 rounded-full bg-clay-900 text-cream-50 font-semibold"
          >
            <ArrowLeft className="h-4 w-4" /> 추천 화면으로
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-cream-100 dark:bg-clay-900">
      <header className="max-w-7xl mx-auto px-6 lg:px-12 py-6 flex items-center justify-between">
        <BrandLockup size="md" />
        <button
          onClick={() => router.back()}
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-clay-700 dark:text-cream-200 hover:text-gochu-500"
        >
          <ArrowLeft className="h-4 w-4" /> 결과로
        </button>
      </header>

      <article className="max-w-4xl mx-auto px-6 lg:px-8 pb-24">
        {/* Hero */}
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="grid md:grid-cols-2 gap-8 items-start"
        >
          <div className="relative aspect-square rounded-3xl overflow-hidden border-2 border-clay-900 dark:border-cream-100 bg-cream-200 dark:bg-clay-700 shadow-sticker">
            {recipe.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={recipe.image_url}
                alt={`${recipe.name} 완성 사진`}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="h-full w-full flex items-center justify-center text-clay-400">
                <ImageOff className="h-12 w-12" aria-hidden="true" />
              </div>
            )}
          </div>

          <div className="flex flex-col">
            {recipe.theme && (
              <span className="inline-flex w-fit items-center gap-1.5 px-3 py-1 rounded-full bg-gochu-500/10 text-gochu-600 dark:text-gochu-400 border-2 border-gochu-500 text-xs font-bold uppercase tracking-wider">
                <Tag className="h-3.5 w-3.5" aria-hidden="true" />
                {recipe.theme}
              </span>
            )}
            <h1 className="mt-3 font-display text-4xl sm:text-5xl font-bold tracking-tight leading-tight">
              {recipe.name}
            </h1>

            <dl className="mt-6 grid grid-cols-2 gap-3 text-sm">
              <Stat icon={<ChefHat />} label="난이도" value={`Lv ${recipe.difficulty_level}`} />
              <Stat icon={<Clock />} label="조리시간" value={`${recipe.cook_min}분`} />
              {recipe.country && (
                <Stat icon={<Globe2 />} label="국가" value={recipe.country} />
              )}
              <Stat
                icon={<Flame />}
                label="맵기"
                value={`${recipe.spicy}/5`}
                valueClass="text-gochu-500"
              />
              {recipe.is_low_calorie && (
                <Stat icon={<Flame />} label="저칼로리" value="Yes" />
              )}
            </dl>

            {/* Allergy warning */}
            {recipe.allergens && recipe.allergens.length > 0 && (
              <div
                className={`mt-5 rounded-2xl border-2 p-4 ${
                  matchedAllergies.length > 0
                    ? 'border-gochu-500 bg-gochu-500/10'
                    : 'border-clay-400 dark:border-cream-100/30 bg-cream-50 dark:bg-clay-800'
                }`}
              >
                <div className="flex items-center gap-2 font-bold">
                  <ShieldAlert
                    className={`h-5 w-5 ${matchedAllergies.length > 0 ? 'text-gochu-600' : 'text-clay-500'}`}
                    aria-hidden="true"
                  />
                  알레르기 정보
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {recipe.allergens.map((a) => {
                    const matched = userAllergies.includes(a);
                    return (
                      <span
                        key={a}
                        className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border-2 ${
                          matched
                            ? 'bg-gochu-500 text-cream-50 border-clay-900'
                            : 'bg-cream-50 dark:bg-clay-700 text-clay-700 dark:text-cream-200 border-clay-400'
                        }`}
                      >
                        {a}
                        {matched && (
                          <span className="ml-1" aria-label="내 알레르기 일치">
                            !
                          </span>
                        )}
                      </span>
                    );
                  })}
                </div>
                {matchedAllergies.length > 0 && (
                  <p className="mt-2 text-sm text-gochu-700 dark:text-gochu-400 font-semibold">
                    회원님의 알레르기 재료({matchedAllergies.join(', ')})가 포함되어 있어요.
                  </p>
                )}
              </div>
            )}

            <div className="mt-6">
              <Button
                variant="secondary"
                disabled={!FAVORITE_ENABLED}
                aria-label={FAVORITE_ENABLED ? '즐겨찾기 추가' : '즐겨찾기는 추후 지원 예정'}
                onClick={() => toast.show('즐겨찾기 기능은 곧 추가될 예정입니다.', 'info')}
              >
                <Star className="h-4 w-4" />
                즐겨찾기 추가
              </Button>
            </div>
          </div>
        </motion.section>

        {/* Ingredients */}
        {recipe.whole_ingredients && recipe.whole_ingredients.length > 0 && (
          <section className="mt-12">
            <h2 className="font-display text-2xl font-bold mb-3">재료</h2>
            <ul className="flex flex-wrap gap-2">
              {recipe.whole_ingredients.map((i) => (
                <li key={i}>
                  <FridgeChip name={i} variant="compact" />
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Steps — 백엔드는 list[str] (단순 텍스트) 또는 빈 배열 */}
        {recipe.steps && recipe.steps.length > 0 && (
          <section className="mt-14">
            <h2 className="font-display text-2xl font-bold mb-6">조리 순서</h2>
            <ol className="space-y-5">
              {recipe.steps.map((step, idx) => {
                const order = (step as { order?: number }).order ?? idx + 1;
                const text =
                  typeof step === 'string' ? step : (step as { text?: string }).text ?? '';
                return (
                  <motion.li
                    key={order}
                    initial={{ opacity: 0, y: 12 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: '-80px' }}
                    transition={{ duration: 0.4 }}
                    className="flex gap-4 sm:gap-6 rounded-3xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 p-5 shadow-soft"
                  >
                    <span
                      aria-hidden="true"
                      className="shrink-0 inline-flex h-11 w-11 items-center justify-center rounded-full bg-gochu-500 text-cream-50 border-2 border-clay-900 font-display font-bold text-lg"
                    >
                      {order}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-base sm:text-lg leading-relaxed">{text}</p>
                    </div>
                  </motion.li>
                );
              })}
            </ol>
          </section>
        )}
      </article>
    </main>
  );
}

function Stat({
  icon,
  label,
  value,
  valueClass,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-2xl border-2 border-clay-900/15 dark:border-cream-100/15 bg-cream-50 dark:bg-clay-800 px-3 py-2.5">
      <dt className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-clay-500 font-bold">
        <span className="shrink-0 [&>svg]:h-3.5 [&>svg]:w-3.5" aria-hidden="true">
          {icon}
        </span>
        {label}
      </dt>
      <dd className={`mt-0.5 font-display font-bold text-lg ${valueClass ?? ''}`}>
        {value}
      </dd>
    </div>
  );
}

function RecipeDetailSkeleton() {
  return (
    <main className="min-h-screen bg-cream-100 dark:bg-clay-900">
      <header className="max-w-7xl mx-auto px-6 lg:px-12 py-6">
        <BrandLockup size="md" />
      </header>
      <div className="max-w-4xl mx-auto px-6 lg:px-8 pb-24">
        <div className="grid md:grid-cols-2 gap-8">
          <div className="skeleton aspect-square rounded-3xl" />
          <div className="space-y-4">
            <div className="skeleton h-6 w-32 rounded-full" />
            <div className="skeleton h-10 w-3/4" />
            <div className="skeleton h-10 w-1/2" />
            <div className="grid grid-cols-2 gap-3 mt-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="skeleton h-16 rounded-2xl" />
              ))}
            </div>
          </div>
        </div>
        <div className="mt-12 space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="skeleton h-24 rounded-3xl" />
          ))}
        </div>
      </div>
    </main>
  );
}
