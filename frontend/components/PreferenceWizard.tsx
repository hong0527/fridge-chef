'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronLeft, ChevronRight, Flame, ChefHat } from 'lucide-react';
import { Button } from './Button';
import type { Preferences } from '@/lib/api';
import { cn } from '@/lib/cn';

interface PreferenceWizardProps {
  onSubmit: (prefs: Preferences) => void;
  loading?: boolean;
  initial?: Partial<Preferences>;
}

// 백엔드 _DIFFICULTY_MAP, _THEME_MAP, _COUNTRY_MAP 키와 동일하게 유지.
// 키 불일치 시 default 값으로 떨어져 모델 A의 country/theme/difficulty 차원이 무력화됨.
const DIFFICULTIES = ['초보', '중급', '고급'] as const;
const FOOD_TYPES = ['메인요리', '반찬', '국물', '디저트', '음료'];
const COUNTRIES = ['한식', '중식', '일식', '양식', '기타'];
const COOK_TIMES = [15, 30, 45, 60, 90, 120];

export function PreferenceWizard({
  onSubmit,
  loading = false,
  initial,
}: PreferenceWizardProps) {
  const [step, setStep] = useState<1 | 2>(1);
  // 백엔드 Preferences.spicy 는 1-5. UI 는 0-9 슬라이더 유지 → 제출 시 1-5 로 매핑.
  const [spice, setSpice] = useState<number>(5);
  const [difficulty, setDifficulty] = useState<(typeof DIFFICULTIES)[number]>(
    (initial?.difficulty as (typeof DIFFICULTIES)[number]) ?? '초보',
  );
  const [diet, setDiet] = useState<boolean>(initial?.diet ?? false);
  // UI 토글은 유지(레거시 일관성), 단 백엔드 전송에서는 제외 — 알레르기는 NFR-EVAL-001
  // 안전 정책에 따라 항상 적용(use_saved_allergies 우회 차단).
  const [useAllergies, setUseAllergies] = useState<boolean>(true);
  // 단일 선택 — 백엔드 Preferences.food_type/country가 단일 문자열이므로
  // UI 다중 선택은 사용자 의도 미스리딩(첫 개만 전송됨).
  const [foodType, setFoodType] = useState<string>(initial?.food_type ?? '');
  const [country, setCountry] = useState<string>(initial?.country ?? '');
  const [maxCookTime, setMaxCookTime] = useState<number | undefined>(
    initial?.max_cook_min,
  );
  const [situation, setSituation] = useState<string>(initial?.user_context ?? '');

  // Step 2 필수 입력 검증 — country/food_type 미선택 시 default 적용 차단.
  const canSubmit = Boolean(foodType && country);

  const handleSubmit = () => {
    if (!canSubmit) return;  // 버튼 disabled 외 안전망
    // UI 0-9 → 백엔드 1-5 매핑 (round(spice * 4 / 9) + 1).
    const spicyMapped = Math.min(5, Math.max(1, Math.round((spice * 4) / 9) + 1));
    onSubmit({
      spicy: spicyMapped,
      difficulty,
      diet,
      food_type: foodType,
      country: country,
      max_cook_min: maxCookTime ?? 60,
      user_context: situation.trim(),
    });
  };

  const spiceLabel =
    spice === 0
      ? '안 매워요'
      : spice <= 2
      ? '살짝 매콤'
      : spice <= 5
      ? '적당히 매운맛'
      : spice <= 7
      ? '제법 매워요'
      : '불맛 정복';

  return (
    <div className="relative">
      {/* progress */}
      <div className="mb-8 flex items-center gap-3 text-sm font-medium">
        <span
          className={cn(
            'flex items-center gap-2',
            step === 1 ? 'text-gochu-500' : 'text-clay-500',
          )}
        >
          <span
            className={cn(
              'inline-flex h-7 w-7 items-center justify-center rounded-full border-2 font-bold',
              step === 1
                ? 'bg-gochu-500 text-cream-50 border-clay-900'
                : 'bg-cream-50 text-clay-700 border-clay-400',
            )}
          >
            1
          </span>
          입맛 · 실력
        </span>
        <span className="flex-1 h-[2px] bg-clay-400/40 rounded-full overflow-hidden">
          <motion.span
            initial={false}
            animate={{ width: step === 2 ? '100%' : '0%' }}
            transition={{ duration: 0.4 }}
            className="block h-full bg-gochu-500"
          />
        </span>
        <span
          className={cn(
            'flex items-center gap-2',
            step === 2 ? 'text-gochu-500' : 'text-clay-500',
          )}
        >
          <span
            className={cn(
              'inline-flex h-7 w-7 items-center justify-center rounded-full border-2 font-bold',
              step === 2
                ? 'bg-gochu-500 text-cream-50 border-clay-900'
                : 'bg-cream-50 text-clay-700 border-clay-400',
            )}
          >
            2
          </span>
          취향 · 상황
        </span>
      </div>

      <AnimatePresence mode="wait">
        {step === 1 ? (
          <motion.div
            key="step1"
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -24 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="space-y-8"
          >
            {/* Spice */}
            <section>
              <div className="flex items-baseline justify-between mb-3">
                <h3 className="font-display text-lg font-bold flex items-center gap-2">
                  <Flame className="h-5 w-5 text-gochu-500" aria-hidden="true" />
                  맵기 정도
                </h3>
                <span className="text-sm text-clay-600 dark:text-clay-400">
                  <span className="font-bold text-gochu-500">{spice}</span>/9 · {spiceLabel}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={9}
                step={1}
                value={spice}
                onChange={(e) => setSpice(Number(e.target.value))}
                className="fc-slider"
                aria-label="맵기 정도 0에서 9까지"
              />
              <div className="mt-1 flex justify-between text-[10px] text-clay-500 font-mono">
                {Array.from({ length: 10 }, (_, i) => (
                  <span key={i}>{i}</span>
                ))}
              </div>
            </section>

            {/* Difficulty */}
            <section>
              <h3 className="font-display text-lg font-bold flex items-center gap-2 mb-3">
                <ChefHat className="h-5 w-5 text-herb-500" aria-hidden="true" />
                요리 실력
              </h3>
              <div role="radiogroup" aria-label="요리 실력" className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {DIFFICULTIES.map((d) => (
                  <button
                    key={d}
                    role="radio"
                    aria-checked={difficulty === d}
                    onClick={() => setDifficulty(d as (typeof DIFFICULTIES)[number])}
                    className={cn(
                      'h-12 rounded-2xl border-2 font-semibold transition-all',
                      difficulty === d
                        ? 'bg-clay-900 text-cream-50 border-clay-900 shadow-sticker dark:bg-cream-100 dark:text-clay-900 dark:border-cream-100'
                        : 'bg-cream-50 dark:bg-clay-800 text-clay-700 dark:text-cream-200 border-clay-400 hover:border-clay-900',
                    )}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </section>

            {/* Toggles */}
            <section className="space-y-3">
              <ToggleRow
                label="다이어트 모드"
                desc="저칼로리 · 저당 위주로 추천"
                checked={diet}
                onChange={setDiet}
              />
              <ToggleRow
                label="알레르기 자동 불러오기"
                desc="회원 정보의 알레르기 재료를 제외합니다"
                checked={useAllergies}
                onChange={setUseAllergies}
              />
            </section>
          </motion.div>
        ) : (
          <motion.div
            key="step2"
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -24 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="space-y-8"
          >
            <section>
              <div className="flex items-baseline justify-between mb-3">
                <h3 className="font-display text-lg font-bold">음식 종류 <span className="text-gochu-500">*</span></h3>
                {!foodType && (
                  <span className="text-xs text-clay-500">하나를 선택해주세요</span>
                )}
              </div>
              <div role="radiogroup" aria-label="음식 종류" className="flex flex-wrap gap-2">
                {FOOD_TYPES.map((t) => (
                  <ChoiceChip
                    key={t}
                    label={t}
                    active={foodType === t}
                    onClick={() => setFoodType(foodType === t ? '' : t)}
                  />
                ))}
              </div>
            </section>

            <section>
              <div className="flex items-baseline justify-between mb-3">
                <h3 className="font-display text-lg font-bold">선호 국가 <span className="text-gochu-500">*</span></h3>
                {!country && (
                  <span className="text-xs text-clay-500">하나를 선택해주세요</span>
                )}
              </div>
              <div role="radiogroup" aria-label="선호 국가" className="flex flex-wrap gap-2">
                {COUNTRIES.map((c) => (
                  <ChoiceChip
                    key={c}
                    label={c}
                    active={country === c}
                    onClick={() => setCountry(country === c ? '' : c)}
                  />
                ))}
              </div>
            </section>

            <section>
              <h3 className="font-display text-lg font-bold mb-3">최대 조리 시간</h3>
              <div className="flex flex-wrap gap-2">
                {COOK_TIMES.map((t) => (
                  <ChoiceChip
                    key={t}
                    label={`${t}분 이내`}
                    active={maxCookTime === t}
                    onClick={() => setMaxCookTime(maxCookTime === t ? undefined : t)}
                  />
                ))}
              </div>
            </section>

            <section>
              <label htmlFor="situation" className="block font-display text-lg font-bold mb-2">
                오늘의 상황
              </label>
              <textarea
                id="situation"
                rows={3}
                placeholder="예: 비 오는 날 따끈한 국물이 땡겨요"
                value={situation}
                onChange={(e) => setSituation(e.target.value)}
                maxLength={200}
                className="w-full rounded-2xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 px-4 py-3 text-base placeholder:text-clay-400 focus:border-gochu-500 focus:outline-none"
              />
              <p className="mt-1 text-xs text-clay-500 text-right">
                {situation.length}/200
              </p>
            </section>
          </motion.div>
        )}
      </AnimatePresence>

      {/* nav */}
      <div className="mt-10 flex items-center justify-between gap-3">
        {step === 2 ? (
          <Button
            variant="secondary"
            size="md"
            onClick={() => setStep(1)}
            type="button"
          >
            <ChevronLeft className="h-4 w-4" /> 이전
          </Button>
        ) : (
          <div />
        )}
        {step === 1 ? (
          <Button
            variant="primary"
            size="md"
            onClick={() => setStep(2)}
            type="button"
          >
            다음 <ChevronRight className="h-4 w-4" />
          </Button>
        ) : (
          <Button
            variant="primary"
            size="lg"
            loading={loading}
            onClick={handleSubmit}
            disabled={!canSubmit}
            type="button"
            aria-disabled={!canSubmit}
            title={canSubmit ? '추천 결과를 받습니다' : '음식 종류와 선호 국가를 선택해주세요'}
          >
            추천받기
          </Button>
        )}
      </div>
    </div>
  );
}

function ToggleRow({
  label,
  desc,
  checked,
  onChange,
}: {
  label: string;
  desc: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="w-full flex items-center justify-between gap-4 rounded-2xl border-2 border-clay-400 hover:border-clay-900 bg-cream-50 dark:bg-clay-800 dark:border-cream-100/30 dark:hover:border-cream-100 px-5 py-4 text-left transition-colors"
    >
      <span className="min-w-0">
        <span className="block font-semibold">{label}</span>
        <span className="block text-sm text-clay-600 dark:text-clay-400">{desc}</span>
      </span>
      <span
        aria-hidden="true"
        className={cn(
          'relative h-7 w-12 rounded-full border-2 border-clay-900 dark:border-cream-100 transition-colors',
          checked ? 'bg-herb-500' : 'bg-cream-200 dark:bg-clay-700',
        )}
      >
        <span
          className={cn(
            'absolute top-[2px] h-[18px] w-[18px] rounded-full bg-cream-50 border-2 border-clay-900 dark:border-cream-100 transition-all',
            checked ? 'left-[22px]' : 'left-[2px]',
          )}
        />
      </span>
    </button>
  );
}

function ChoiceChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'px-4 py-2 rounded-full border-2 text-sm font-semibold transition-all',
        active
          ? 'bg-gochu-500 text-cream-50 border-clay-900 shadow-sticker dark:border-cream-100'
          : 'bg-cream-50 dark:bg-clay-800 text-clay-700 dark:text-cream-200 border-clay-400 hover:border-clay-900',
      )}
    >
      {label}
    </button>
  );
}
