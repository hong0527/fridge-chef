'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { Clock, Flame, ChefHat, Tag } from 'lucide-react';
import { FridgeChip } from './FridgeChip';
import type { ModelACandidate, ModelBCandidate, Recipe } from '@/lib/api';
import { cn } from '@/lib/cn';

type CardRecipe = ModelACandidate | ModelBCandidate | Recipe;

interface RecipeCardProps {
  recipe: CardRecipe;
  type: 'cold' | 'missing';
  index?: number;
}

/**
 * RecipeCard — 모델 A(냉털) / 모델 B(부족재료) 통합 카드.
 * 백엔드 스키마 (schemas/recommend.py) 기준 필드명만 사용:
 *  - 공통: recipe_id, name, cook_min, spicy, difficulty_level, theme, country
 *  - 모델 A: score
 *  - 모델 B: final_score, have[], missing[], reason
 */
export function RecipeCard({ recipe, type, index = 0 }: RecipeCardProps) {
  const have = (recipe as ModelBCandidate).have;
  const missing = (recipe as ModelBCandidate).missing;
  const reason = (recipe as ModelBCandidate).reason;
  const imageUrl = (recipe as Recipe).image_url;

  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.5,
        delay: index * 0.06,
        ease: [0.22, 1, 0.36, 1],
      }}
      whileHover={{ y: -4 }}
      className={cn(
        'group relative flex flex-col overflow-hidden rounded-3xl border-2 bg-cream-50 dark:bg-clay-800 shadow-sticker hover:shadow-sticker-hover transition-shadow duration-300',
        type === 'cold'
          ? 'border-clay-900 dark:border-cream-100'
          : 'border-mustard-500',
      )}
    >
      <Link
        href={`/recipe/${recipe.recipe_id}`}
        className="flex h-full flex-col focus:outline-none"
      >
        {/* image */}
        <div className="relative aspect-[4/3] w-full overflow-hidden bg-cream-200 dark:bg-clay-700">
          {imageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={imageUrl}
              alt={`${recipe.name} 완성 사진`}
              className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-clay-400">
              <ChefHat className="h-12 w-12" aria-hidden="true" />
            </div>
          )}
          {/* type badge */}
          <span
            className={cn(
              'absolute top-3 left-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border-2 border-clay-900',
              type === 'cold'
                ? 'bg-herb-500 text-cream-50'
                : 'bg-mustard-500 text-clay-900',
            )}
          >
            {type === 'cold' ? '냉털 레시피' : '부족재료 +'}
          </span>
        </div>

        {/* body */}
        <div className="flex flex-1 flex-col gap-3 p-5">
          <h3 className="font-display text-xl font-bold leading-snug tracking-tight">
            {recipe.name}
          </h3>

          <dl className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-clay-600 dark:text-clay-400">
            <div className="inline-flex items-center gap-1">
              <Clock className="h-4 w-4" aria-hidden="true" />
              <dt className="sr-only">조리시간</dt>
              <dd>{recipe.cook_min}분</dd>
            </div>
            <div className="inline-flex items-center gap-1">
              <ChefHat className="h-4 w-4" aria-hidden="true" />
              <dt className="sr-only">난이도</dt>
              <dd>Lv {recipe.difficulty_level}</dd>
            </div>
            <div className="inline-flex items-center gap-1">
              <Flame className="h-4 w-4" aria-hidden="true" />
              <dt className="sr-only">맵기</dt>
              <dd>{recipe.spicy}/5</dd>
            </div>
            {recipe.theme && (
              <div className="inline-flex items-center gap-1">
                <Tag className="h-4 w-4" aria-hidden="true" />
                <dt className="sr-only">테마</dt>
                <dd>{recipe.theme}</dd>
              </div>
            )}
          </dl>

          {/* tag row — 모델 A: have, 모델 B: missing */}
          {type === 'cold' && have && have.length > 0 && (
            <div>
              <p className="text-[11px] font-bold tracking-wider uppercase text-herb-600 dark:text-herb-400 mb-1.5">
                활용할 냉장고 재료
              </p>
              <div className="flex flex-wrap gap-1.5">
                {have.slice(0, 6).map((ing) => (
                  <FridgeChip key={ing} name={ing} variant="used" />
                ))}
                {have.length > 6 && (
                  <FridgeChip
                    name={`+${have.length - 6}`}
                    variant="compact"
                  />
                )}
              </div>
            </div>
          )}

          {type === 'missing' && missing && missing.length > 0 && (
            <div>
              <p className="text-[11px] font-bold tracking-wider uppercase text-mustard-600 dark:text-mustard-400 mb-1.5">
                이것만 있으면 돼요
              </p>
              <div className="flex flex-wrap gap-1.5">
                {missing.map((ing) => (
                  <FridgeChip key={ing} name={ing} variant="missing" />
                ))}
              </div>
            </div>
          )}

          {/* Gemini 추천 이유 (모델 B 전용, 폴백 시 빈 문자열) */}
          {type === 'missing' && (
            <div
              className={cn(
                'mt-auto rounded-2xl px-4 py-3 text-sm leading-relaxed border-2 border-dashed',
                reason
                  ? 'border-mustard-500/40 text-clay-700 dark:text-cream-200 bg-mustard-500/5'
                  : 'border-clay-400 text-clay-500 italic',
              )}
            >
              <span className="inline-flex items-center gap-1.5 mb-1 text-xs font-bold text-mustard-600 dark:text-mustard-400">
                <Flame className="h-3.5 w-3.5" aria-hidden="true" />
                Gemini 추천 이유
              </span>
              <p className="mt-1">
                {reason || '추천 이유 일시 불가 (Gemini 폴백)'}
              </p>
            </div>
          )}
        </div>
      </Link>
    </motion.article>
  );
}

/** 결과 스켈레톤 */
export function RecipeCardSkeleton({ type = 'cold' }: { type?: 'cold' | 'missing' }) {
  return (
    <div
      className={cn(
        'flex flex-col overflow-hidden rounded-3xl border-2 bg-cream-50 dark:bg-clay-800 p-0',
        type === 'cold'
          ? 'border-clay-900/40 dark:border-cream-100/30'
          : 'border-mustard-500/40',
      )}
      aria-busy="true"
      aria-label="레시피 로딩 중"
    >
      <div className="skeleton aspect-[4/3] w-full rounded-none" />
      <div className="flex flex-col gap-3 p-5">
        <div className="skeleton h-6 w-3/4" />
        <div className="skeleton h-4 w-1/2" />
        <div className="flex gap-2">
          <div className="skeleton h-7 w-16 rounded-chip" />
          <div className="skeleton h-7 w-20 rounded-chip" />
          <div className="skeleton h-7 w-12 rounded-chip" />
        </div>
        {type === 'missing' && <div className="skeleton h-16 w-full rounded-2xl" />}
      </div>
    </div>
  );
}
